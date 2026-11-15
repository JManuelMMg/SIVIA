"""
Tablero de operación: entregables/tablero/index.html  (+ img/ con la evidencia de Mapillary).

Une el trabajo de todos los agentes:
  - Inventario DENUE (#09) y siniestralidad ATUS (#08): mapa de instituciones y mapa de calor de accidentes.
  - Coordinador: órdenes de trabajo priorizadas, con filtros, búsqueda, exportación y orden imprimible.
  - Vigía (SMN #45): pronóstico de 4 días, umbrales históricos y escenario de evento extremo que
    recalcula las prioridades en vivo.
  - Inspector (modelo Edge Impulse): candidatos detectados en las imágenes de calle, con validación
    humana (confirmar / descartar) y exportación de los confirmados.

Uso:  python agente/tablero.py
"""
import csv
import json
import os
import sys

from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from instituciones_zonas import ZONAS, zona_de  # noqa: E402
from agente.coordinador import tipo_de  # noqa: E402
from agente.camara_simulada import filtro, ruta  # noqa: E402
from agente.centro_control import Enriquecedor  # noqa: E402

RAIZ = os.path.dirname(BASE)
OUT = os.path.join(RAIZ, "entregables", "tablero")
IMG_OUT = os.path.join(OUT, "img")
IMG_IN = os.path.join(BASE, "entrenamiento", "mapillary", "images")
SAL = os.path.join(BASE, "agente", "salida")
ANCHO = 720


def leer(p, enc="utf-8"):
    with open(p, encoding=enc) as fh:
        return list(csv.DictReader(fh))


inst = leer(os.path.join(BASE, "datos", "denue_gdl_instituciones.csv"))
sin = {r["id"]: r for r in leer(os.path.join(BASE, "datos", "instituciones_siniestralidad.csv"))}
ordenes = leer(os.path.join(SAL, "ordenes_trabajo.csv"), "utf-8-sig")
det_mly = json.load(open(os.path.join(SAL, "detecciones_confiables.json"), encoding="utf-8"))
det_mod = json.load(open(os.path.join(SAL, "detecciones_modelo.json"), encoding="utf-8"))
# Solo las fotos que revisó el Inspector (imagenes.csv también lista las bajadas para entrenar)
imgs_csv = [r for r in leer(os.path.join(BASE, "entrenamiento", "mapillary", "imagenes.csv")) if r["archivo"] in det_mod]
clima = json.load(open(os.path.join(SAL, "clima_smn.json"), encoding="utf-8"))
atus = leer(os.path.join(BASE, "datos", "atus_gdl_2022_2024.csv"))

# --- Imágenes: copia reducida + cajas normalizadas ------------------------------------------
os.makedirs(IMG_OUT, exist_ok=True)
por_inst, imagenes, tam_img = {}, {}, {}
for r in imgs_csv:
    f = r["archivo"]
    src = os.path.join(IMG_IN, f)
    if not os.path.exists(src):
        continue
    with Image.open(src) as im:
        w, h = im.size
        tam_img[f] = (w, h)
        dst = os.path.join(IMG_OUT, f)
        if not os.path.exists(dst):
            im.convert("RGB").resize((ANCHO, round(h * ANCHO / w)), Image.LANCZOS).save(dst, quality=68, optimize=True)
    cajas = []
    for d in det_mly.get(f, []):
        if d["label"] in ("poste_electrico", "cruce_peatonal"):
            cajas.append([d["label"], 0.9, round(d["x"] / w, 4), round(d["y"] / h, 4), round(d["w"] / w, 4),
                          round(d["h"] / h, 4), "mly"])
    for d in det_mod.get(f, []):
        if filtro(d, w, h):
            cajas.append([d["label"], d["score"], round(d["x"] / w, 4), round(d["y"] / h, 4), round(d["w"] / w, 4),
                          round(d["h"] / h, 4), "modelo"])
    imagenes[f] = {"id": f[4:-4], "autor": r["autor_mapillary"], "fecha": r["captura"], "r": round(h / w, 4),
                   "c": cajas}
    por_inst.setdefault(r["institucion_id"], []).append(f)

# --- Instituciones ---------------------------------------------------------------------------
ord_por = {}
for o in ordenes:
    ord_por.setdefault(o["institucion_id"], []).append(o)
