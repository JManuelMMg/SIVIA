"""
Dataset YOLO v4 = dataset_yolo (v3) + datos nuevos, con o sin filtro adaptativo por imagen.

Datos nuevos:
  - rdd2022_mas: imágenes de RDD2022 con bache o piel de cocodrilo que no se habían usado (-> dano_pavimento).
    Se descartan las casi idénticas (hash de diferencia, distancia <= 6) a cualquier imagen de prueba o ya usada.
  - campo/etiquetas_campo.json: imágenes de calle de Guadalajara (Mapillary) revisadas a mano; las detecciones
    falsas quedan como imágenes sin objetos (negativos difíciles). Nunca entran las instituciones reservadas
    para medir en campo (modelo/campo_reservado.json).
  - 9 rejillas nuevas revisadas en alcantarillas_hd/laminas/lam_38.

Uso:   python preparar_yolo_v4.py            -> dataset_yolo_v4/
       python preparar_yolo_v4.py --filtro   -> dataset_yolo_v4f/ (todas las imágenes pasan por agente/filtros.py)
Salida: datos.yaml y filtros.json (qué filtro recibió cada imagen).
"""
import argparse
import csv
import json
import os
import random
import shutil
import sys

from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE))
from agente.filtros import filtrar  # noqa: E402

V3 = os.path.join(BASE, "dataset_yolo")
CLASES = ["alcantarilla_riesgo", "alcantarilla_tapada", "arbol_riesgo", "dano_pavimento"]
UNIR = {"bache": "dano_pavimento", "grieta_cocodrilo": "dano_pavimento"}
LADO_CAMPO = 1280


