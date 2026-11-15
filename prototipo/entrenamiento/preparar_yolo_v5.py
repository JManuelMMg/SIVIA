"""
Dataset YOLO v5 = dataset_yolo_v4f (ya filtrado) + correcciones de etiquetas + RDD2022 de dron, moto y Japón
+ variantes de clima adverso. Pensado para drones y vehículos que recorren las vías también en temporal.

Cambios contra v4f, y el sesgo que atiende cada uno:
  1. Correcciones de la revisión a mano (campo/auditoria/correcciones.json): 4 cajas equivocadas fuera, 12 objetos
     reales sin etiqueta dentro.
  2. Validación más representativa: la v4 validaba con 17 alcantarillas de riesgo y 23 árboles, así que el umbral y
     el mejor modelo se elegían casi solo por pavimento. Se pasa el 25 % de las alcantarillas y árboles originales de
     entrenamiento a validación (sin sus variantes rotadas, para no filtrar información).
  3. Punto de vista y país: RDD2022 China_Drone (vista aérea), China_MotorBike (cámara baja) y Japan. De cada uno, 70 %
     entrenamiento, 10 % validación y 20 % se guarda como prueba aparte (prueba_dron, prueba_moto, prueba_japon) para
     medir cada condición por separado.
  4. Clima: al 35 % de las imágenes originales de entrenamiento se le agrega una variante de lluvia, noche, niebla o
     movimiento (clima_sintetico.py), y después pasa por el mismo filtro adaptativo que usa la cámara.
Además se genera calibracion/ (validación en formato Edge Impulse) para elegir umbrales fuera de la prueba.

Uso:    python preparar_yolo_v5.py
Salida: dataset_yolo_v5/ (datos.yaml, resumen.json), prueba_dron/, prueba_moto/, prueba_japon/, calibracion/
"""
import json
import os
import random
import re
import shutil
import sys
from collections import Counter

from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE))
sys.path.insert(0, BASE)
from agente.filtros import filtrar  # noqa: E402
from clima_sintetico import aplicar  # noqa: E402

V4F = os.path.join(BASE, "dataset_yolo_v4f")
OUT = os.path.join(BASE, "dataset_yolo_v5")
CLASES = ["alcantarilla_riesgo", "alcantarilla_tapada", "arbol_riesgo", "dano_pavimento"]
UNIR = {"bache": "dano_pavimento", "grieta_cocodrilo": "dano_pavimento"}
SUB = {"China_Drone": "prueba_dron", "China_MotorBike": "prueba_moto", "Japan": "prueba_japon"}
PESOS_CLIMA = [("lluvia", 0.45), ("noche", 0.2), ("niebla", 0.15), ("movimiento", 0.2)]
rnd = random.Random(21)


def variante(nombre):
    return re.search(r"_a\d+\.jpg$", nombre) is not None


def a_yolo(cajas, w, h):
    return [f"{CLASES.index(c)} {(x0 + x1) / 2 / w:.6f} {(y0 + y1) / 2 / h:.6f} {(x1 - x0) / w:.6f} {(y1 - y0) / h:.6f}"
            for c, x0, y0, x1, y1 in cajas]


def de_yolo(lineas, w, h):
    out = []
    for l in lineas:
        c, x, y, bw, bh = l.split()
        x, y, bw, bh = float(x) * w, float(y) * h, float(bw) * w, float(bh) * h
        out.append((CLASES[int(c)], x - bw / 2, y - bh / 2, x + bw / 2, y + bh / 2))
    return out


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i
    return i / u if u else 0


def escribir(parte, nombre, img, cajas):
    for d in ("images", "labels"):
        os.makedirs(os.path.join(OUT, d, parte), exist_ok=True)
    img.save(os.path.join(OUT, "images", parte, nombre), quality=95)
    open(os.path.join(OUT, "labels", parte, nombre[:-4] + ".txt"), "w").write("\n".join(a_yolo(cajas, *img.size)))


def enlazar(parte_src, parte_dst, nombre, lineas):
    for d in ("images", "labels"):
        os.makedirs(os.path.join(OUT, d, parte_dst), exist_ok=True)
    src = os.path.join(V4F, "images", parte_src, nombre)
    dst = os.path.join(OUT, "images", parte_dst, nombre)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)
    open(os.path.join(OUT, "labels", parte_dst, nombre[:-4] + ".txt"), "w").write("\n".join(lineas))


def guardar_ei(carpeta, items):
    """items: [(nombre, img PIL, [(clase, x0, y0, x1, y1)])] -> carpeta en formato Edge Impulse para evaluar_yolo."""
    os.makedirs(carpeta, exist_ok=True)
    lab = {}
    for nombre, img, cajas in items:
        img.save(os.path.join(carpeta, nombre), quality=95)
        lab[nombre] = [{"label": c, "x": round(x0), "y": round(y0), "width": round(x1 - x0), "height": round(y1 - y0)}
                       for c, x0, y0, x1, y1 in cajas]
    json.dump({"version": 1, "type": "bounding-box-labels", "boundingBoxes": lab},
              open(os.path.join(carpeta, "bounding_boxes.labels"), "w", encoding="utf-8"))


