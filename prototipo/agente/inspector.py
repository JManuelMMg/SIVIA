"""
Entorno Seguro GDL - Agente Inspector.

Corre el modelo de detección entrenado en Edge Impulse (MobileNetV2 SSD FPN-Lite 320x320,
exportado como TensorFlow Lite float32) sobre las imágenes de calle de cada institución.

Preprocesamiento igual que el impulso de Edge Impulse:
  - RGB, escala 0..1
  - "Fit longest axis": se reduce la imagen para que su lado mayor mida 320 px y se rellena
    de negro hasta 320 x 320, centrada.

Uso:
  python agente/inspector.py --modelo entrenamiento/modelo/modelo.lite
  python agente/inspector.py --modelo ... --imagenes entrenamiento/mapillary/images --evidencia 40

Salida: agente/salida/detecciones.json  {archivo: [{"label","score","x","y","w","h"}]} en píxeles
        de la imagen original; con --evidencia N, N imágenes anotadas en agente/salida/evidencia/.
"""
import argparse
import glob
import json
import os

import numpy as np
from PIL import Image, ImageDraw

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(BASE, "agente", "salida")
ETIQUETAS_2 = ["bache", "grieta_cocodrilo"]  # modelo de pavimento (v1, v2)
ETIQUETAS_7 = ["alcantarilla_riesgo", "alcantarilla_tapada", "bache", "grieta_cocodrilo",
               "rama_riesgo", "rama_sobre_cable", "tronco_inclinado"]  # modelo único (orden de Edge Impulse)
ETIQUETAS_5 = ["alcantarilla_riesgo", "alcantarilla_tapada", "arbol_riesgo", "bache",
               "grieta_cocodrilo"]  # modelo v2 (árboles unidos en una clase)
ETIQUETAS_4 = ["alcantarilla_riesgo", "alcantarilla_tapada", "arbol_riesgo",
               "dano_pavimento"]  # modelo v3 (bache y piel de cocodrilo unidos)
ETIQUETAS = ETIQUETAS_7
COLORES = {"bache": "red", "dano_pavimento": "red", "grieta_cocodrilo": "orange", "poste_electrico": "yellow", "cruce_peatonal": "lime",
           "alcantarilla_tapada": "cyan", "alcantarilla_riesgo": "magenta", "rama_riesgo": "green",
           "rama_sobre_cable": "green", "tronco_inclinado": "green", "arbol_riesgo": "green"}
N = 320


def letterbox(img):
    w, h = img.size
    s = N / max(w, h)
    nw, nh = round(w * s), round(h * s)
    canvas = Image.new("RGB", (N, N))
    ox, oy = (N - nw) // 2, (N - nh) // 2
    canvas.paste(img.resize((nw, nh), Image.LANCZOS), (ox, oy))
    return canvas, s, ox, oy


