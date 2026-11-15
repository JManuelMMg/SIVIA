"""
Baja de RDD2022 todas las imágenes con bache o piel de cocodrilo que aún no se usan (India, República Checa y
Estados Unidos, ya indexadas en rdd2022_subset/candidatos.json). Lee el ZIP remoto por rangos, sin bajar 13 GB.

Uso:    python rdd2022_mas.py [--max 3000]
Salida: rdd2022_mas/images/*.jpg + bounding_boxes.labels (formato Edge Impulse)
"""
import argparse
import json
import os

import rdd2022_subset as r

BASE = os.path.dirname(os.path.abspath(__file__))


def ya_usadas():
    vistos = set()
    for d in ("rdd2022_subset", "rdd2022_grietas", "rdd2022_fondos"):
        carpeta = os.path.join(BASE, d, "images")
        if os.path.isdir(carpeta):
            vistos |= set(os.listdir(carpeta))
    return vistos


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=3000)
    a = ap.parse_args()
    cand = json.load(open(os.path.join(BASE, "rdd2022_subset", "candidatos.json"), encoding="utf-8"))
    vistos = ya_usadas()
    nuevas = [((p, i), [tuple(o) for o in objs]) for (p, i), objs in cand["con"] + cand["sin"]
              if objs and p + "_" + os.path.basename(i) not in vistos]
    print(f"Imágenes con daño sin usar: {len(nuevas)}")
    r.OUT = os.path.join(BASE, "rdd2022_mas")
    paises = sorted({p for (p, _), _ in nuevas})
    f, z = r.abrir()
    zips = {p: r.abrir_pais(f, z, p) for p in paises}
    r.elegir_y_bajar(f, zips, nuevas, [], a.max, 0, semilla=11)
