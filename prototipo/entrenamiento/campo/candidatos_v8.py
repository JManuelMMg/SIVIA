"""Candidatos para etiquetar fotos de Mapillary libres (ni reservadas ni usadas): une lo que proponen v4f, v5, v6 y v7
(conf >= 0.2, con el filtro adaptativo) y quita duplicados por clase. Salida: campo/candidatos_v8.json"""
import json, os, sys
from PIL import Image
from ultralytics import YOLO
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(BASE))
from agente.filtros import filtrar  # noqa: E402

def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy; u = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - i
    return i / u if u else 0

libres = json.load(open(os.path.join(BASE, "campo", "libres_v8.json")))
ms = {"v4f": YOLO(os.path.join(BASE, "modelo/yolo/v4_con_filtro/weights/best.pt")),
      "v5": YOLO(os.path.join(BASE, "modelo/yolo/v5_clima/weights/best.pt")),
      "v6": YOLO(os.path.join(BASE, "modelo/yolo/v6_gdl/weights/best.pt")),
      "v7": YOLO(os.path.join(BASE, "modelo/yolo/v7_gdl/weights/best.pt"))}
out = {}
for k, f in enumerate(libres):
    with Image.open(os.path.join(BASE, "mapillary", "images", f)) as im:
        im = filtrar(im.convert("RGB"))[0]
        cands = []
        for n, m in ms.items():
            r = m.predict(im, conf=0.2, verbose=False)[0]
            for b, c, s in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist()):
                lab = m.names[int(c)]
                dup = next((x for x in cands if x["clase"] == lab and iou(x["caja"], b) > 0.4), None)
                if dup:
                    dup["conf"][n] = round(s, 3)
                else:
                    cands.append({"clase": lab, "caja": [round(v) for v in b], "conf": {n: round(s, 3)}})
    out[f] = cands
    if k % 100 == 0:
        print(k, flush=True)
json.dump(out, open(os.path.join(BASE, "campo", "candidatos_v8.json"), "w"), indent=0)
from collections import Counter
print(Counter(x["clase"] for v in out.values() for x in v), "imagenes con candidatos:", sum(1 for v in out.values() if v))
