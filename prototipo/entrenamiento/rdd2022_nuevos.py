"""
Baja de RDD2022 tres subconjuntos que el modelo no había visto, para reducir sesgos de fuente y de punto de vista:
  - China_Drone:     vista aérea desde dron (despliegue en drones)
  - China_MotorBike: cámara baja desde motocicleta
  - Japan:           cámara de vehículo, otro país y otro pavimento
Solo se usan bache (D40) y piel de cocodrilo (D20), que se unen en dano_pavimento. Se guardan también algunas
imágenes sin daño de ningún tipo como negativos. Lee el ZIP remoto por rangos, sin bajar 13 GB.

Uso:    python rdd2022_nuevos.py [--max-japon 1500]
Salida: rdd2022_nuevos/images/*.jpg + bounding_boxes.labels (formato Edge Impulse)
"""
import argparse
import json
import os
import random

import rdd2022_subset as r

BASE = os.path.dirname(os.path.abspath(__file__))
PAISES = ["China_Drone", "China_MotorBike", "Japan"]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-japon", type=int, default=1500)
    ap.add_argument("--negativas", type=float, default=0.12, help="fracción de negativos respecto a las positivas")
    a = ap.parse_args()
    r.OUT = os.path.join(BASE, "rdd2022_nuevos")
    os.makedirs(r.OUT, exist_ok=True)
    cand_path = os.path.join(r.OUT, "candidatos.json")
    f, z = r.abrir()
    zips = {p: r.abrir_pais(f, z, p) for p in PAISES}
    if os.path.exists(cand_path):
        cand = json.load(open(cand_path, encoding="utf-8"))
        con, sin = cand["con"], cand["sin"]
    else:
        con, sin = r.escanear(f, zips)
        json.dump({"con": con, "sin": sin}, open(cand_path, "w", encoding="utf-8"))
    # positivas: cualquier bache o piel de cocodrilo; negativas: sin ningún daño anotado
    todas = [((p, i), [tuple(o) for o in objs]) for (p, i), objs in con + sin]
    random.seed(13)
    random.shuffle(todas)
    elegidas, cuenta = [], {}
    for (p, i), objs in todas:
        if not objs:
            continue
        if p == "Japan" and cuenta.get(p, 0) >= a.max_japon:
            continue
        elegidas.append(((p, i), objs))
        cuenta[p] = cuenta.get(p, 0) + 1
    neg = [((p, i), []) for (p, i), objs in todas if not objs]
    n_neg = {p: int(c * a.negativas) for p, c in cuenta.items()}
    for (p, i), _ in neg:
        if n_neg.get(p, 0) > 0:
            elegidas.append(((p, i), []))
            n_neg[p] -= 1
    print("positivas por subconjunto:", cuenta, "| total con negativas:", len(elegidas))
    r.elegir_y_bajar(f, zips, elegidas, [], len(elegidas), 0, semilla=13)
