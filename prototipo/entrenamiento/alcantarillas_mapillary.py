"""
Entorno Seguro GDL - Recortes de alcantarillas y coladeras de Guadalajara desde Mapillary.

1. Recorre Guadalajara en cuadros de 0.01° (límite de la API) y pide los "map features"
   object--manhole (alcantarilla) y object--catch-basin (coladera).
2. Para cada objeto toma una detección en una imagen y baja la imagen de 1024 px.
3. Guarda un recorte cuadrado alrededor del objeto (con margen) para etiquetar su estado.

Uso:  $env:MAPILLARY_TOKEN="MLY|..." ;  python alcantarillas_mapillary.py --max 500
Salida: alcantarillas/recortes/*.jpg  +  alcantarillas/recortes.csv
"""
import argparse
import base64
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import mapbox_vector_tile
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "alcantarillas_hd")
API = "https://graph.mapillary.com"
GDL = (20.58, -103.44, 20.76, -103.24)  # lat_min, lng_min, lat_max, lng_max (aprox. municipio)


def get(path, token, **p):
    p["access_token"] = token
    url = f"{API}/{path}?{urllib.parse.urlencode(p)}"
    for i in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.loads(r.read())
        except Exception:
            if i == 3:
                return {}
            time.sleep(2 * (i + 1))


def caja(geom_b64, w, h):
    t = mapbox_vector_tile.decode(base64.decodebytes(geom_b64.encode()), default_options={"y_coord_down": True})
    pts = []
    for capa in t.values():
        ext = capa.get("extent", 4096)
        for f in capa["features"]:
            g = f["geometry"]
            anillos = g["coordinates"] if g["type"] == "Polygon" else [r for p in g["coordinates"] for r in p]
            pts += [(x / ext * w, y / ext * h) for a in anillos for x, y in a]
    if not pts:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=500)
    ap.add_argument("--ids", help="csv con columna feature_id: solo re-recortar esos")
    a = ap.parse_args()
    token = os.environ.get("MAPILLARY_TOKEN") or sys.exit("Falta MAPILLARY_TOKEN")
    os.makedirs(os.path.join(OUT, "recortes"), exist_ok=True)

    # 1) objetos en la ciudad
    feats = {}
    la0, lo0, la1, lo1 = GDL
    celdas = [(la0 + i * 0.01, lo0 + j * 0.01) for i in range(round((la1 - la0) / 0.01))
              for j in range(round((lo1 - lo0) / 0.01))]

    def buscar(c):
        la, lo = c
        r = get("map_features", token, bbox=f"{lo},{la},{lo + 0.0099},{la + 0.0099}",
                object_values="object--manhole,object--catch-basin", fields="id,object_value,geometry")
        return r.get("data", [])

    with ThreadPoolExecutor(8) as ex:
        for fu in as_completed([ex.submit(buscar, c) for c in celdas]):
            for f in fu.result():
                feats[f["id"]] = f
    print(f"Objetos encontrados en Guadalajara: {len(feats)}", flush=True)
    if a.ids:
        want = {r["feature_id"] for r in csv.DictReader(open(a.ids, encoding="utf-8"))}
        lista = [f for f in feats.values() if f["id"] in want]
    else:
        lista = sorted(feats.values(), key=lambda f: f["id"])[: a.max]

    # 2) una detección por objeto -> recorte
    def recortar(f):
        dets = get(f"{f['id']}/detections", token, fields="geometry,image{id,thumb_2048_url,width,height,captured_at}")
        for d in dets.get("data", [])[:3]:
            im = d.get("image") or {}
            if not im.get("thumb_2048_url"):
                continue
            w0, h0 = im.get("width") or 1024, im.get("height") or 768
            esc = 2048 / max(w0, 1)
            w, h = round(w0 * esc), round(h0 * esc)
            b = caja(d["geometry"], w, h)
            if not b or (b[2] - b[0]) < 10:
                continue
            with urllib.request.urlopen(im["thumb_2048_url"], timeout=60) as r:
                img = Image.open(__import__("io").BytesIO(r.read())).convert("RGB")
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            lado = max(320, 3 * max(b[2] - b[0], b[3] - b[1]))
            x0, y0 = max(0, cx - lado / 2), max(0, cy - lado / 2)
            x1, y1 = min(img.width, x0 + lado), min(img.height, y0 + lado)
            crop = img.crop((round(x0), round(y0), round(x1), round(y1)))
            nombre = f"alc_{f['id']}.jpg"
            crop.save(os.path.join(OUT, "recortes", nombre), quality=92)
            lng, lat = f["geometry"]["coordinates"]
            return {"archivo": nombre, "feature_id": f["id"], "clase_mapillary": f["object_value"],
                    "lat": lat, "lng": lng, "imagen_id": im["id"],
                    "captura": time.strftime("%Y-%m-%d", time.localtime(im.get("captured_at", 0) / 1000)),
                    "caja_en_recorte": json.dumps([round(b[0] - x0), round(b[1] - y0),
                                                   round(b[2] - x0), round(b[3] - y0)]),
                    "ancho": crop.width, "alto": crop.height}
        return None

    filas = []
    with ThreadPoolExecutor(8) as ex:
        for k, fu in enumerate(as_completed([ex.submit(recortar, f) for f in lista]), 1):
            try:
                r = fu.result()
                if r:
                    filas.append(r)
            except Exception as e:
                print("error:", e)
            if k % 100 == 0:
                print(f"  {k}/{len(lista)} | recortes: {len(filas)}", flush=True)
    csvp = os.path.join(OUT, "recortes.csv")
    previas = list(csv.DictReader(open(csvp, encoding="utf-8"))) if os.path.exists(csvp) else []
    vistos = {r["archivo"] for r in filas}
    filas = filas + [r for r in previas if r["archivo"] not in vistos]
    with open(csvp, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
    from collections import Counter
    print(f"Recortes: {len(filas)} | {Counter(r['clase_mapillary'] for r in filas)}")


if __name__ == "__main__":
    main()
