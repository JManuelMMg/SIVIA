"""
Dataset YOLO v7 = dataset_yolo_v6 + 1,170 fotos de Mapillary bajadas el 13-nov-2026 (campo/candidatos_v7.py, revisión en
campo/v7/revision.json). Mismo procedimiento que v6, descrito abajo.

(v6) Dataset YOLO v6 = dataset_yolo_v5 + escenas recientes de Mapillary en Guadalajara revisadas a mano.

Las 749 fotos de Mapillary que no estaban reservadas ni usadas pasaron por v4f y v5 (campo/candidatos_v6.py); los 284
candidatos se revisaron uno por uno (campo/v6/revision.json). Lo real queda como caja; lo falso (rejillas de
ventilación del tablero, pintura vial, árboles sin cables) queda como ejemplo negativo de la misma imagen.
Se separa por institución (20 % a validación) para no tener fotos casi iguales en los dos lados. Como son pocas frente
a las ~9,000 de v5, cada foto de entrenamiento se repite 4 veces: original, espejo, lluvia y noche.

Uso:    python preparar_yolo_v7.py
Salida: dataset_yolo_v7/ (datos.yaml, resumen.json) y calibracion_v7/ (validación en formato Edge Impulse)
"""
import csv
import json
import os
import random
import shutil
import sys
from collections import Counter

from PIL import Image, ImageOps

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE))
sys.path.insert(0, BASE)
from agente.filtros import filtrar  # noqa: E402
from clima_sintetico import aplicar  # noqa: E402
from preparar_yolo_v5 import CLASES, a_yolo, de_yolo, guardar_ei  # noqa: E402

V5 = os.path.join(BASE, "dataset_yolo_v6")
OUT = os.path.join(BASE, "dataset_yolo_v7")
MLY = os.path.join(BASE, "mapillary", "images")


def enlazar_todo():
    for d in ("images", "labels"):
        for parte in ("train", "val", "test"):
            src, dst = os.path.join(V5, d, parte), os.path.join(OUT, d, parte)
            os.makedirs(dst, exist_ok=True)
            for f in os.listdir(src):
                try:
                    os.link(os.path.join(src, f), os.path.join(dst, f))
                except OSError:
                    shutil.copy2(os.path.join(src, f), os.path.join(dst, f))


def escribir(parte, nombre, img, cajas):
    img.save(os.path.join(OUT, "images", parte, nombre), quality=95)
    open(os.path.join(OUT, "labels", parte, nombre[:-4] + ".txt"), "w").write("\n".join(a_yolo(cajas, *img.size)))


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    enlazar_todo()
    cuenta = Counter()
    mapa = json.load(open(os.path.join(BASE, "campo", "v7", "mapa.json")))
    reales = set(json.load(open(os.path.join(BASE, "campo", "v7", "revision.json"), encoding="utf-8"))["reales"])
    cajas = {}
    for k, (f, x) in mapa.items():
        cajas.setdefault(f, [])
        if k in reales:
            cajas[f].append((x["clase"], *x["caja"]))
    inst = {r["archivo"]: r["institucion_id"] for r in csv.DictReader(open(os.path.join(BASE, "mapillary", "imagenes.csv"),
                                                                             encoding="utf-8"))}
    inst_csv = inst
    inst = {f: inst.get(f, f) for f in cajas}
    ids = sorted(set(inst.values()))
    rnd = random.Random(7)
    val_ids = set(rnd.sample(ids, len(ids) // 5))
    # mantener la separación de v6: una institución que ya está en entrenamiento (o validación) de v6 se queda ahí
    for parte in ("train", "val"):
        ya = {i for n in os.listdir(os.path.join(V5, "images", parte)) if n.startswith("m6_")
              for i in [inst_csv.get(n[3:])] if i}
        val_ids = (val_ids - ya) if parte == "train" else (val_ids | (ya & set(ids)))
    val_items = []
    for k, (f, cs) in enumerate(sorted(cajas.items())):
        img = filtrar(Image.open(os.path.join(MLY, f)).convert("RGB"))[0]
        if inst[f] in val_ids:
            escribir("val", f"m7_{f}", img, cs)
            val_items.append((f"m7_{f}", img, cs))
            cuenta["val"] += 1
            continue
        w = img.width
        espejo = [(c, w - x1, y0, w - x0, y1) for c, x0, y0, x1, y1 in cs]
        crudo = Image.open(os.path.join(MLY, f)).convert("RGB")
        escribir("train", f"m7_{f}", img, cs)
        escribir("train", f"m7e_{f}", ImageOps.mirror(img), espejo)
        escribir("train", f"m7l_{f}", filtrar(aplicar(crudo, "lluvia", k))[0], cs)
        escribir("train", f"m7n_{f}", filtrar(aplicar(crudo, "noche", k + 999))[0], cs)
        cuenta["train_originales"] += 1
        cuenta["negativas" if not cs else "con_objetos"] += 1
        for c in cs:
            cuenta[f"cajas_{c[0]}"] += 1

    # calibración = validación de v5 + escenas de Guadalajara de validación
    cal = os.path.join(BASE, "calibracion_v7")
    if os.path.exists(cal):
        shutil.rmtree(cal)
    shutil.copytree(os.path.join(BASE, "calibracion_v6"), cal)
    lab = json.load(open(os.path.join(cal, "bounding_boxes.labels"), encoding="utf-8"))
    for nombre, img, cs in val_items:
        img.save(os.path.join(cal, nombre), quality=95)
        lab["boundingBoxes"][nombre] = [{"label": c, "x": round(x0), "y": round(y0), "width": round(x1 - x0),
                                         "height": round(y1 - y0)} for c, x0, y0, x1, y1 in cs]
    json.dump(lab, open(os.path.join(cal, "bounding_boxes.labels"), "w", encoding="utf-8"))

    with open(os.path.join(OUT, "datos.yaml"), "w", encoding="utf-8") as fh:
        fh.write(f"path: {OUT.replace(os.sep, '/')}\ntrain: images/train\nval: images/val\ntest: images/test\n")
        fh.write("names:\n" + "".join(f"  {i}: {c}\n" for i, c in enumerate(CLASES)))
    for parte in ("train", "val"):
        cuenta[f"total_{parte}"] = len(os.listdir(os.path.join(OUT, "images", parte)))
    json.dump(dict(cuenta), open(os.path.join(OUT, "resumen.json"), "w", encoding="utf-8"), indent=1)
    print(json.dumps(dict(cuenta), indent=1))


if __name__ == "__main__":
    main()
