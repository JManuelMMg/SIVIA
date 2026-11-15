"""
Entorno Seguro GDL - Evaluador de impacto + Clasificador + Coordinador.

Toma las detecciones del agente Inspector (modelo entrenado en Edge Impulse) sobre las imágenes
de calle de cada institución y genera órdenes de trabajo priorizadas por dependencia.

Entradas:
  agente/salida/detecciones.json     {archivo: [{"label", "score", "x", "y", "w", "h"}]}  (Inspector)
  entrenamiento/mapillary/imagenes.csv   archivo -> institución
  datos/denue_gdl_instituciones.csv      DENUE INEGI 05/2026 (dataset #09)
  datos/instituciones_siniestralidad.csv ATUS INEGI 2022-2024 (dataset #08)

Salidas (agente/salida/):
  hallazgos.csv          un renglón por hallazgo, con prioridad y explicación
  ordenes_trabajo.csv    hallazgos ordenados por prioridad, con la dependencia responsable
  resumen.json           conteos por zona, dependencia y tipo (línea base)

Uso:
  python agente/coordinador.py                 # condiciones normales
  python agente/coordinador.py --clima extremo # Vigía (SMN): escenario de evento extremo
  python agente/coordinador.py --umbral 0.5    # confianza mínima de las detecciones
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from instituciones_zonas import ZONAS, zona_de  # noqa: E402

SALIDA = os.path.join(BASE, "agente", "salida")
_ALTO = {}


def alto(f):
    """Alto en píxeles de una imagen de calle (para saber si una detección cae bajo el horizonte)."""
    if f not in _ALTO:
        from PIL import Image
        with Image.open(os.path.join(BASE, "entrenamiento", "mapillary", "images", f)) as im:
            _ALTO[f] = im.height
    return _ALTO[f]

# --- Clasificador: qué es cada hallazgo, qué tan grave y quién lo atiende -----------------
HALLAZGOS = {
    "bache": ("Bache frente a la institución", 1.0, "Dirección de Pavimentos"),
    "dano_pavimento": ("Daño en el pavimento (bache o piel de cocodrilo)", 0.9, "Dirección de Pavimentos"),
    "grieta_cocodrilo": ("Pavimento agrietado (se convertirá en bache)", 0.6, "Dirección de Pavimentos"),
    # alcantarilla_tapada = rejilla con su tapa en buen estado (así se etiquetó); solo amerita limpieza preventiva
    "alcantarilla_tapada": ("Rejilla pluvial: limpieza preventiva antes del temporal", 0.25, "Agua y Drenaje (SIAPA)"),
    "alcantarilla_riesgo": ("Alcantarilla obstruida, abierta o dañada", 1.0, "Agua y Drenaje (SIAPA)"),
    "arbol_riesgo": ("Árbol de riesgo (rama sobre cable o tronco inclinado)", 1.0, "Parques y Jardines"),
    "poste_electrico": ("Poste y cableado eléctrico a revisar", 0.3, "Alumbrado Público / CFE"),
    "sin_cruce": ("Sin cruce peatonal visible en zona con atropellamientos", 0.8, "Dirección de Movilidad"),
}

# --- Evaluador de impacto ---------------------------------------------------------------
TIPO = [("611111", "611112", "Preescolar", 1.0), ("62441", None, "Guardería / estancia", 1.0),
        ("611121", "611122", "Primaria", 0.9), ("622", None, "Hospital", 0.9)]
PER_OCU = {"0 a 5 personas": 1, "6 a 10 personas": 2, "11 a 30 personas": 3, "31 a 50 personas": 4,
           "51 a 100 personas": 5, "101 a 250 personas": 6, "251 y más personas": 7}


def tipo_de(codigo):
    for a, b, nombre, peso in TIPO:
        if codigo.startswith(a) or (b and codigo.startswith(b)):
            return nombre, peso
    return "Otra escuela", 0.7


def impacto(inst, sin):
    nombre, peso = tipo_de(inst["codigo_act"])
    tam = 0.7 + 0.05 * PER_OCU.get(inst["per_ocu"].strip(), 1)
    acc = int(sin.get("accidentes_200m_3a", 0) or 0)
    peat = int(sin.get("accidentes_con_peaton_200m", 0) or 0)
    riesgo = 1 + min(acc, 30) / 30 + 0.5 * min(peat, 3) / 3
    return nombre, peso * tam, riesgo, acc, peat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detecciones", default=os.path.join(SALIDA, "detecciones_yolo.json"))
    ap.add_argument("--umbral", type=float, default=0.5)
    ap.add_argument("--clima", choices=("actual", "extremo", "ninguno"), default="actual",
                    help="Vigía (SMN #45): pronóstico actual, escenario de evento extremo o sin clima")
    a = ap.parse_args()
    fac = {}
    ruta_clima = os.path.join(SALIDA, "clima_smn.json")
    if a.clima != "ninguno" and os.path.exists(ruta_clima):
        with open(ruta_clima, encoding="utf-8") as fh:
            c = json.load(fh)
        fac = c["factores_actuales"] if a.clima == "actual" else c["factores_escenario_extremo"]

    with open(a.detecciones, encoding="utf-8") as fh:
        dets = json.load(fh)
    with open(os.path.join(BASE, "datos", "denue_gdl_instituciones.csv"), encoding="utf-8") as fh:
        inst = {r["id"]: r for r in csv.DictReader(fh)}
    with open(os.path.join(BASE, "datos", "instituciones_siniestralidad.csv"), encoding="utf-8") as fh:
        sin = {r["id"]: r for r in csv.DictReader(fh)}
    img_inst = defaultdict(set)
    with open(os.path.join(BASE, "entrenamiento", "mapillary", "imagenes.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            img_inst[r["institucion_id"]].add(r["archivo"])

    hallazgos = []
    inspeccionadas = 0
    for iid, archivos in img_inst.items():
        archivos = [f for f in archivos if f in dets]
        if iid not in inst or not archivos:
            continue
        inspeccionadas += 1
        r = inst[iid]
        conteo = Counter()
        mejor = {}
        for f in archivos:
            for d in dets[f]:
                # YOLO trae su umbral calibrado por clase ("u"); lo demás (Mapillary, FOMO) usa --umbral
                if (d["score"] >= d["u"] and (d["label"] != "dano_pavimento" or d["y"] + d["h"] / 2 > 0.4 * alto(f))
                        if "u" in d else d["score"] >= a.umbral):
                    conteo[d["label"]] += 1
                    if d["score"] > mejor.get(d["label"], (0, ""))[0]:
                        mejor[d["label"]] = (d["score"], f)
        tipo, imp, riesgo, acc, peat = impacto(r, sin.get(iid, {}))
        encontrados = {k: v for k, v in conteo.items() if k in HALLAZGOS and k != "cruce_peatonal"}
        if (tipo != "Hospital" and conteo["cruce_peatonal"] == 0 and peat > 0 and len(archivos) >= 2):
            encontrados["sin_cruce"] = 1
        for clave, n in encontrados.items():
            desc, grav, dep = HALLAZGOS[clave]
            clima = fac.get(clave, 1.0)
            base = 100 * grav * min(1 + 0.15 * (n - 1), 1.45) * imp * riesgo
            prioridad = round(base * clima, 1)
            porque = (f"{desc}: {n} detección(es) en {len(archivos)} imagen(es). {tipo} "
                      f"({r['per_ocu'].strip()}). {acc} accidentes y {peat} atropellamientos a menos de 200 m "
                      f"(INEGI 2022-2024).") + (f" Clima SMN: prioridad x{clima:.2f}." if clima > 1 else "")
            hallazgos.append({
                "prioridad": prioridad, "prioridad_base": round(base, 1), "factor_clima": clima, "clave": clave,
                "hallazgo": desc, "dependencia": dep, "institucion": r["nom_estab"].strip(),
                "tipo": tipo, "zona": ZONAS[zona_de(float(r["latitud"]), float(r["longitud"]))][0],
                "direccion": f"{r['tipo_vial'].title()} {r['nom_vial'].title()} {r['numero_ext']}".strip(),
                "colonia": r["nomb_asent"].title(), "lat": r["latitud"], "lng": r["longitud"],
                "detecciones": n, "imagen_evidencia": (mejor.get(clave) or ("", sorted(archivos)[0]))[1],
                "explicacion": porque, "institucion_id": iid})

    hallazgos.sort(key=lambda h: -h["prioridad"])
    os.makedirs(SALIDA, exist_ok=True)
    campos = list(hallazgos[0].keys()) if hallazgos else ["prioridad"]
    for nombre in ("hallazgos.csv", "ordenes_trabajo.csv"):
        with open(os.path.join(SALIDA, nombre), "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=campos)
            w.writeheader()
            w.writerows(hallazgos)
    resumen = {
        "instituciones_inspeccionadas": inspeccionadas,
        "instituciones_con_hallazgos": len({h["institucion_id"] for h in hallazgos}),
        "hallazgos": len(hallazgos),
        "por_tipo": Counter(h["hallazgo"] for h in hallazgos),
        "por_dependencia": Counter(h["dependencia"] for h in hallazgos),
        "por_zona": Counter(h["zona"] for h in hallazgos),
        "umbral": a.umbral, "clima": a.clima,
    }
    with open(os.path.join(SALIDA, "resumen.json"), "w", encoding="utf-8") as fh:
        json.dump(resumen, fh, ensure_ascii=False, indent=1)
    print(json.dumps(resumen, ensure_ascii=False, indent=1))
    for h in hallazgos[:5]:
        print(f"  [{h['prioridad']:6.1f}] {h['dependencia']:<26} {h['institucion'][:40]:<40} {h['hallazgo']}")


if __name__ == "__main__":
    main()