class DetectorYOLO:
    """Detector YOLO entrenado en local (Ultralytics) y exportado a ONNX. Misma salida que Detector:
    lista de {"label","score","x","y","w","h"} en píxeles de la imagen original."""

    def __init__(self, path, minimo=0.25, iou=0.5):
        import ast
        import onnxruntime as ort
        self.ses = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
        self.entrada = self.ses.get_inputs()[0]
        self.n = int(self.entrada.shape[2])
        meta = self.ses.get_modelmeta().custom_metadata_map
        nombres = ast.literal_eval(meta["names"]) if "names" in meta else dict(enumerate(ETIQUETAS_4))
        self.etiquetas = [nombres[i] for i in sorted(nombres)]
        self.minimo, self.iou = minimo, iou
        # Umbral por clase calibrado en evaluar_yolo.py (archivo junto al modelo). En campo nunca baja
        # de `minimo`: las imágenes de calle son más variadas que las de prueba.
        sidecar = path[:-5] + ".umbrales.json"
        cfg = json.load(open(sidecar, encoding="utf-8")) if os.path.exists(sidecar) else {}
        u = cfg.get("umbrales_campo") or cfg.get("umbrales", {})
        self.umbrales = {k: max(minimo, u.get(k, 0.5)) for k in self.etiquetas}
        self.filtro = bool(cfg.get("filtro"))  # el modelo se entrenó con agente/filtros.py

    def __call__(self, img):
        img = img.convert("RGB")
        if self.filtro:
            try:
                from agente.filtros import filtrar
            except ImportError:  # ejecutado como script desde agente/
                from filtros import filtrar
            img = filtrar(img)[0]
        w, h = img.size
        s = self.n / max(w, h)
        nw, nh = round(w * s), round(h * s)
        lienzo = Image.new("RGB", (self.n, self.n), (114, 114, 114))
        ox, oy = (self.n - nw) // 2, (self.n - nh) // 2
        lienzo.paste(img.resize((nw, nh), Image.BILINEAR), (ox, oy))
        x = (np.asarray(lienzo, dtype=np.float32) / 255.0).transpose(2, 0, 1)[None]
        out = self.ses.run(None, {self.entrada.name: x})[0][0].T  # (anclas, 4 + clases)
        puntajes = out[:, 4:]
        clase = puntajes.argmax(1)
        conf = puntajes[np.arange(len(clase)), clase]
        m = conf >= self.minimo
        cajas, clase, conf = out[m, :4], clase[m], conf[m]
        xyxy = np.stack([cajas[:, 0] - cajas[:, 2] / 2, cajas[:, 1] - cajas[:, 3] / 2,
                         cajas[:, 0] + cajas[:, 2] / 2, cajas[:, 1] + cajas[:, 3] / 2], 1)
        res = []
        for c in np.unique(clase):
            idx = np.where(clase == c)[0]
            idx = idx[conf[idx].argsort()[::-1]]
            while len(idx):
                i, idx = idx[0], idx[1:]
                a = xyxy[i]
                x0, y0, x1, y1 = (a[0] - ox) / s, (a[1] - oy) / s, (a[2] - ox) / s, (a[3] - oy) / s
                k = self.etiquetas[int(c)]
                res.append({"label": k, "score": round(float(conf[i]), 3), "u": self.umbrales[k],
                            "x": round(max(0, x0)), "y": round(max(0, y0)), "w": round(x1 - x0), "h": round(y1 - y0)})
                if len(idx):
                    b = xyxy[idx]
                    inter = (np.clip(np.minimum(a[2], b[:, 2]) - np.maximum(a[0], b[:, 0]), 0, None)
                             * np.clip(np.minimum(a[3], b[:, 3]) - np.maximum(a[1], b[:, 1]), 0, None))
                    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1]) - inter
                    idx = idx[inter / np.maximum(union, 1e-6) < self.iou]
        return res



def confiable(d, w, h):
    """Criterio único para mostrar o reportar una detección (tablero, cámara, coordinador).
    YOLO: umbral calibrado por clase ("u"); el daño de pavimento además debe estar bajo el horizonte.
    FOMO (modelo anterior): alcantarillas >= 0.6; lo demás >= 0.8 y en la mitad baja."""
    cy = (d["y"] + d["h"] / 2) / h
    if "u" in d:
        return d["score"] >= d["u"] and (d["label"] != "dano_pavimento" or cy > 0.4)
    return (d["label"].startswith("alcantarilla") and d["score"] >= 0.6) or (d["score"] >= 0.8 and cy > 0.5)


def crear_detector(path):
    """Elige el motor según el archivo: .onnx (YOLO local) o .lite (Edge Impulse)."""
    return DetectorYOLO(path) if path.lower().endswith(".onnx") else Detector(path)


