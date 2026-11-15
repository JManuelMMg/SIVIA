"""
Busca etiquetas dudosas comparando lo que predice el modelo con lo etiquetado (minería de errores de etiqueta).
  - "omitida": caja etiquetada sin ninguna predicción de su clase que la toque (IoU < 0.1 con conf >= 0.05).
               Puede ser un objeto difícil o una caja mal puesta.
  - "sin_etiqueta": predicción con conf >= 0.6 que no toca ninguna caja de su clase. Puede ser un objeto real
               que nadie etiquetó, o un falso positivo seguro.
Solo revisa imágenes originales (sin las variantes rotadas, que heredan la etiqueta de su original).

Uso:    .venv_yolo/Scripts/python auditar_etiquetas.py modelo/yolo/v4_con_filtro/weights/best.pt [--datos dataset_yolo_v4f]
Salida: modelo/auditoria_etiquetas.json
"""
import argparse
import json
import os
import re

from ultralytics import YOLO

BASE = os.path.dirname(os.path.abspath(__file__))
CLASES = ["alcantarilla_riesgo", "alcantarilla_tapada", "arbol_riesgo", "dano_pavimento"]


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i
    return i / u if u else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pesos")
    ap.add_argument("--datos", default="dataset_yolo_v4f")
    a = ap.parse_args()
    m = YOLO(os.path.join(BASE, a.pesos))
    out = {"omitida": [], "sin_etiqueta": [], "imagenes": 0}
    for parte in ("train", "val"):
        carpeta = os.path.join(BASE, a.datos, "images", parte)
        fs = [f for f in sorted(os.listdir(carpeta)) if not re.search(r"_a\d+\.jpg$", f)]
        for k in range(0, len(fs), 32):
            lote = fs[k:k + 32]
            res = m.predict([os.path.join(carpeta, f) for f in lote], conf=0.05, imgsz=640, verbose=False)
            for f, rr in zip(lote, res):
                h, w = rr.orig_shape
                gt = []
                for linea in open(os.path.join(BASE, a.datos, "labels", parte, f[:-4] + ".txt")).read().splitlines():
                    if linea.strip():
                        c, x, y, bw, bh = linea.split()
                        x, y, bw, bh = float(x) * w, float(y) * h, float(bw) * w, float(bh) * h
                        gt.append((int(c), [x - bw / 2, y - bh / 2, x + bw / 2, y + bh / 2]))
                pr = [(int(c), float(s), b.tolist()) for c, s, b in zip(rr.boxes.cls, rr.boxes.conf, rr.boxes.xyxy)]
                for c, b in gt:
                    if not any(pc == c and iou(b, pb) >= 0.1 for pc, _, pb in pr):
                        out["omitida"].append({"parte": parte, "img": f, "clase": CLASES[c], "caja": [round(v) for v in b]})
                for pc, s, pb in pr:
                    if s >= 0.6 and not any(c == pc and iou(b, pb) >= 0.1 for c, b in gt):
                        out["sin_etiqueta"].append({"parte": parte, "img": f, "clase": CLASES[pc], "conf": round(s, 3),
                                                    "caja": [round(v) for v in pb]})
            out["imagenes"] += len(lote)
    json.dump(out, open(os.path.join(BASE, "modelo", "auditoria_etiquetas.json"), "w", encoding="utf-8"), indent=1)
    from collections import Counter
    print("imágenes revisadas:", out["imagenes"])
    for t in ("omitida", "sin_etiqueta"):
        print(t, dict(Counter(x["clase"] for x in out[t])), "| fuentes:",
              dict(Counter(x["img"].split("_")[0] + "_" + x["img"].split("_")[1] for x in out[t]).most_common(6)))
