"""
Tablero en vivo: entregables/tablero_vivo/  (index.html + smn_server.py + img/).

Integra el complemento del colaborador B (agente/colab_b/) con los datos reales del proyecto:
  - Plantilla y servidor de B: clima SMN en vivo, satélite GOES, radar RainViewer, límites INEGI,
    sismos SSN, placas USGS, pestaña de Análisis y validación humana de candidatos IA.
  - Datos nuestros: las órdenes de trabajo del Coordinador (salida/ordenes_trabajo.csv), los
    candidatos del detector YOLO11s sobre las fotos de Mapillary y sus imágenes de evidencia.

No escribe ningún token en el HTML: la foto de cada punto es la evidencia local de Mapillary.

Uso:  python agente/tablero.py   (primero, genera las imágenes reducidas)
      python agente/tablero_vivo.py
      entregables/tablero_vivo/iniciar_tablero.bat   (o: python smn_server.py dentro de esa carpeta)
"""
import csv
import json
import math
import os
import re
import shutil
import sys

from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from agente.coordinador import HALLAZGOS  # noqa: E402
from agente.camara_simulada import filtro  # noqa: E402

RAIZ = os.path.dirname(BASE)
B = os.path.join(BASE, "agente", "colab_b")
SAL = os.path.join(BASE, "agente", "salida")
IMG_TAB = os.path.join(RAIZ, "entregables", "tablero", "img")      # ya reducidas por tablero.py
IMG_ORIG = os.path.join(BASE, "entrenamiento", "mapillary", "images")
OUT = os.path.join(RAIZ, "entregables", "tablero_vivo")

# Nuestras claves -> categorías del tablero de B (las que B no tenía se agregan a la plantilla)
CATEGORIA = {"poste_electrico": "cableado_postes", "arbol_riesgo": "arboles_cables",
             "dano_pavimento": "baches_banquetas", "bache": "baches_banquetas",
             "grieta_cocodrilo": "baches_banquetas", "alcantarilla_tapada": "alcantarilla_tapada",
             "alcantarilla_riesgo": "alcantarilla_riesgo", "sin_cruce": "sin_cruce"}
CLASES_IA = ("arbol_riesgo", "dano_pavimento", "alcantarilla_tapada", "alcantarilla_riesgo")
# Mismos multiplicadores de prototipo que usa B (exploratorios, no criterios oficiales)
FACTOR_TORMENTA = {"arboles_cables": 1.5, "cableado_postes": 1.5}
FACTOR_LLUVIA = {"alcantarilla_tapada": 1.35, "alcantarilla_riesgo": 1.35, "baches_banquetas": 1.2}
TAM_RUTA, RADIO_RUTA_KM = 10, 3.0


def severidad(clave):
    g = HALLAZGOS[clave][1]
    return "critica" if g >= 1.0 else "alta" if g >= 0.8 else "media"


def dist_m(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(h))


def ruta(filas):
    """Hasta 10 instituciones cercanas, desde la más urgente, por vecino más cercano (como B)."""
    if not filas:
        return []
    ancla, radio = filas[0], RADIO_RUTA_KM
    ids = {f["id"] for f in filas}
    while True:
        cerca = [f for f in filas if dist_m(ancla, f) <= radio * 1000]
        if len({f["id"] for f in cerca}) >= min(TAM_RUTA, len(ids)) or radio > 50:
            break
        radio *= 1.5
    vistos, pts = set(), []
    for f in cerca:
        if f["id"] not in vistos:
            vistos.add(f["id"])
            pts.append(f)
        if len(pts) == TAM_RUTA:
            break
    r, resto = [pts[0]], pts[1:]
    while resto:
        s = min(resto, key=lambda f: dist_m(r[-1], f))
        r.append(s)
        resto.remove(s)
    return [f["id"] for f in r]


def copiar_img(f, usadas):
    if f and f not in usadas and os.path.exists(os.path.join(IMG_TAB, f)):
        shutil.copy2(os.path.join(IMG_TAB, f), os.path.join(OUT, "img", f))
        usadas.add(f)
    return f"img/{f}" if f in usadas else ""