def dhash(img, n=8):
    g = img.convert("L").resize((n + 1, n))
    p = list(g.getdata())
    return sum(1 << i for i in range(n * n) if p[(i // n) * (n + 1) + i % n] > p[(i // n) * (n + 1) + i % n + 1])


def cerca(h, hs, d=6):
    return any(bin(h ^ x).count("1") <= d for x in hs)


class Escritor:
    def __init__(self, out, con_filtro):
        self.out, self.con_filtro, self.log = out, con_filtro, {}

    def poner(self, parte, nombre, img_o_ruta, cajas_px=None, lineas=None):
        """cajas_px: [(clase, x0, y0, x1, y1)] en píxeles de la imagen final; lineas: etiquetas YOLO ya hechas."""
        di, dl = os.path.join(self.out, "images", parte), os.path.join(self.out, "labels", parte)
        os.makedirs(di, exist_ok=True)
        os.makedirs(dl, exist_ok=True)
        dst = os.path.join(di, nombre)
        if self.con_filtro or not isinstance(img_o_ruta, str):
            img = Image.open(img_o_ruta) if isinstance(img_o_ruta, str) else img_o_ruta
            img = img.convert("RGB")
            if self.con_filtro:
                img, hechos, _ = filtrar(img)
                self.log[f"{parte}/{nombre}"] = hechos
            img.save(dst, quality=95)
            w, h = img.size
        else:
            try:
                os.link(img_o_ruta, dst)
            except OSError:
                shutil.copy2(img_o_ruta, dst)
            with Image.open(dst) as im:
                w, h = im.size
        if lineas is None:
            lineas = [f"{CLASES.index(c)} {(x0 + x1) / 2 / w:.6f} {(y0 + y1) / 2 / h:.6f} {(x1 - x0) / w:.6f} {(y1 - y0) / h:.6f}"
                      for c, x0, y0, x1, y1 in cajas_px or []]
        open(os.path.join(dl, nombre[:-4] + ".txt"), "w").write("\n".join(lineas))
        return len(lineas)


def main(con_filtro):
    out = os.path.join(BASE, "dataset_yolo_v4f" if con_filtro else "dataset_yolo_v4")
    if os.path.exists(out):
        shutil.rmtree(out)
    esc, cuenta = Escritor(out, con_filtro), {}

    # 1) lo que ya tenía v3 (train, val, test)
    vistos = []
    for parte in ("train", "val", "test"):
        for f in sorted(os.listdir(os.path.join(V3, "images", parte))):
            ruta = os.path.join(V3, "images", parte, f)
            lineas = [x for x in open(os.path.join(V3, "labels", parte, f[:-4] + ".txt")).read().splitlines() if x.strip()]
            esc.poner(parte, f, ruta, lineas=lineas)
            if not f.startswith("v2_") or "_a" not in f[-8:]:
                with Image.open(ruta) as im:
                    vistos.append(dhash(im))
        cuenta[f"v3_{parte}"] = len(os.listdir(os.path.join(V3, "images", parte)))

    # 2) RDD2022 adicional (90 % entrenamiento, 10 % validación)
    carpeta = os.path.join(BASE, "rdd2022_mas", "images")
    lab = json.load(open(os.path.join(carpeta, "bounding_boxes.labels"), encoding="utf-8"))["boundingBoxes"]
    nombres = sorted(lab)
    random.Random(4).shuffle(nombres)
    dup = n_rdd = 0
    for k, f in enumerate(nombres):
        ruta = os.path.join(carpeta, f)
        if not os.path.exists(ruta):
            continue
        with Image.open(ruta) as im:
            h = dhash(im)
        if cerca(h, vistos):
            dup += 1
            continue
        vistos.append(h)
        cajas = [(UNIR.get(b["label"], b["label"]), b["x"], b["y"], b["x"] + b["width"], b["y"] + b["height"]) for b in lab[f]]
        esc.poner("val" if k % 10 == 0 else "train", "rdd_" + f, ruta, cajas)
        n_rdd += 1
    cuenta["rdd_mas"], cuenta["rdd_mas_casi_duplicadas"] = n_rdd, dup

    # 3) calle de Guadalajara revisada a mano (sin las instituciones reservadas)
    reservadas = set(json.load(open(os.path.join(BASE, "modelo", "campo_reservado.json")))["imagenes"])
    campo = json.load(open(os.path.join(BASE, "campo", "etiquetas_campo.json"), encoding="utf-8"))["boundingBoxes"]
    n_pos = n_neg = 0
    for f, bs in sorted(campo.items()):
        if f in reservadas:
            continue
        img = Image.open(os.path.join(BASE, "mapillary", "images", f)).convert("RGB")
        s = min(1.0, LADO_CAMPO / max(img.size))
        if s < 1:
            img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
        cajas = [(b["label"], b["x"] * s, b["y"] * s, (b["x"] + b["width"]) * s, (b["y"] + b["height"]) * s) for b in bs]
        esc.poner("train", "campo_" + f, img, cajas)
        n_pos += bool(cajas)
        n_neg += not cajas
    cuenta["campo_con_objetos"], cuenta["campo_negativos"] = n_pos, n_neg

    # 4) rejillas nuevas de la lámina 38
    mapa = json.load(open(os.path.join(BASE, "alcantarillas_hd", "laminas", "mapa.json"), encoding="utf-8"))
    estados = json.load(open(os.path.join(BASE, "alcantarillas_hd", "estados.json"), encoding="utf-8"))
    rec = {r["archivo"]: r for r in csv.DictReader(open(os.path.join(BASE, "alcantarillas_hd", "recortes.csv"), encoding="utf-8"))}
    n_alc = 0
    for i, cod in enumerate(estados.get("38", "")):
        f = mapa.get(f"38-{i}")
        if cod in ("t", "r") and f in rec:
            x0, y0, x1, y1 = json.loads(rec[f]["caja_en_recorte"])
            c = "alcantarilla_tapada" if cod == "t" else "alcantarilla_riesgo"
            esc.poner("train", "alc38_" + f, os.path.join(BASE, "alcantarillas_hd", "recortes", f), [(c, x0, y0, x1, y1)])
            n_alc += 1
    cuenta["alcantarillas_nuevas"] = n_alc

    with open(os.path.join(out, "datos.yaml"), "w", encoding="utf-8") as fh:
        fh.write(f"path: {out.replace(os.sep, '/')}\ntrain: images/train\nval: images/val\ntest: images/test\n")
        fh.write("names:\n" + "".join(f"  {i}: {c}\n" for i, c in enumerate(CLASES)))
    if con_filtro:
        from collections import Counter
        cuenta["filtros"] = dict(Counter(x for v in esc.log.values() for x in v) + Counter(sin_cambio=sum(not v for v in esc.log.values())))
        json.dump(esc.log, open(os.path.join(out, "filtros.json"), "w", encoding="utf-8"))
    for parte in ("train", "val", "test"):
        cuenta[parte] = len(os.listdir(os.path.join(out, "images", parte)))
    json.dump(cuenta, open(os.path.join(out, "resumen.json"), "w", encoding="utf-8"), indent=1)
    print(json.dumps(cuenta, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--filtro", action="store_true")
    main(ap.parse_args().filtro)