puntos = []
for r in inst:
    s = sin.get(r["id"], {})
    acc, peat = int(s.get("accidentes_200m_3a", 0) or 0), int(s.get("accidentes_con_peaton_200m", 0) or 0)
    hs = ord_por.get(r["id"], [])
    nivel = 2 if (hs and peat > 0) or any(h["clave"] == "sin_cruce" for h in hs) else \
        1 if (hs or peat > 0 or acc >= 15) else 0
    lat, lng = float(r["latitud"]), float(r["longitud"])
    puntos.append({"id": r["id"], "la": round(lat, 5), "ln": round(lng, 5), "n": nivel,
                   "nom": r["nom_estab"].strip().title()[:60], "t": tipo_de(r["codigo_act"])[0],
                   "z": ZONAS[zona_de(lat, lng)][0], "acc": acc, "peat": peat,
                   "her": int(float(s.get("heridos_200m", 0) or 0)), "mue": int(float(s.get("muertos_200m", 0) or 0)),
                   "per": r["per_ocu"].strip(), "dir": f"{r['tipo_vial'].title()} {r['nom_vial'].title()} {r['numero_ext']}".strip(),
                   "col": r["nomb_asent"].title(), "img": por_inst.get(r["id"], [])})

ords = [{"pb": float(o["prioridad_base"]), "k": o["clave"], "h": o["hallazgo"], "dep": o["dependencia"],
         "inst": o["institucion"].title()[:60], "iid": o["institucion_id"], "t": o["tipo"], "z": o["zona"],
         "dir": o["direccion"], "col": o["colonia"], "la": float(o["lat"]), "ln": float(o["lng"]),
         "img": o["imagen_evidencia"], "x": o["explicacion"].split(" Clima SMN")[0]} for o in ordenes]

# Candidatos del modelo para validación humana (uno por imagen, el de mayor confianza)
cands = []
inst_de = {r["archivo"]: r["institucion_id"] for r in imgs_csv}
nom = {p["id"]: p for p in puntos}
for f, d in imagenes.items():
    mods = [c for c in d["c"] if c[6] == "modelo"]
    if mods and inst_de.get(f) in nom:
        c = max(mods, key=lambda c: c[1])
        p = nom[inst_de[f]]
        cands.append({"f": f, "k": c[0], "s": c[1], "iid": p["id"], "inst": p["nom"], "z": p["z"],
                      "la": p["la"], "ln": p["ln"]})
cands.sort(key=lambda c: -c["s"])

acc_pts = [[round(float(r["LATITUD"]), 4), round(float(r["LONGITUD"]), 4),
            1 if int(r["PEATHERIDO"] or 0) + int(r["PEATMUERTO"] or 0) > 0 else 0] for r in atus]

# Recorrido grabado para la pestaña "En vivo" cuando no hay centro de control corriendo
enr, vivo, R = Enriquecedor(), [], ruta()
for i, fr in enumerate(R, 1):
    vivo.append({"tipo": "pos", "veh": "GDL-01", "la": fr["la"], "ln": fr["ln"], "f": fr["f"], "n": i, "total": len(R)})
    w, h = tam_img[fr["f"]]
    for d in det_mod.get(fr["f"], []):
        if filtro(d, w, h):
            vivo.append(enr.procesar({"k": d["label"], "s": d["score"], "la": fr["la"], "ln": fr["ln"], "f": fr["f"],
                                      "caja": [round(d["x"] / w, 4), round(d["y"] / h, 4), round(d["w"] / w, 4),
                                               round(d["h"] / h, 4)]}))

DATA = {"vivo": vivo, "p": puntos, "o": ords, "img": imagenes, "cand": cands, "acc": acc_pts,
        "clima": {k: clima[k] for k in ("umbrales_mm", "maximo_historico", "climatologia_mensual_mm",
                                        "eventos_extremos_por_mes", "pronostico", "nivel_actual", "factores_actuales",
                                        "factores_escenario_extremo", "periodo_historico", "dias_con_dato",
                                        "lluvia_vs_accidentes")}}

plantilla = open(os.path.join(BASE, "agente", "tablero_plantilla.html"), encoding="utf-8").read()
html = plantilla.replace("/*__DATA__*/null", json.dumps(DATA, ensure_ascii=False, separators=(",", ":")))
with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as fh:
    fh.write(html)
viejo = os.path.join(RAIZ, "entregables", "tablero.html")
if os.path.exists(viejo):
    os.remove(viejo)
tam = sum(os.path.getsize(os.path.join(IMG_OUT, x)) for x in os.listdir(IMG_OUT)) / 1e6
print(f"recorrido en vivo: {len(R)} cuadros, {len(enr.eventos)} eventos")
print(f"tablero: {OUT}\\index.html | instituciones {len(puntos)} | órdenes {len(ords)} | imágenes {len(imagenes)} "
      f"({tam:.0f} MB) | candidatos del modelo {len(cands)} | accidentes {len(acc_pts)} | "
      f"niveles alto/medio/bajo {sum(p['n'] == 2 for p in puntos)}/{sum(p['n'] == 1 for p in puntos)}/{sum(p['n'] == 0 for p in puntos)}")
