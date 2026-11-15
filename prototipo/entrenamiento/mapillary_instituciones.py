"""
Entorno Seguro GDL - Imágenes de Mapillary (2048 px) alrededor de las 1,646 instituciones
de Guadalajara, con las detecciones de Mapillary convertidas a etiquetas para Edge Impulse.

Por qué Mapillary: imágenes de calle con licencia CC BY-SA 4.0 y términos que permiten su uso
para entrenar algoritmos (sección 12), siempre que se cite a Mapillary y no se intente
reidentificar personas ni placas (las imágenes ya vienen difuminadas).

Requisitos:
  - Token de cliente de Mapillary (https://www.mapillary.com/dashboard/developers -> registrar
    una aplicación -> "Client Token", empieza con MLY|...). En PowerShell:
        $env:MAPILLARY_TOKEN="MLY|..."
  - pip install mapbox-vector-tile

Uso:
    python mapillary_instituciones.py --prueba            # 5 instituciones, para revisar
    python mapillary_instituciones.py --por-institucion 2 # todas

Salida: entrenamiento/mapillary/images/*.jpg + bounding_boxes.labels (formato Edge Impulse)
        entrenamiento/mapillary/imagenes.csv (institución, fecha, coordenadas, autor, etiquetas)
"""
import argparse
import base64
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
DENUE = os.path.join(BASE, "..", "datos", "denue_gdl_instituciones.csv")
OUT = os.path.join(BASE, "mapillary")
API = "https://graph.mapillary.com"

# Clases de Mapillary -> etiquetas del proyecto (las que importan para Entorno Seguro GDL)
CLASES = {
    "object--support--utility-pole": "poste_electrico",
    "object--support--pole": "poste",
    "object--street-light": "luminaria",
    "object--manhole": "alcantarilla",
    "object--catch-basin": "coladera",
    "construction--flat--crosswalk-plain": "cruce_peatonal",
    "marking--discrete--crosswalk-zebra": "cruce_peatonal",
}
MIN_LADO = 12  # px; cajas más chicas se descartan


def get(path, token, **params):
    params["access_token"] = token
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    for intento in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                sys.exit(f"Mapillary rechazó el token (HTTP {e.code}). Revisa MAPILLARY_TOKEN.")
            if e.code == 429 or intento < 3:
                time.sleep(3 * (intento + 1))
                continue
            raise
        except Exception:
            if intento == 3:
                raise
            time.sleep(3 * (intento + 1))


