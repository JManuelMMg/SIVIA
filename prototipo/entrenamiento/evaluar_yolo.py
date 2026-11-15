"""
Evalúa el detector YOLO local con el mismo criterio que evaluar_modelo.py (centro dentro de la caja real,
clases de pavimento unidas) y sobre las mismas imágenes de prueba no vistas por el modelo v1.
Además barre el umbral de confianza por clase y elige el menor umbral con precisión >= META.

Uso:  .venv_yolo/Scripts/python evaluar_yolo.py modelo/yolo/v3_yolo11s/weights/best.pt
Salida: modelo/evaluacion_yolo.json (por clase con umbral 0.5, curva de umbrales y umbrales elegidos)
"""
import json
import os
import sys
from collections import defaultdict

from PIL import Image
from ultralytics import YOLO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agente.filtros import filtrar  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
TEST = os.path.join(BASE, "dataset_v2", "test")
UNIR = {"bache": "dano_pavimento", "grieta_cocodrilo": "dano_pavimento"}
META = 0.9
IMGSZ = int(os.environ.get("IMGSZ", 640))


def emparejar(dets, cajas, umbral_por_clase):
    """dets: [(label, score, cx, cy)]; devuelve tp, fp, fn por clase."""
    tp, fp, fn = defaultdict(int), defaultdict(int), defaultdict(int)
    usadas = set()
    for k, sc, cx, cy in sorted(dets, key=lambda d: -d[1]):
        if sc < umbral_por_clase.get(k, 0.5):
            continue
        hit = next((i for i, c in enumerate(cajas) if i not in usadas and c["label"] == k
                    and c["x"] <= cx <= c["x"] + c["width"] and c["y"] <= cy <= c["y"] + c["height"]), None)
        if hit is None:
            fp[k] += 1
        else:
            usadas.add(hit)
            tp[k] += 1
    for i, c in enumerate(cajas):
        if i not in usadas:
            fn[c["label"]] += 1
    return tp, fp, fn


def metricas(tp, fp, fn, clases):
    res = {}
    for k in clases:
        p = tp[k] / (tp[k] + fp[k]) if tp[k] + fp[k] else 0.0
        r = tp[k] / (tp[k] + fn[k]) if tp[k] + fn[k] else 0.0
        res[k] = {"precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0,
                  "tp": tp[k], "fp": fp[k], "fn": fn[k]}
    T, F, N = (sum(d[k] for k in clases) for d in (tp, fp, fn))
    p, r = (T / (T + F) if T + F else 0), (T / (T + N) if T + N else 0)
    res["general"] = {"precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0}
    return res


def main(pesos, filtro=False, archivo="evaluacion_yolo.json", prueba=None, clima=None, umbrales_fijos=None):
    """prueba: otra carpeta en formato Edge Impulse (se usan todas sus imágenes); clima: condición sintética que se
    aplica antes del filtro (clima_sintetico.py); umbrales_fijos: json con umbrales elegidos en otro conjunto
    (calibración), para no elegirlos sobre la misma prueba que se reporta."""
    modelo = YOLO(pesos)
    nombres = modelo.names
    test = os.path.join(BASE, prueba) if prueba else TEST
    gt = json.load(open(os.path.join(test, "bounding_boxes.labels"), encoding="utf-8"))["boundingBoxes"]
    vistas = set() if prueba else set(json.load(open(os.path.join(BASE, "modelo", "test_fuga_v1.json")))["vistas_por_v1"])
    gt = {f: [dict(b, label=UNIR.get(b["label"], b["label"])) for b in c] for f, c in gt.items() if f not in vistas}
    clases = sorted({b["label"] for c in gt.values() for b in c} | set(nombres.values()))
    preds = {}
    for f in gt:
        with Image.open(os.path.join(test, f)) as im:
            im = im.convert("RGB")
            if clima:
                from clima_sintetico import aplicar
                im = aplicar(im, clima, sum(map(ord, f)))
            im = filtrar(im)[0] if filtro else im
            r = modelo.predict(im, conf=0.05, imgsz=IMGSZ, verbose=False)[0]
        preds[f] = [(nombres[int(c)], float(s), float((b[0] + b[2]) / 2), float((b[1] + b[3]) / 2))
                    for b, c, s in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist())]

    def evaluar(umbrales):
        TP, FP, FN = defaultdict(int), defaultdict(int), defaultdict(int)
        for f, cajas in gt.items():
            tp, fp, fn = emparejar(preds[f], cajas, umbrales)
            for d, s in ((TP, tp), (FP, fp), (FN, fn)):
                for k, v in s.items():
                    d[k] += v
        return metricas(TP, FP, FN, clases)

    salida = {"n_imagenes": len(gt), "umbral_0.5": evaluar({k: 0.5 for k in clases}), "curva": {}, "umbral_elegido": {}}
    for k in clases:
        curva = []
        for u in [x / 20 for x in range(1, 20)]:
            m = evaluar({c: (u if c == k else 1.1) for c in clases})[k]
            curva.append({"umbral": u, **m})
        salida["curva"][k] = curva
        ok = [c for c in curva if c["precision"] >= META and c["tp"] >= 3]
        mejor = ok[0] if ok else max(curva, key=lambda c: c["f1"])
        salida["umbral_elegido"][k] = {"umbral": mejor["umbral"], "alcanza_meta": bool(ok)}
    salida["con_umbral_elegido"] = evaluar({k: v["umbral"] for k, v in salida["umbral_elegido"].items()})
    salida["condicion"] = {"prueba": prueba or "dataset_v2/test (no vistas por v1)", "clima": clima or "ninguno",
                           "filtro": filtro}
    if umbrales_fijos:
        u = json.load(open(os.path.join(BASE, umbrales_fijos), encoding="utf-8"))
        u = {k: v["umbral"] for k, v in u["umbral_elegido"].items()} if "umbral_elegido" in u else u["umbrales"]
        salida["umbrales_fijos"] = u
        salida["con_umbrales_fijos"] = evaluar({k: u.get(k, 0.5) for k in clases})
    json.dump(salida, open(os.path.join(BASE, "modelo", archivo), "w", encoding="utf-8"), indent=1)
    for titulo in ("umbral_0.5", "con_umbral_elegido") + (("con_umbrales_fijos",) if umbrales_fijos else ()):
        print(f"\n== {titulo} ({len(gt)} imágenes no vistas)")
        for k, v in salida[titulo].items():
            u = salida["umbral_elegido"].get(k, {}).get("umbral", "")
            print(f"  {k:<22} P {v['precision']:.2f}  R {v['recall']:.2f}  F1 {v['f1']:.2f}  {u}")


if __name__ == "__main__":
    # uso: evaluar_yolo.py pesos.pt [--filtro] [--salida X.json] [--prueba carpeta] [--clima lluvia] [--umbrales Y.json]
    arg = sys.argv[1:]
    op = lambda n, d=None: arg[arg.index(n) + 1] if n in arg else d  # noqa: E731
    main(arg[0], "--filtro" in arg, op("--salida", "evaluacion_yolo.json"), op("--prueba"), op("--clima"), op("--umbrales"))