def main():
    for d in [OUT, os.path.join(BASE, "calibracion")] + [os.path.join(BASE, v) for v in SUB.values()]:
        if os.path.exists(d):
            shutil.rmtree(d)
    cuenta = Counter()
    corr = json.load(open(os.path.join(BASE, "campo", "auditoria", "correcciones.json"), encoding="utf-8"))
    quitar, agregar = {}, {}
    for x in corr["quitar"]:
        quitar.setdefault((x["parte"], x["img"]), []).append(x)
    for x in corr["agregar"]:
        agregar.setdefault((x["parte"], x["img"]), []).append(x)

    # 1) y 2) v4f con correcciones; parte de alcantarillas y árboles de train pasa a val
    originales = sorted(f for f in os.listdir(os.path.join(V4F, "images", "train"))
                        if f.startswith(("v2_alcantarilla", "v2_arbol")) and not variante(f))
    a_val = set(rnd.sample(originales, len(originales) // 4))
    raiz = lambda f: re.sub(r"_a\d+\.jpg$", ".jpg", f)  # noqa: E731
    entrenamiento_orig = []
    for parte in ("train", "val", "test"):
        for f in sorted(os.listdir(os.path.join(V4F, "images", parte))):
            lineas = [x for x in open(os.path.join(V4F, "labels", parte, f[:-4] + ".txt")).read().splitlines() if x.strip()]
            if (parte, f) in quitar or (parte, f) in agregar:
                with Image.open(os.path.join(V4F, "images", parte, f)) as im:
                    w, h = im.size
                cajas = de_yolo(lineas, w, h)
                for q in quitar.get((parte, f), []):
                    cajas = [c for c in cajas if not (c[0] == q["clase"] and iou(c[1:], q["caja"]) >= 0.5)]
                    cuenta["cajas_quitadas"] += 1
                for g in agregar.get((parte, f), []):
                    cajas.append((g["clase"], *g["caja"]))
                    cuenta["cajas_agregadas"] += 1
                lineas = a_yolo(cajas, w, h)
            destino = parte
            if parte == "train" and raiz(f) in a_val:
                if variante(f):
                    cuenta["variantes_descartadas"] += 1
                    continue
                destino = "val"
                cuenta["pasadas_a_val"] += 1
            enlazar(parte, destino, f, lineas)
            if destino == "train" and not variante(f):
                entrenamiento_orig.append((f, lineas))

    # 3) RDD2022 de dron, moto y Japón
    carpeta = os.path.join(BASE, "rdd2022_nuevos", "images")
    lab = json.load(open(os.path.join(carpeta, "bounding_boxes.labels"), encoding="utf-8"))["boundingBoxes"]
    pruebas = {v: [] for v in SUB.values()}
    nombres = sorted(lab)
    rnd.shuffle(nombres)
    for k, f in enumerate(nombres):
        sub = next(s for s in SUB if f.startswith(s))
        cajas = [(UNIR.get(b["label"], b["label"]), b["x"], b["y"], b["x"] + b["width"], b["y"] + b["height"])
                 for b in lab[f]]
        img = Image.open(os.path.join(carpeta, f)).convert("RGB")
        r = k % 10
        if r < 2:
            pruebas[SUB[sub]].append(("rdd_" + f, img, cajas))
            cuenta[f"{SUB[sub]}"] += 1
            continue
        parte = "val" if r == 2 else "train"
        escribir(parte, "rdd_" + f, filtrar(img)[0], cajas)
        cuenta[f"{sub}_{parte}"] += 1
        if parte == "train":
            entrenamiento_orig.append(("rdd_" + f, (os.path.join(carpeta, f), cajas)))
    for nombre_p, items in pruebas.items():
        guardar_ei(os.path.join(BASE, nombre_p), items)

    # 4) variantes de clima adverso
    tipos, pesos = zip(*PESOS_CLIMA)
    for k, (f, dato) in enumerate(entrenamiento_orig):
        if rnd.random() >= 0.35:
            continue
        tipo = rnd.choices(tipos, pesos)[0]
        if isinstance(dato, tuple):  # imagen cruda de RDD nuevo
            img, cajas = Image.open(dato[0]).convert("RGB"), dato[1]
        else:
            img = Image.open(os.path.join(OUT, "images", "train", f)).convert("RGB")
            cajas = de_yolo(dato, *img.size)
        escribir("train", f"w_{tipo}_{f}", filtrar(aplicar(img, tipo, k))[0], cajas)
        cuenta[f"clima_{tipo}"] += 1

    # calibración: validación original (sin clima) en formato Edge Impulse; ya está filtrada
    items = []
    for f in sorted(os.listdir(os.path.join(OUT, "images", "val"))):
        img = Image.open(os.path.join(OUT, "images", "val", f)).convert("RGB")
        lineas = [x for x in open(os.path.join(OUT, "labels", "val", f[:-4] + ".txt")).read().splitlines() if x.strip()]
        items.append((f, img, de_yolo(lineas, *img.size)))
    guardar_ei(os.path.join(BASE, "calibracion"), items)

    with open(os.path.join(OUT, "datos.yaml"), "w", encoding="utf-8") as fh:
        fh.write(f"path: {OUT.replace(os.sep, '/')}\ntrain: images/train\nval: images/val\ntest: images/test\n")
        fh.write("names:\n" + "".join(f"  {i}: {c}\n" for i, c in enumerate(CLASES)))
    for parte in ("train", "val", "test"):
        cuenta[parte] = len(os.listdir(os.path.join(OUT, "images", parte)))
        cls = Counter()
        for t in os.listdir(os.path.join(OUT, "labels", parte)):
            for l in open(os.path.join(OUT, "labels", parte, t)).read().splitlines():
                if l.strip():
                    cls[CLASES[int(l.split()[0])]] += 1
        cuenta[f"cajas_{parte}"] = dict(cls)
    json.dump(dict(cuenta), open(os.path.join(OUT, "resumen.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps(dict(cuenta), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