def cajas_de(det, w, h):
    """Decodifica la geometría (MVT en base64, extent 4096) a una caja en píxeles."""
    import mapbox_vector_tile
    tile = mapbox_vector_tile.decode(base64.decodebytes(det["geometry"].encode()),
                                     default_options={"y_coord_down": True})  # origen arriba-izquierda
    cajas = []
    for capa in tile.values():
        ext = capa.get("extent", 4096)
        for feat in capa["features"]:
            g = feat["geometry"]
            anillos = g["coordinates"] if g["type"] == "Polygon" else [r for p in g["coordinates"] for r in p]
            pts = [pt for anillo in anillos for pt in anillo]
            xs = [p[0] / ext * w for p in pts]
            ys = [p[1] / ext * h for p in pts]
            x0, x1, y0, y1 = max(0, min(xs)), min(w, max(xs)), max(0, min(ys)), min(h, max(ys))
            if x1 - x0 >= MIN_LADO and y1 - y0 >= MIN_LADO:
                cajas.append((round(x0), round(y0), round(x1 - x0), round(y1 - y0)))
    return cajas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--por-institucion", type=int, default=2)
    ap.add_argument("--radio", type=int, default=50, help="metros alrededor de la institución (máx 50)")
    ap.add_argument("--desde", default="2019-01-01", help="solo imágenes capturadas desde esta fecha")
    ap.add_argument("--prueba", action="store_true", help="solo 5 instituciones")
    a = ap.parse_args()

    token = os.environ.get("MAPILLARY_TOKEN")
    if not token:
        sys.exit("Falta la variable de entorno MAPILLARY_TOKEN (token de cliente MLY|...).")
    with open(DENUE, encoding="utf-8") as fh:
        inst = list(csv.DictReader(fh))
    if a.prueba:
        inst = inst[:5]
    desde_ms = int(time.mktime(time.strptime(a.desde, "%Y-%m-%d")) * 1000)

    os.makedirs(os.path.join(OUT, "images"), exist_ok=True)
    lab_path = os.path.join(OUT, "images", "bounding_boxes.labels")
    labels = {"version": 1, "type": "bounding-box-labels", "boundingBoxes": {}}
    if os.path.exists(lab_path):
        with open(lab_path, encoding="utf-8") as fh:
            labels = json.load(fh)
    filas, vistos = [], set(labels["boundingBoxes"])
    campos = "id,thumb_2048_url,captured_at,compass_angle,computed_geometry,width,height,is_pano,camera_type,creator"

    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed
    lock = threading.Lock()
    csv_path = os.path.join(OUT, "imagenes.csv")
    columnas = ["archivo", "institucion_id", "institucion", "captura", "lat", "lng", "autor_mapillary", "etiquetas"]
    if not os.path.exists(csv_path):
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, fieldnames=columnas).writeheader()

    def procesar(r):
        res = get("images", token, lat=r["latitud"], lng=r["longitud"], radius=a.radio, limit=100, fields=campos)
        imgs = [i for i in res.get("data", []) if not i.get("is_pano")
                and i.get("camera_type", "perspective") == "perspective"
                and i.get("captured_at", 0) >= desde_ms and i.get("thumb_2048_url")]
        imgs.sort(key=lambda i: -i["captured_at"])  # las más recientes primero
        tomadas = 0
        for im in imgs:
            if tomadas >= a.por_institucion:
                break
            nombre = f"mly_{im['id']}.jpg"
            with lock:  # reservar el nombre para que dos hilos no bajen la misma imagen
                if nombre in vistos:
                    continue
                vistos.add(nombre)
            w, h = im.get("width") or 2048, im.get("height") or 1536
            esc = 2048 / w if w > 2048 else 1.0  # la miniatura mide 2048 px de ancho
            wt, ht = round(w * esc), round(h * esc)
            dets = get(f"{im['id']}/detections", token, fields="value,geometry").get("data", [])
            cajas = []
            for d in dets:
                etiqueta = CLASES.get(d.get("value"))
                if etiqueta:
                    for (x, y, bw, bh) in cajas_de(d, wt, ht):
                        cajas.append({"label": etiqueta, "x": x, "y": y, "width": bw, "height": bh})
            dst = os.path.join(OUT, "images", nombre)
            if not os.path.exists(dst):
                with urllib.request.urlopen(im["thumb_2048_url"], timeout=120) as resp:
                    data = resp.read()
                with open(dst + ".tmp", "wb") as fh:
                    fh.write(data)
                os.replace(dst + ".tmp", dst)
            fila = {"archivo": nombre, "institucion_id": r["id"], "institucion": r["nom_estab"],
                    "captura": time.strftime("%Y-%m-%d", time.localtime(im["captured_at"] / 1000)),
                    "lng": im["computed_geometry"]["coordinates"][0] if im.get("computed_geometry") else "",
                    "lat": im["computed_geometry"]["coordinates"][1] if im.get("computed_geometry") else "",
                    "autor_mapillary": (im.get("creator") or {}).get("username", ""),
                    "etiquetas": ";".join(sorted({c["label"] for c in cajas}))}
            with lock:
                labels["boundingBoxes"][nombre] = cajas
                with open(csv_path, "a", newline="", encoding="utf-8") as fh:
                    csv.DictWriter(fh, fieldnames=columnas).writerow(fila)
            tomadas += 1

    def guardar():
        with lock:
            snap = json.dumps(labels)
        with open(lab_path + ".tmp", "w", encoding="utf-8") as fh:
            fh.write(snap)
        os.replace(lab_path + ".tmp", lab_path)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(procesar, r) for r in inst]
        for k, fu in enumerate(as_completed(futs), 1):
            try:
                fu.result()
            except Exception as exc:
                print(f"  error en una institución: {exc}")
            if k % 50 == 0 or k == len(inst):
                guardar()
                n_cajas = sum(len(v) for v in labels["boundingBoxes"].values())
                print(f"  {k}/{len(inst)} instituciones | imágenes: {len(labels['boundingBoxes'])} | "
                      f"cajas: {n_cajas} | {time.time() - t0:.0f} s")
    guardar()
    from collections import Counter
    c = Counter(b["label"] for v in labels["boundingBoxes"].values() for b in v)
    print(f"\nListo: {len(labels['boundingBoxes'])} imágenes | cajas por etiqueta: {dict(c)}")
    print("Atribución requerida: 'Imágenes © Mapillary y sus colaboradores, CC BY-SA 4.0'")


if __name__ == "__main__":
    main()
