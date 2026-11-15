"""
Cámara del vehículo (simulada): recorre una zona de Guadalajara con imágenes reales de calle y
corre el detector YOLO11s v9 (ONNX) en cada cuadro, como lo haría una Raspberry Pi 5 en un camión municipal.

En el equipo real cada evento llevaría el recorte JPEG con rostros y placas difuminados; aquí se manda
el nombre de la imagen, que el tablero ya tiene en img/.

Uso:  python agente/camara_simulada.py [--servidor http://localhost:8765] [--pausa 1.2] [--cuadros 70]
"""
import argparse
import csv
import json
import math
import os
import sys
import time
import urllib.request
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from instituciones_zonas import zona_de  # noqa: E402

RAIZ = os.path.dirname(BASE)
IMGS = os.path.join(BASE, "entrenamiento", "mapillary", "images")
WEB_IMG = os.path.join(RAIZ, "entregables", "tablero", "img")
MODELO = os.path.join(BASE, "entrenamiento", "modelo", "entorno_seguro_v9_yolo11s.onnx")


def filtro(d, w, h):
    """Mismo criterio que el tablero y el coordinador (umbral calibrado por clase; ver inspector.confiable)."""
    from agente.inspector import confiable
    return confiable(d, w, h)


def ruta(cuadros=70):
    """Recorrido del vehículo: la zona con más candidatos, ordenada por vecino más cercano."""
    det = json.load(open(os.path.join(BASE, "agente", "salida", "detecciones_modelo.json"), encoding="utf-8"))
    vistos, frames = set(), []
    with open(os.path.join(BASE, "entrenamiento", "mapillary", "imagenes.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            f = r["archivo"]
            if f in vistos or f not in det or not r["lat"] or not os.path.exists(os.path.join(WEB_IMG, f)):
                continue
            vistos.add(f)
            la, ln = float(r["lat"]), float(r["lng"])
            n = sum(1 for d in det.get(f, []) if filtro(d, 2048, 1536))
            frames.append({"f": f, "la": la, "ln": ln, "z": zona_de(la, ln), "n": n})
    zona = Counter(fr["z"] for fr in frames if fr["n"]).most_common(1)[0][0]
    pend = [fr for fr in frames if fr["z"] == zona]
    actual = min(pend, key=lambda fr: fr["ln"])
    orden = []
    while pend and len(orden) < cuadros:
        pend.remove(actual)
        orden.append(actual)
        if pend:
            actual = min(pend, key=lambda fr: math.hypot(fr["la"] - actual["la"], fr["ln"] - actual["ln"]))
    return [{"f": fr["f"], "la": fr["la"], "ln": fr["ln"]} for fr in orden]


def detectar(det, img):
    """Escena completa (alcantarillas, árboles) + franja de pavimento (baches), sin duplicados."""
    crudo = det(img)
    crudo += [r for r in det.pavimento(img)
              if not any(q["label"] == r["label"] and abs(q["x"] - r["x"]) < 60 for q in crudo)]
    w, h = img.size
    return [{"k": d["label"], "s": d["score"],
             "caja": [round(d["x"] / w, 4), round(d["y"] / h, 4), round(d["w"] / w, 4), round(d["h"] / h, 4)]}
            for d in crudo if filtro(d, w, h)]


def enviar(servidor, ruta_api, datos):
    req = urllib.request.Request(servidor + ruta_api, data=json.dumps(datos).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--servidor", default="http://localhost:8765")
    ap.add_argument("--pausa", type=float, default=1.2, help="segundos entre cuadros")
    ap.add_argument("--cuadros", type=int, default=70)
    ap.add_argument("--vehiculo", default="GDL-01")
    a = ap.parse_args()
    from PIL import Image
    from agente.inspector import crear_detector
    det = crear_detector(MODELO)
    r = ruta(a.cuadros)
    enviar(a.servidor, "/api/reiniciar", {})
    print(f"Vehículo {a.vehiculo}: {len(r)} cuadros", flush=True)
    for i, fr in enumerate(r, 1):
        t = time.strftime("%H:%M:%S")
        enviar(a.servidor, "/api/posicion", {"veh": a.vehiculo, "la": fr["la"], "ln": fr["ln"], "f": fr["f"],
                                             "n": i, "total": len(r), "t": t})
        t0 = time.time()
        with Image.open(os.path.join(IMGS, fr["f"])) as img:
            dets = detectar(det, img.convert("RGB"))
        ms = round((time.time() - t0) * 1000)
        for d in dets:
            resp = enviar(a.servidor, "/api/deteccion", dict(d, veh=a.vehiculo, la=fr["la"], ln=fr["ln"], f=fr["f"], t=t))
            print(f"  [{i}/{len(r)}] {d['k']} {d['s']:.2f} -> {resp['id']} (vistas {resp['vistas']})", flush=True)
        if not dets:
            print(f"  [{i}/{len(r)}] sin detecciones ({ms} ms)", flush=True)
        time.sleep(max(0, a.pausa - (time.time() - t0)))
    print("Recorrido terminado.")


if __name__ == "__main__":
    main()
