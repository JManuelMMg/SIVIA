r"""
Carga la línea base del sistema en PostgreSQL: instituciones (DENUE + ATUS), imágenes, detecciones del
modelo, órdenes de trabajo, candidatos para validar y el pronóstico SMN usado.

Se puede correr las veces que haga falta: actualiza los datos y CONSERVA el estado que las personas ya
dieron (órdenes asignadas o resueltas, candidatos confirmados o descartados).

La conexión se toma SOLO de la variable de entorno DATABASE_URL; nunca se escribe en un archivo.
Uso (PowerShell):  .\plataforma\iniciar_con_bd.ps1 -Solo cargar
"""
import csv
import json
import os
import sys

import psycopg
from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # prototipo/
RAIZ = os.path.dirname(BASE)
sys.path.insert(0, BASE)
from instituciones_zonas import ZONAS, zona_de  # noqa: E402
from agente.coordinador import tipo_de  # noqa: E402
from agente.camara_simulada import filtro  # noqa: E402

SAL = os.path.join(BASE, "agente", "salida")
IMG_ORIG = os.path.join(BASE, "entrenamiento", "mapillary", "images")
IMG_TAB = os.path.join(RAIZ, "entregables", "tablero", "img")
MODELO = "yolo11s_v9"
CLASES_IA = ("arbol_riesgo", "dano_pavimento", "alcantarilla_tapada", "alcantarilla_riesgo")


def leer(p, enc="utf-8"):
    with open(p, encoding=enc) as fh:
        return list(csv.DictReader(fh))


def entero(v):
    try:
        return int(float(v or 0))
    except ValueError:
        return 0


def tam(f):
    """Tamaño de la foto original; sin ella, la proporción de la copia reducida a 2048 px de ancho."""
    if os.path.exists(os.path.join(IMG_ORIG, f)):
        with Image.open(os.path.join(IMG_ORIG, f)) as im:
            return im.size
    if os.path.exists(os.path.join(IMG_TAB, f)):
        with Image.open(os.path.join(IMG_TAB, f)) as im:
            return 2048, round(2048 * im.size[1] / im.size[0])
    return None