class Detector:
    def __init__(self, path):
        from ai_edge_litert.interpreter import Interpreter
        self.it = Interpreter(model_path=path)
        self.it.allocate_tensors()
        self.inp = self.it.get_input_details()[0]
        self.outs = self.it.get_output_details()
        global ETIQUETAS, N
        N = int(self.inp["shape"][1])  # 320 en Edge Impulse; los modelos locales pueden usar más resolución
        canales = self.outs[0]["shape"][-1]
        if len(self.outs) == 1 and canales in (3, 5, 6, 8):
            ETIQUETAS = {3: ETIQUETAS_2, 5: ETIQUETAS_4, 6: ETIQUETAS_5, 8: ETIQUETAS_7}[canales]

    def __call__(self, img):
        box_img, s, ox, oy = letterbox(img.convert("RGB"))
        x = np.asarray(box_img, dtype=np.float32)[None] / 255.0
        if self.inp["dtype"] != np.float32:  # modelo cuantizado
            esc, cero = self.inp["quantization"]
            x = (x / esc + cero).astype(self.inp["dtype"])
        self.it.set_tensor(self.inp["index"], x)
        self.it.invoke()
        outs = [self.it.get_tensor(o["index"]) for o in self.outs]
        if len(outs) == 1 and outs[0].ndim == 4:
            return self._fomo(outs[0], s, ox, oy)
        boxes = next(o for o in outs if o.ndim == 3 and o.shape[-1] == 4)[0]
        planos = [o[0] for o in outs if o.ndim == 2]
        # los puntajes tienen decimales; las clases son enteras. Si no se distinguen, se usa
        # el orden estándar de TFLite Detection PostProcess: clases y luego puntajes.
        con_decimales = [p for p in planos if not np.allclose(p, np.round(p))]
        if len(con_decimales) == 1:
            scores = con_decimales[0]
            clases = next(p for p in planos if p is not scores)
        else:
            clases, scores = planos[0], planos[1]
        res = []
        for b, c, sc in zip(boxes, clases, scores):
            ymin, xmin, ymax, xmax = (float(v) * N for v in b)
            x0, y0 = (xmin - ox) / s, (ymin - oy) / s
            x1, y1 = (xmax - ox) / s, (ymax - oy) / s
            res.append({"label": ETIQUETAS[int(c)] if int(c) < len(ETIQUETAS) else str(int(c)),
                        "score": round(float(sc), 3), "x": round(max(0, x0)), "y": round(max(0, y0)),
                        "w": round(x1 - x0), "h": round(y1 - y0)})
        return res


    def pavimento(self, img, banda=(0.50, 0.86), cortes=((0.08, 0.54), (0.46, 0.92))):
        """Imágenes de calle (cámara de auto): analiza solo la franja del pavimento, partida en dos
        recortes, para que los baches no se pierdan al reducir la escena completa a 320 px.
        La banda omite el cielo y el cofre del auto. Devuelve cajas en píxeles de la imagen completa."""
        img = img.convert("RGB")
        w, h = img.size
        y0, y1 = int(banda[0] * h), int(banda[1] * h)
        res = []
        for fx0, fx1 in cortes:
            x0, x1 = int(fx0 * w), int(fx1 * w)
            for r in self(img.crop((x0, y0, x1, y1))):
                r = dict(r, x=r["x"] + x0, y=r["y"] + y0)
                # evitar duplicados en la zona donde se traslapan los recortes
                if not any(q["label"] == r["label"] and abs(q["x"] - r["x"]) < 40 and abs(q["y"] - r["y"]) < 40
                           for q in res):
                    res.append(r)
        return res

    def _fomo(self, out, s, ox, oy, minimo=0.3):
        """FOMO: mapa [1, G, G, C+1] (índice 0 = fondo). Se agrupan celdas vecinas de la misma
        clase (componentes conexos) y cada grupo es un objeto con su caja y su centro."""
        o = self.outs[0]
        mapa = out[0].astype(np.float32)
        if o["dtype"] != np.float32:
            esc, cero = o["quantization"]
            mapa = (mapa - cero) * esc
        g = mapa.shape[0]
        celda = N / g
        clase = mapa.argmax(-1)
        prob = mapa.max(-1)
        visto = np.zeros_like(clase, dtype=bool)
        res = []
        for i in range(g):
            for j in range(g):
                c = clase[i, j]
                if c == 0 or visto[i, j] or prob[i, j] < minimo:
                    continue
                pila, celdas = [(i, j)], []
                visto[i, j] = True
                while pila:
                    a, b = pila.pop()
                    celdas.append((a, b))
                    for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        na, nb = a + da, b + db
                        if 0 <= na < g and 0 <= nb < g and not visto[na, nb] and clase[na, nb] == c \
                                and prob[na, nb] >= minimo:
                            visto[na, nb] = True
                            pila.append((na, nb))
                filas = [p[0] for p in celdas]
                cols = [p[1] for p in celdas]
                x0, x1 = min(cols) * celda, (max(cols) + 1) * celda
                y0, y1 = min(filas) * celda, (max(filas) + 1) * celda
                ox0, oy0 = (x0 - ox) / s, (y0 - oy) / s
                ox1, oy1 = (x1 - ox) / s, (y1 - oy) / s
                res.append({"label": ETIQUETAS[c - 1] if c - 1 < len(ETIQUETAS) else str(int(c)),
                            "score": round(float(max(prob[a, b] for a, b in celdas)), 3),
                            "x": round(max(0, ox0)), "y": round(max(0, oy0)),
                            "w": round(ox1 - ox0), "h": round(oy1 - oy0)})
        return res


