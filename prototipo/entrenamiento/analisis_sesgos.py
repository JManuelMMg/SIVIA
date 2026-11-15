"""
Análisis de sesgos del detector sobre las imágenes de prueba no vistas: ¿acierta igual según el tamaño del objeto,
la luz de la imagen y la fuente? ¿Cuántas falsas alarmas da en imágenes sin objetos?
Usa el mismo criterio de acierto que evaluar_yolo.py (centro dentro de la caja real, misma clase) y los umbrales
de un archivo de evaluación o de umbrales.

Uso:    .venv_yolo/Scripts/python analisis_sesgos.py pesos.pt umbrales.json [--filtro] [--salida X.json]
Salida: modelo/<X.json> con exhaustividad por grupo y falsas alarmas por imagen.
"""
import json
import os
import sys
from collections import defaultdict

from PIL import Image
from ultralytics import YOLO

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE))
from agente.filtros import filtrar, medir  # noqa: E402

TEST = os.path.join(BASE, "dataset_v2", "test")
UNIR = {"bache": "dano_pavimento", "grieta_cocodrilo": "dano_pavimento"}


def grupo_tamano(area):
    return "pequeño (<1 %)" if area < 0.01 else ("mediano (1-5 %)" if area < 0.05 else "grande (>5 %)")


def grupo_luz(b):
    return "oscura (<85)" if b < 85 else ("clara (>150)" if b > 150 else "normal")


def fuente(f):
    for k in ("rdd", "alcantarilla", "arbol", "negativo"):
        if f"v2_{k}" in f:
            return k
    return "otra"


if __name__ == "__main__":
    arg = sys.argv[1:]
    pesos, umb_path = arg[0], arg[1]
    filtro = "--filtro" in arg
    salida = arg[arg.index("--salida") + 1] if "--salida" in arg else "sesgos.json"
    u = json.load(open(os.path.join(BASE, umb_path), encoding="utf-8"))
    umb = {k: v["umbral"] for k, v in u["umbral_elegido"].items()} if "umbral_elegido" in u else u["umbrales"]
    m = YOLO(os.path.join(BASE, pesos))
    gt = json.load(open(os.path.join(TEST, "bounding_boxes.labels"), encoding="utf-8"))["boundingBoxes"]
    vistas = set(json.load(open(os.path.join(BASE, "modelo", "test_fuga_v1.json")))["vistas_por_v1"])
    rec = defaultdict(lambda: [0, 0])  # grupo -> [aciertos, total]
    fa = defaultdict(lambda: [0, 0])   # grupo -> [falsas alarmas, imágenes]
    for f, cajas in gt.items():
        if f in vistas:
            continue
        with Image.open(os.path.join(TEST, f)) as im:
            im = im.convert("RGB")
            luz = grupo_luz(medir(im)["brillo"])
            w, h = im.size
            if filtro:
                im = filtrar(im)[0]
            r = m.predict(im, conf=0.05, verbose=False)[0]
        pred = [(m.names[int(c)], float(s), (b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
                for b, c, s in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist())]
        pred = [p for p in pred if p[1] >= umb.get(p[0], 0.5)]
        usadas, n_fp = set(), 0
        for k, s, cx, cy in sorted(pred, key=lambda p: -p[1]):
            hit = next((i for i, c in enumerate(cajas) if i not in usadas and UNIR.get(c["label"], c["label"]) == k
                        and c["x"] <= cx <= c["x"] + c["width"] and c["y"] <= cy <= c["y"] + c["height"]), None)
            if hit is None:
                n_fp += 1
            else:
                usadas.add(hit)
        for i, c in enumerate(cajas):
            clase = UNIR.get(c["label"], c["label"])
            for g in (f"{clase} · {grupo_tamano(c['width'] * c['height'] / (w * h))}", f"luz {luz} · {clase}",
                      f"fuente {fuente(f)}"):
                rec[g][0] += i in usadas
                rec[g][1] += 1
        for g in (f"luz {luz}", f"fuente {fuente(f)}", "sin objetos" if not cajas else "con objetos"):
            fa[g][0] += n_fp
            fa[g][1] += 1
    out = {"exhaustividad": {g: {"aciertos": a, "total": t, "valor": round(a / t, 3)} for g, (a, t) in sorted(rec.items())},
           "falsas_alarmas_por_imagen": {g: {"falsas": a, "imagenes": t, "valor": round(a / t, 3)}
                                         for g, (a, t) in sorted(fa.items())},
           "umbrales": umb, "filtro": filtro}
    json.dump(out, open(os.path.join(BASE, "modelo", salida), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("Exhaustividad por grupo (aciertos/total):")
    for g, v in out["exhaustividad"].items():
        print(f"  {g:<45} {v['valor']:.2f}  ({v['aciertos']}/{v['total']})")
    print("Falsas alarmas por imagen:")
    for g, v in out["falsas_alarmas_por_imagen"].items():
        print(f"  {g:<45} {v['valor']:.2f}  ({v['falsas']}/{v['imagenes']})")