def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Falta DATABASE_URL en el entorno (usa plataforma/iniciar_con_bd.ps1).")

    sin = {r["id"]: r for r in leer(os.path.join(BASE, "datos", "instituciones_siniestralidad.csv"))}
    inst = []
    for r in leer(os.path.join(BASE, "datos", "denue_gdl_instituciones.csv")):
        la, ln = float(r["latitud"]), float(r["longitud"])
        s = sin.get(r["id"], {})
        inst.append((r["id"], r["nom_estab"].strip(), tipo_de(r["codigo_act"])[0], r["codigo_act"],
                     ZONAS[zona_de(la, ln)][0],
                     f"{r['tipo_vial'].title()} {r['nom_vial'].title()} {r['numero_ext']}".strip(),
                     r["nomb_asent"].title(), la, ln, entero(s.get("accidentes_200m_3a")),
                     entero(s.get("accidentes_con_peaton_200m")), entero(s.get("heridos_200m")),
                     entero(s.get("muertos_200m"))))
    ids = {i[0] for i in inst}

    det = json.load(open(os.path.join(SAL, "detecciones_yolo.json"), encoding="utf-8"))
    fotos = {r["archivo"]: r for r in leer(os.path.join(BASE, "entrenamiento", "mapillary", "imagenes.csv"))
             if r["archivo"] in det}
    imgs = [(f, r["institucion_id"] if r["institucion_id"] in ids else None, r.get("captura"),
             float(r["lat"]) if r["lat"] else None, float(r["lng"]) if r["lng"] else None, r.get("autor_mapillary"))
            for f, r in fotos.items()]
    dets = [(f, MODELO if d.get("fuente") != "mapillary" else "mapillary", d["label"], d["score"], d.get("u"),
             d["x"], d["y"], d["w"], d["h"], d.get("fuente", "modelo"))
            for f, ds in det.items() if f in fotos for d in ds]

    cands = []
    for f, ds in det.items():
        if f not in fotos:
            continue
        ok = [d for d in ds if d["label"] in CLASES_IA and d.get("fuente") != "mapillary"]
        wh = tam(f) if ok else None
        ok = [d for d in ok if wh and filtro(d, *wh)]
        if ok:
            d = max(ok, key=lambda d: d["score"])
            iid = fotos[f]["institucion_id"]
            cands.append((f"ia_{f[4:-4]}", f, iid if iid in ids else None, d["label"], round(d["score"], 3)))

    ords = [(f"{o['institucion_id']}:{o['clave']}", o["institucion_id"] if o["institucion_id"] in ids else None,
             o["clave"], o["hallazgo"], o["dependencia"], float(o["prioridad_base"]), float(o["factor_clima"]),
             float(o["prioridad"]), entero(o["detecciones"]), o["imagen_evidencia"], o["explicacion"])
            for o in leer(os.path.join(SAL, "ordenes_trabajo.csv"), "utf-8-sig")]
    clima = json.load(open(os.path.join(SAL, "clima_smn.json"), encoding="utf-8"))

    with psycopg.connect(url) as con, con.cursor() as cur:
        cur.execute(open(os.path.join(os.path.dirname(__file__), "esquema.sql"), encoding="utf-8").read())
        cur.executemany("""INSERT INTO instituciones VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET nombre=EXCLUDED.nombre, tipo=EXCLUDED.tipo, codigo_scian=EXCLUDED.codigo_scian,
            zona=EXCLUDED.zona, direccion=EXCLUDED.direccion, colonia=EXCLUDED.colonia, lat=EXCLUDED.lat, lng=EXCLUDED.lng,
            accidentes_200m=EXCLUDED.accidentes_200m, atropellamientos_200m=EXCLUDED.atropellamientos_200m,
            heridos_200m=EXCLUDED.heridos_200m, muertos_200m=EXCLUDED.muertos_200m""", inst)
        cur.executemany("""INSERT INTO imagenes (archivo, institucion_id, fecha_captura, lat, lng, autor)
            VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (archivo) DO UPDATE SET institucion_id=EXCLUDED.institucion_id,
            fecha_captura=EXCLUDED.fecha_captura, lat=EXCLUDED.lat, lng=EXCLUDED.lng, autor=EXCLUDED.autor""", imgs)
        # Al cambiar de modelo se reemplazan sus detecciones; órdenes y candidatos que ya no salen se borran solo si
        # nadie los ha revisado (lo revisado por una persona se conserva).
        cur.execute("DELETE FROM detecciones WHERE fuente = 'modelo' OR modelo IN (%s, 'mapillary')", (MODELO,))
        cur.execute("DELETE FROM ordenes WHERE estado = 'pendiente' AND NOT (id = ANY(%s))", ([o[0] for o in ords],))
        cur.execute("DELETE FROM candidatos WHERE estado = 'pendiente' AND NOT (id = ANY(%s))", ([c[0] for c in cands],))
        cur.executemany("""INSERT INTO detecciones (archivo, modelo, clase, confianza, umbral, x, y, w, h, fuente)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", dets)
        cur.executemany("""INSERT INTO ordenes (id, institucion_id, clave, hallazgo, dependencia, prioridad_base,
            factor_clima, prioridad, detecciones, imagen, explicacion) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET hallazgo=EXCLUDED.hallazgo, dependencia=EXCLUDED.dependencia,
            prioridad_base=EXCLUDED.prioridad_base, factor_clima=EXCLUDED.factor_clima, prioridad=EXCLUDED.prioridad,
            detecciones=EXCLUDED.detecciones, imagen=EXCLUDED.imagen, explicacion=EXCLUDED.explicacion,
            actualizada_en=now()""", ords)
        cur.executemany("""INSERT INTO candidatos (id, archivo, institucion_id, clase, confianza) VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET clase=EXCLUDED.clase, confianza=EXCLUDED.confianza""", cands)
        cur.execute("INSERT INTO pronosticos (fuente, datos) VALUES (%s, %s)",
                    ("SMN/CONAGUA", json.dumps({"pronostico": clima.get("pronostico"),
                                                "nivel_actual": clima.get("nivel_actual")}, ensure_ascii=False)))
        con.commit()
        cur.execute("SELECT (SELECT count(*) FROM instituciones), (SELECT count(*) FROM imagenes), "
                    "(SELECT count(*) FROM detecciones), (SELECT count(*) FROM ordenes), "
                    "(SELECT count(*) FROM candidatos), (SELECT count(*) FROM candidatos WHERE estado <> 'pendiente')")
        n = cur.fetchone()
    print(f"base cargada | instituciones {n[0]} | imágenes {n[1]} | detecciones {n[2]} | órdenes {n[3]} | "
          f"candidatos {n[4]} (ya revisados {n[5]})")


if __name__ == "__main__":
    main()