DetectorYOLO.pavimento = Detector.pavimento  # mismo análisis por franja de pavimento


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", required=True)
    ap.add_argument("--imagenes", default=os.path.join(BASE, "entrenamiento", "mapillary", "images"))
    ap.add_argument("--umbral-guardar", type=float, default=0.3)
    ap.add_argument("--evidencia", type=int, default=0, help="guardar N imágenes anotadas")
    ap.add_argument("--salida", default=os.path.join(SALIDA, "detecciones.json"))
    ap.add_argument("--mixto", action="store_true",
                    help="escena completa (alcantarillas, árboles) + franja de pavimento (baches)")
    ap.add_argument("--calle", action="store_true",
                    help="imágenes de calle: analizar solo la franja del pavimento en dos recortes")
    ap.add_argument("--mapillary", default=os.path.join(BASE, "entrenamiento", "mapillary", "images",
                                                         "bounding_boxes.labels"),
                    help="etiquetas de Mapillary para postes y cruces ('' para no usarlas)")
    a = ap.parse_args()

    det = crear_detector(a.modelo)
    archivos = sorted(glob.glob(os.path.join(a.imagenes, "*.jpg")))
    salida, anotadas = {}, 0
    os.makedirs(os.path.join(SALIDA, "evidencia"), exist_ok=True)
    for k, f in enumerate(archivos, 1):
        img = Image.open(f)
        if a.mixto:
            crudo = det(img)
            crudo += [r for r in det.pavimento(img)
                      if not any(q["label"] == r["label"] and abs(q["x"] - r["x"]) < 60 for q in crudo)]
        else:
            crudo = det.pavimento(img) if a.calle else det(img)
        d = [r for r in crudo if r["score"] >= a.umbral_guardar]
        salida[os.path.basename(f)] = d
        if a.evidencia and anotadas < a.evidencia and any(r["score"] >= 0.5 for r in d):
            im = img.convert("RGB")
            dr = ImageDraw.Draw(im)
            for r in d:
                if r["score"] >= 0.5:
                    dr.rectangle([r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"]],
                                 outline=COLORES.get(r["label"], "white"), width=6)
                    dr.text((r["x"] + 6, r["y"] + 6), f"{r['label']} {r['score']:.2f}", fill=COLORES.get(r["label"], "white"))
            im.save(os.path.join(SALIDA, "evidencia", os.path.basename(f)), quality=88)
            anotadas += 1
        if k % 100 == 0 or k == len(archivos):
            print(f"  {k}/{len(archivos)} imágenes", flush=True)
    if a.mapillary:
        # Postes eléctricos y cruces peatonales: detecciones que Mapillary ya hace sobre cada imagen
        # (se usan las mismas reglas de limpieza que en entrenamiento/preparar_mapillary_ei.py)
        with open(a.mapillary, encoding="utf-8") as fh:
            mly = json.load(fh)["boundingBoxes"]
        agregadas = 0
        for nombre, cajas in mly.items():
            if nombre not in salida:
                continue
            for b in cajas:
                if b["label"] in ("poste_electrico", "cruce_peatonal") and min(b["width"], b["height"]) >= 48:
                    salida[nombre].append({"label": b["label"], "score": 0.9, "x": b["x"], "y": b["y"],
                                           "w": b["width"], "h": b["height"], "fuente": "mapillary"})
                    agregadas += 1
        print(f"Detecciones de Mapillary agregadas: {agregadas}")
    with open(a.salida, "w", encoding="utf-8") as fh:
        json.dump(salida, fh)
    from collections import Counter
    c = Counter(r["label"] for v in salida.values() for r in v if r["score"] >= 0.5)
    print(f"Detecciones con confianza >= 0.5: {dict(c)}")


if __name__ == "__main__":
    main()