def main():
    os.makedirs(os.path.join(OUT, "img"), exist_ok=True)
    usadas = set()
    with open(os.path.join(SAL, "ordenes_trabajo.csv"), encoding="utf-8-sig") as fh:
        ordenes = list(csv.DictReader(fh))
    datos = []
    for o in ordenes:
        acc = re.search(r"(\d+) accidentes", o["explicacion"])
        datos.append({"id": o["institucion_id"], "nombre": o["institucion"].title()[:60], "tipo": o["tipo"],
                      "categoria": CATEGORIA[o["clave"]], "dependencia": o["dependencia"],
                      "severidad": severidad(o["clave"]),
                      "descripcion": f"{o['hallazgo']}. {o['direccion']}, {o['colonia']}. {o['zona']}.",
                      "lat": float(o["lat"]), "lon": float(o["lng"]),
                      "prioridad_base": float(o["prioridad_base"]),
                      "accidentes_200m": int(acc.group(1)) if acc else 0,
                      "imagen": copiar_img(o["imagen_evidencia"], usadas)})

    # Candidatos del detector (uno por foto, el de mayor confianza) -> pestaña Validación IA
    det = json.load(open(os.path.join(SAL, "detecciones_modelo.json"), encoding="utf-8"))
    with open(os.path.join(BASE, "entrenamiento", "mapillary", "imagenes.csv"), encoding="utf-8") as fh:
        fotos = {r["archivo"]: r for r in csv.DictReader(fh)}
    inst = {d["id"]: d for d in datos}
    dep_de = {k: v[2] for k, v in HALLAZGOS.items()}
    n_ia = 0
    for f, ds in det.items():
        r = fotos.get(f)
        if not r:
            continue
        if os.path.exists(os.path.join(IMG_ORIG, f)):
            with Image.open(os.path.join(IMG_ORIG, f)) as im:
                w, h = im.size
        elif os.path.exists(os.path.join(IMG_TAB, f)):  # paquete sin originales: Mapillary entrega 2048 px de
            with Image.open(os.path.join(IMG_TAB, f)) as im:  # ancho; la copia reducida conserva la proporción
                w, h = 2048, round(2048 * im.size[1] / im.size[0])
        else:
            continue
        ok = [d for d in ds if d["label"] in CLASES_IA and filtro(d, w, h)]
        if not ok:
            continue
        d = max(ok, key=lambda d: d["score"])
        cerca = inst.get(r["institucion_id"])
        datos.append({"id": f"ia_{f[4:-4]}", "nombre": cerca["nombre"] if cerca else "Punto inspeccionado",
                      "tipo": cerca["tipo"] if cerca else "Vía pública",
                      "categoria": CATEGORIA[d["label"]], "dependencia": dep_de[d["label"]],
                      "severidad": "media", "descripcion": HALLAZGOS[d["label"]][0],
                      "lat": float(r["lat"]), "lon": float(r["lng"]),
                      "prioridad_base": round(min(float(o["prioridad_base"]) for o in ordenes), 1),
                      "accidentes_200m": cerca["accidentes_200m"] if cerca else 0,
                      "confianza": round(d["score"], 2), "estado_revision": "pendiente",
                      "modelo_clase": d["label"], "fecha_captura": r.get("captura", ""),
                      "imagen": copiar_img(f, usadas)})
        n_ia += 1

    with open(os.path.join(BASE, "datos", "denue_gdl_instituciones.csv"), encoding="utf-8") as fh:
        n_denue = sum(1 for _ in csv.DictReader(fh))
    operables = sorted((d for d in datos if "modelo_clase" not in d), key=lambda d: -d["prioridad_base"])
    rutas = {}
    for d in operables:
        rutas.setdefault(d["dependencia"], []).append(d)
    rutas = {k: ruta(v) for k, v in rutas.items()}
    ps = sorted(d["prioridad_base"] for d in operables)
    rojo, amar, pmax = ps[int(0.8 * (len(ps) - 1))], ps[len(ps) // 2], ps[-1]

    # Plantilla de B con los ajustes mínimos para nuestros datos (cada cambio se verifica)
    html = open(os.path.join(B, "tablero_plantilla.html"), encoding="utf-8").read()
    cambios = [
        ("<title>Inspección urbana GDL</title>", "<title>SIVIA · Tablero en vivo</title>"),
        ("const UMBRAL_ROJO = 6, UMBRAL_AMAR = 3;",
         f"const UMBRAL_ROJO = {rojo}, UMBRAL_AMAR = {amar}, PMAX = {pmax};"),
        ('alcantarilla_tapada:"Alcantarilla aparentemente obstruida" };',
         'alcantarilla_tapada:"Rejilla pluvial: limpieza preventiva", '
         'alcantarilla_riesgo:"Alcantarilla abierta o dañada", '
         'sin_cruce:"Sin cruce peatonal visible" };'),
        ("radius:6+Math.min(top.p,14)/2", "radius:6+Math.min(top.p*14/PMAX,14)/2"),
        ("llenarMapillary(box,Number(top.lat),Number(top.lon));",
         "llenarMapillary(box,Number(top.lat),Number(top.lon),top.imagen);"),
        ("async function llenarMapillary(container, lat, lon) {\n",
         "async function llenarMapillary(container, lat, lon, local) {\n"
         "  if (local && imageSource(local)) { container.innerHTML = `<img src=\"${imageSource(local)}\" "
         "alt=\"Evidencia\"><div class=\"mly-credit\">Evidencia: Mapillary (CC BY-SA)</div>`; return; }\n"),
        # Plataforma: cada validación se guarda también en PostgreSQL (plataforma/servidor.py) y al abrir
        # se traen las validaciones de todos los operadores; sin base, sigue en el navegador.
        ("  try { localStorage.setItem(REVIEW_KEY,JSON.stringify(revisiones)); } catch (_) {}\n",
         "  try { localStorage.setItem(REVIEW_KEY,JSON.stringify(revisiones)); } catch (_) {}\n"
         "  fetch(`/api/candidatos/${encodeURIComponent(id)}`,{method:\"POST\",headers:{\"Content-Type\":\"application/json\"},"
         "body:JSON.stringify({estado:status})}).catch(()=>{});\n"),
        ("cargarClima(); setInterval(cargarClima, CLIMA_REFRESH_MS);",
         "async function sincronizarBD(){try{const r=await fetch(\"/api/candidatos\",{cache:\"no-store\"});"
         "if(!r.ok)return;const j=await r.json();if(!j.ok)return;Object.assign(revisiones,j.estados);"
         "Object.keys(revisiones).forEach(k=>{if(revisiones[k]===\"pendiente\")delete revisiones[k];});"
         "indicadores();pintarIA();pintarAnalisis();pintarOrdenes();}catch(_){}}\n"
         "sincronizarBD(); setInterval(sincronizarBD, 60000);\n"
         "cargarClima(); setInterval(cargarClima, CLIMA_REFRESH_MS);"),
        ("El modelo entrenado en Edge Impulse revisa cada imagen de calle.",
         "El detector YOLO11s del proyecto revisa cada imagen de calle de Mapillary."),
    ]
    for viejo, nuevo in cambios:
        assert viejo in html, f"no encontré en la plantilla de B: {viejo[:60]}"
        html = html.replace(viejo, nuevo)
    html = (html.replace("__DATOS__", json.dumps(datos, ensure_ascii=False, separators=(",", ":")))
                .replace("__RUTAS__", json.dumps(rutas, ensure_ascii=False))
                .replace("__TOTAL_INST__", str(n_denue))
                .replace("__TORMENTA__", json.dumps(FACTOR_TORMENTA))
                .replace("__LLUVIA__", json.dumps(FACTOR_LLUVIA))
                .replace("__MAPILLARY_TOKEN__", '""'))
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(html)

    srv = open(os.path.join(B, "smn_server.py"), encoding="utf-8").read()
    assert srv.count("/resultados_b/tablero.html") == 2
    with open(os.path.join(OUT, "smn_server.py"), "w", encoding="utf-8") as fh:
        fh.write(srv.replace("/resultados_b/tablero.html", "/index.html"))
    bat = open(os.path.join(B, "iniciar_tablero.bat"), encoding="utf-8").read()
    assert bat.count("smn_server.py") == 2
    with open(os.path.join(OUT, "iniciar_tablero.bat"), "w", encoding="utf-8") as fh:
        fh.write(bat.replace("smn_server.py", "servidor.py"))
    for f in ("servidor.py", "iniciar_con_bd.ps1"):
        shutil.copy2(os.path.join(BASE, "plataforma", f), os.path.join(OUT, f))
    print(f"tablero en vivo: {OUT}\\index.html | órdenes {len(operables)} | candidatos IA {n_ia} | "
          f"imágenes {len(usadas)} | rutas {len(rutas)} | colores rojo>={rojo} amarillo>={amar}")


if __name__ == "__main__":
    main()
