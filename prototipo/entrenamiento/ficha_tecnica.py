"""
Ficha técnica del detector (v9 integrado) (entregable técnico): entregables/Ficha_Tecnica_Modelo_v9.docx + figuras.

Lee: dataset_v2/resumen.json, modelo/evaluacion.json, modelo/evaluacion_yolo.json,
     modelo/yolo/v3_yolo11s/results.csv, modelo/entorno_seguro_v3_yolo11s.umbrales.json
Uso: python ficha_tecnica.py
"""
import json
import os
import re

import docx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.shared import Cm, Pt, RGBColor  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(BASE))
FIG = os.path.join(RAIZ, "entregables", "figuras")
OUT = os.path.join(RAIZ, "entregables", "Ficha_Tecnica_Modelo_v9.docx")
N = "SIVIA"
os.makedirs(FIG, exist_ok=True)

res = json.load(open(os.path.join(BASE, "dataset_v2", "resumen.json"), encoding="utf-8"))
ev_todo = json.load(open(os.path.join(BASE, "modelo", "evaluacion.json"), encoding="utf-8"))
ev, ev_c, NIMG = ev_todo["limpio"], ev_todo["completo"], ev_todo["n_imagenes"]
V1, V2A, V2 = "entorno_seguro_7clases.lite", "entorno_seguro_v2a_lr001.lite", "entorno_seguro_v2b_lr005.lite"
CL = ["alcantarilla_riesgo", "alcantarilla_tapada", "arbol_riesgo", "bache", "grieta_cocodrilo"]
NOM = {"alcantarilla_riesgo": "Alcantarilla obstruida o dañada", "alcantarilla_tapada": "Rejilla en buen estado",
       "arbol_riesgo": "Árbol de riesgo", "bache": "Bache", "grieta_cocodrilo": "Piel de cocodrilo",
       "general": "General"}
# Conteo del dataset anterior (activo en Edge Impulse antes del cambio)
ANTES = {"alcantarilla_riesgo": 86, "alcantarilla_tapada": 290, "arbol_riesgo": 126, "bache": 1391,
         "grieta_cocodrilo": 309}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.5, "axes.spines.top": False,
                     "axes.spines.right": False})
GRIS, VERDE, AZUL = "#9aa3a0", "#1f6f5c", "#2f6db5"

# 1) balance antes / después
fig, ax = plt.subplots(figsize=(6.2, 2.6), dpi=200)
x = range(len(CL))
ax.bar([i - .2 for i in x], [ANTES[c] for c in CL], .4, color=GRIS, label="Dataset v1 (entrenamiento)")
ax.bar([i + .2 for i in x], [res["objetos_train"].get(c, 0) for c in CL], .4, color=VERDE,
       label="Dataset v2 (entrenamiento, con aumentos)")
ax.set_xticks(list(x), [NOM[c] for c in CL])
ax.set_ylabel("objetos etiquetados")
ax.legend(frameon=False, fontsize=7.5)
fig.savefig(os.path.join(FIG, "modelo_balance.png"), bbox_inches="tight")
plt.close(fig)

# 2) ejemplos de aumento (original y dos variantes rotadas con sus cajas); si ya no está dataset_v2/train,
#    se conserva la figura generada antes
LAB_V2 = os.path.join(BASE, "dataset_v2", "train", "bounding_boxes.labels")
if os.path.exists(LAB_V2):
    lab = json.load(open(LAB_V2, encoding="utf-8"))["boundingBoxes"]
    filas = []
    for pref in ("v2_arbol_recorte", "v2_alcantarilla"):
        base = next(f[:-4] for f in sorted(lab) if f.startswith(pref) and not re.search(r"_a\d+\.jpg$", f) and f"{f[:-4]}_a1.jpg" in lab)
        filas.append([base + ".jpg", base + "_a0.jpg", base + "_a1.jpg"])
    T = 300
    hoja = Image.new("RGB", (3 * T + 20, len(filas) * T + 10), "white")
    for r, fila in enumerate(filas):
        for c, f in enumerate(fila):
            im = Image.open(os.path.join(BASE, "dataset_v2", "train", f)).convert("RGB")
            d = ImageDraw.Draw(im)
            for b in lab[f]:
                d.rectangle([b["x"], b["y"], b["x"] + b["width"], b["y"] + b["height"]], outline=(255, 210, 0), width=4)
            im.thumbnail((T, T))
            hoja.paste(im, (c * (T + 10), r * (T + 10)))
    hoja.save(os.path.join(FIG, "modelo_aumentos.jpg"), quality=88)

# 3) curva de entrenamiento (si el registro trae métricas por época)
curva = []
log = os.path.join(BASE, "modelo", "log_entrenamiento_v2b.txt")
if os.path.exists(log):
    for linea in open(log, encoding="utf-8"):
        m = re.match(r"\s*(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*$", linea)
        if m and (not curva or int(m.group(1)) + 1 != curva[-1][0]):
            curva.append((int(m.group(1)) + 1, float(m.group(3)), float(m.group(6))))
if curva:
    fig, ax = plt.subplots(figsize=(6.2, 2.4), dpi=200)
    ax.plot([c[0] for c in curva], [c[2] for c in curva], color=VERDE, lw=1.6, label="F1 de validación")
    ax2 = ax.twinx()
    ax2.plot([c[0] for c in curva], [c[1] for c in curva], color=GRIS, lw=1.2, label="pérdida de validación")
    ax.set_xlabel("época")
    ax.set_ylabel("F1")
    ax2.set_ylabel("pérdida")
    ax2.spines["top"].set_visible(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=7.5, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2)
    fig.savefig(os.path.join(FIG, "modelo_curva.png"), bbox_inches="tight")
    plt.close(fig)

# 4) F1 por clase v1 vs v2
fig, ax = plt.subplots(figsize=(6.2, 2.6), dpi=200)
cls = CL + ["general"]
f1 = lambda m, c: ev.get(m, {}).get(c, {}).get("f1", 0)  # noqa: E731
ax.bar([i - .2 for i in range(len(cls))], [f1(V1, c) for c in cls], .4, color=GRIS, label="Modelo v1")
ax.bar([i + .2 for i in range(len(cls))], [f1(V2, c) for c in cls], .4, color=AZUL, label="Modelo v2")
for i, c in enumerate(cls):
    ax.text(i + .2, f1(V2, c) + .01, f"{f1(V2, c):.2f}", ha="center", fontsize=7)
ax.set_xticks(range(len(cls)), [NOM[c].replace(" de ", "\nde ").replace(" con ", "\ncon ") for c in cls], fontsize=7.5)
ax.set_ylabel(f"F1 ({NIMG['limpio']} imágenes no vistas)")
ax.set_ylim(0, 1)
ax.legend(frameon=False, fontsize=7.5)
fig.savefig(os.path.join(FIG, "modelo_f1.png"), bbox_inches="tight")
plt.close(fig)

# ------------------------------------------------------------------------------- documento
d = docx.Document()
st = d.styles["Normal"]
st.font.name, st.font.size = "Calibri", Pt(10.5)
for s in d.sections:
    s.left_margin = s.right_margin = Cm(2.2)


def h(t, n=1):
    p = d.add_heading(t, level=n)
    for r in p.runs:
        r.font.color.rgb = RGBColor(0x1f, 0x3d, 0x35)


def p(t, it=False, size=None):
    q = d.add_paragraph()
    r = q.add_run(t)
    r.italic = it
    if size:
        r.font.size = Pt(size)
    return q


def fig_(archivo, pie, ancho=15.5):
    if not os.path.exists(os.path.join(FIG, archivo)):
        return
    q = d.add_paragraph()
    q.alignment = WD_ALIGN_PARAGRAPH.CENTER
    q.add_run().add_picture(os.path.join(FIG, archivo), width=Cm(ancho))
    p(pie, it=True, size=8.5)


def tabla(filas, anchos=None):
    t = d.add_table(rows=len(filas), cols=len(filas[0]))
    t.style = "Light Grid Accent 1"
    for i, f in enumerate(filas):
        for j, v in enumerate(f):
            c = t.cell(i, j)
            c.text = str(v)
            for r in c.paragraphs[0].runs:
                r.font.size, r.bold = Pt(9), i == 0
    d.add_paragraph()


# --- v3: clases de pavimento unidas, FOMO 4 clases y YOLO11s local ---
import csv  # noqa: E402
evu = ev_todo["limpio_unido"]
yo = json.load(open(os.path.join(BASE, "modelo", "evaluacion_yolo.json"), encoding="utf-8"))
umb = json.load(open(os.path.join(BASE, "modelo", "entorno_seguro_v3_yolo11s.umbrales.json"), encoding="utf-8"))
y4 = json.load(open(os.path.join(BASE, "modelo", "evaluacion_yolo_v4.json"), encoding="utf-8"))
y4f = json.load(open(os.path.join(BASE, "modelo", "evaluacion_yolo_v4f.json"), encoding="utf-8"))
umb4 = json.load(open(os.path.join(BASE, "modelo", "entorno_seguro_v4f_yolo11s.umbrales.json"), encoding="utf-8"))
filt = json.load(open(os.path.join(BASE, "dataset_yolo_v4f", "resumen.json"), encoding="utf-8"))
CL4 = ["alcantarilla_riesgo", "alcantarilla_tapada", "arbol_riesgo", "dano_pavimento"]
NOM.update({"dano_pavimento": "Daño de pavimento (bache + piel de cocodrilo)"})
V3F = "entorno_seguro_v3_fomo4.lite"
with open(os.path.join(BASE, "modelo", "yolo", "v3_yolo11s", "results.csv"), encoding="utf-8") as fh:
    yres = [{k.strip(): float(v) for k, v in r.items()} for r in csv.DictReader(fh)]
fig, ax = plt.subplots(figsize=(6.2, 2.4), dpi=200)
ep = [r["epoch"] for r in yres]
ax.plot(ep, [r["metrics/mAP50(B)"] for r in yres], color="#1f6f5c", lw=1.6, label="mAP50 (validación)")
ax.plot(ep, [r["metrics/precision(B)"] for r in yres], color="#c46b2d", lw=1, label="Precisión")
ax.plot(ep, [r["metrics/recall(B)"] for r in yres], color="#5a6fb0", lw=1, label="Exhaustividad")
ax.set_xlabel("Época")
ax.set_ylim(0, 1)
ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, frameon=False)
fig.savefig(os.path.join(FIG, "modelo_yolo_curva.png"), bbox_inches="tight")
plt.close(fig)
fig, ax = plt.subplots(figsize=(6.2, 2.6), dpi=200)
mods = [("FOMO v1", evu["entorno_seguro_7clases.lite"]), ("FOMO v2", evu[V2]), ("FOMO v3 (4 clases)", evu[V3F]),
        ("YOLO11s v3", yo["con_umbral_elegido"])]
xs = range(len(CL4) + 1)
for i, (nom, r) in enumerate(mods):
    ax.bar([x + (i - 1.5) * 0.2 for x in xs], [r.get(c, {}).get("f1", 0) for c in CL4 + ["general"]], 0.2,
           label=nom, color=["#b9c4c0", "#8fa69e", "#5f8478", "#1f6f5c"][i])
ax.set_xticks(list(xs))
ax.set_xticklabels(["Alcantarilla\nobstruida", "Rejilla en\nbuen estado", "Árbol\nde riesgo", "Daño de\npavimento",
                    "General"])
ax.set_ylabel(f"F1 ({yo['n_imagenes']} imágenes no vistas)")
ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=4, frameon=False)
fig.savefig(os.path.join(FIG, "modelo_f1_v3.png"), bbox_inches="tight")
plt.close(fig)

# Identificador gráfico del Hackathon en el encabezado de cada página (lo pide el kit del reto)
_logo = os.path.join(RAIZ, "entregables", "figuras", "logos", "hackathon_jalisco_2026.jpg")
if os.path.exists(_logo):
    _hp = d.sections[0].header.paragraphs[0]
    _hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _hp.add_run().add_picture(_logo, width=Cm(8))

ttl = d.add_heading(f"{N}: ficha técnica del detector v9", 0)
p("Hackathon Jalisco Internacional 2026 · Reto 01 Ciudades Inteligentes · Entregable técnico", it=True)
p("Modelo en uso: YOLO11s v9 (Ultralytics), afinado desde la v5 con 515 fotos recientes de Guadalajara revisadas a mano (v8) y 30 épocas más (v9); entrenado también con clima adverso y vistas de dron, con filtro adaptativo por imagen, entrada 640 x 640 px, 4 clases, ONNX "
  "(38 MB), entrenado en una laptop con GPU RTX 3050. Modelos anteriores: FOMO MobileNetV2 0.35 en Edge Impulse (studio.edgeimpulse.com/public/1161125).")

g1, g2 = ev[V1]["general"], ev.get(V2, {}).get("general", {})
f1c = lambda m, c: ev[m].get(c, {}).get("f1", 0)  # noqa: E731
h("Resumen")
gy, gf = yo["con_umbral_elegido"]["general"], evu["entorno_seguro_7clases.lite"]["general"]
meta_ok = [NOM[k].split(" (")[0].lower() for k, v in yo["umbral_elegido"].items() if v["alcanza_meta"]]
p(f"Tres versiones de FOMO en Edge Impulse se quedaron en un F1 de 0.29 a 0.33, aun después de limpiar, balancear y "
  f"rotar los datos. El límite era la arquitectura: FOMO marca puntos en una cuadrícula y no separa objetos largos. "
  f"Para la v3 se unieron bache y piel de cocodrilo en una clase de daño de pavimento (las dos van a Pavimentos) y se "
  f"entrenó un detector de cajas YOLO11s en local. Sobre las {yo['n_imagenes']} imágenes de prueba que ningún modelo "
  f"vio, el F1 general sube de {gf['f1']:.2f} a {gy['f1']:.2f} y la precisión de {gf['precision']:.2f} a "
  f"{gy['precision']:.2f}. Con el umbral calibrado por clase, la meta de 0.9 de precisión se cumple en "
  f"{' y '.join(meta_ok)}; en alcantarillas queda entre 0.69 y 0.75. La exhaustividad ({gy['recall']:.2f}) sigue "
  f"siendo el punto débil: el modelo acierta cuando marca, pero omite casos. La v4 (sección 6) agrega 1,961 imágenes de "
  f"pavimento, escenas de calle revisadas a mano y un filtro adaptativo por imagen: el F1 general sube a "
  f"{y4f['con_umbral_elegido']['general']['f1']:.2f} (precisión {y4f['con_umbral_elegido']['general']['precision']:.2f}) "
  f"y en calles reservadas la mitad de los candidatos resulta real. La v5 (sección 7) recalcula todo con umbrales "
  f"calibrados fuera de la prueba: F1 0.51 con precisión 0.86 en limpio, y mucho más robusta en lluvia, movimiento y "
  f"vista de dron (F1 de 0.06 a 0.41); en calles reservadas de Guadalajara, en cambio, 5 de 17 candidatos "
  f"fueron reales. La v8 (sección 7.1) parte de la v5 y suma 515 fotos recientes de calles de Guadalajara revisadas "
  f"a mano: en las mismas calles reservadas 11 de 18 candidatos fueron reales, y en laboratorio conserva la robustez "
  f"de la v5 (F1 0.46 en limpio, 0.43 en dron con precisión 0.92). La v9 (sección 7.2) sigue entrenando la v8 con los "
  f"mismos datos: acierta lo mismo en calle con menos falsas alarmas (11 de 16) y sube a F1 0.48 con precisión 0.85 "
  f"en limpio. Es el modelo integrado.")

h("Historia: del detector v1 al v2")
p(f"El detector v1 tenía 7 clases muy desbalanceadas (de 19 a 1,391 ejemplos), etiquetas sueltas y el aumento de datos "
  f"apagado. Para la versión 2 se rehízo el dataset completo: se revisaron 363 recortes de alcantarillas que no se habían "
  f"etiquetado, se bajaron 469 imágenes más de piel de cocodrilo de RDD2022, las tres clases de árbol se unieron en una "
  f"sola y cada clase escasa se amplió con rotaciones de 4 a 15 grados, espejo, cambios de luz y acercamiento. "
  f"Resultado: sobre {NIMG['limpio']} imágenes de prueba que ningún modelo vio al entrenar, el F1 general queda "
  f"prácticamente igual ({g1['f1']:.2f} en v1 y {g2.get('f1', 0):.2f} en v2). v2 empieza a detectar alcantarillas de "
  f"riesgo (F1 {f1c(V1, 'alcantarilla_riesgo'):.2f} a {f1c(V2, 'alcantarilla_riesgo'):.2f}) y mantiene las "
  f"rejillas en buen estado ({f1c(V2, 'alcantarilla_tapada'):.2f}). Ningún modelo distingue la piel de cocodrilo: la "
  f"confunde con bache. El cambio de fondo que sí funcionó es la limpieza y el balanceo de datos; lo que falta es "
  f"resolución y una clase de pavimento mejor definida (sección 5).")

h("1. Datos")
tabla([["Fuente", "Contenido", "Licencia"],
       ["RDD2022 (Arya et al., 2022)", f"{res['por_fuente'].get('rdd', 0) + res['por_fuente'].get('rdd_grieta', 0):,} "
        f"imágenes con baches y piel de cocodrilo; {res['por_fuente'].get('rdd_fondo', 0)} sin daño", "CC BY 4.0"],
       ["Alcantarillas de Guadalajara (Mapillary)", f"{res['por_fuente'].get('alcantarilla', 0)} recortes en su "
        f"resolución original (402-706 px), revisados uno por uno", "CC BY-SA 4.0"],
       ["Árboles de Guadalajara (Mapillary)", f"{res['por_fuente'].get('arbol', 0)} escenas y su recorte centrado",
        "CC BY-SA 4.0"],
       ["Negativos difíciles", f"{res['por_fuente'].get('negativo_calle', 0)} franjas altas de calles (cielo, "
        f"fachadas, postes)", "CC BY-SA 4.0"]])
fig_("modelo_balance.png", "Figura 1. Objetos por clase en entrenamiento, antes y después del balanceo.")

h("2. Preprocesamiento")
for t in [
    f"Limpieza: se quitaron {res['duplicados_quitados']} imágenes casi duplicadas (hash perceptual) y "
    f"{len(res['ilegibles'])} archivos dañados; se eliminaron etiquetas sueltas (poste_cableado, arbol, poste_inclinado).",
    "Máxima calidad: cada alcantarilla se toma de su recorte original en lugar del reducido a 320 px; todo se guarda "
    f"a {res['lado_max_px']} px de lado mayor con Lanczos y JPEG calidad 95. Edge Impulse lo reduce a 320 x 320 con "
    "el mismo método que usará la cámara.",
    "Árboles: además de la escena completa se usa un recorte centrado en el árbol, para que no se pierda al reducir.",
    "Separación sin fuga: 80/20 por imagen original antes de aumentar. Ninguna variante de una imagen de prueba "
    "entra al entrenamiento.",
    f"Balanceo por aumento: árboles x{4}, alcantarillas de riesgo x{5}, rejillas en buen estado x{2} (original más "
    "variantes). Baches y grietas no se aumentan porque ya tienen ejemplos suficientes.",
    f"Rotaciones: {res['rotacion_grados']['n']:,} variantes con giros entre {res['rotacion_grados']['min']} y "
    f"{res['rotacion_grados']['max']} grados (promedio {res['rotacion_grados']['media_abs']}). Después de girar se "
    "recorta el rectángulo interior para que no queden esquinas negras, y cada caja se recalcula; si un objeto "
    "queda cortado, la variante se descarta.",
    "Además: espejo horizontal, brillo, contraste y saturación de 0.75 a 1.25, desenfoque leve y acercamiento de "
    "0.85 a 1. En Edge Impulse se activó también su aumento de datos propio."]:
    d.add_paragraph(t, style="List Bullet")
fig_("modelo_aumentos.jpg", "Figura 2. Imagen original (izquierda) y dos variantes rotadas, con sus cajas recalculadas.",
     13)

h("3. Entrenamiento")
tabla([["Parámetro", "Valor"], ["Arquitectura", "FOMO, MobileNetV2 0.35"], ["Entrada", "320 x 320 px, RGB, fit longest axis"],
       ["Imágenes de entrenamiento", f"{res['imagenes']['train'] + res['imagenes']['train_aumentadas']:,} "
        f"({res['imagenes']['train_aumentadas']:,} aumentadas)"],
       ["Imágenes de prueba", f"{res['imagenes']['test']}"], ["Ciclos", "70"], ["Tasa de aprendizaje", "0.005"],
       ["Aumento en Edge Impulse", "activado"], ["Tiempo de entrenamiento", "unos 45 min en GPU T4 (plan gratuito, límite 1 h)"]])
p("Se hicieron tres corridas. La primera usó YOLO-Pro (xlarge, sin pesos preentrenados) y Edge Impulse la detuvo al "
  "pasar el límite de una hora. La segunda, FOMO con tasa 0.001 y 60 ciclos, terminó subentrenada: el F1 de validación "
  "seguía subiendo en la última época. La tercera, con tasa 0.005 y 70 ciclos, es la que se reporta como v2.")
fig_("modelo_curva.png", "Figura 3. F1 y pérdida de validación por época (registro de Edge Impulse).")

h("4. Resultados")
p(f"El conjunto de prueba v2 tiene {NIMG['completo']} imágenes. Al cruzarlo con los archivos que usó el modelo v1 se "
  f"encontró que {NIMG['completo'] - NIMG['limpio']} ya estaban en su entrenamiento, así que la comparación justa se hace "
  f"con las {NIMG['limpio']} restantes. Una detección es correcta si su centro cae dentro de una caja real de la misma "
  "clase, con umbral de confianza de 0.5.")
filas = [["Clase", "F1 v1", "F1 v2", "Precisión v2", "Exhaustividad v2"]]
for c in CL + ["general"]:
    a, b = ev[V1].get(c, {}), ev.get(V2, {}).get(c, {})
    filas.append([NOM[c], f"{a.get('f1', 0):.2f}", f"{b.get('f1', 0):.2f}", f"{b.get('precision', 0):.2f}",
                  f"{b.get('recall', 0):.2f}"])
tabla(filas)
fig_("modelo_f1.png", f"Figura 4. F1 por clase del modelo v1 y del v2 sobre las {NIMG['limpio']} imágenes no vistas.")
p(f"Con las {NIMG['completo']} imágenes completas el F1 general de v1 sube a {ev_c[V1]['general']['f1']:.2f}, por las "
  f"imágenes que ya conocía; v2 obtiene {ev_c[V2]['general']['f1']:.2f}. La corrida intermedia (tasa 0.001) tuvo "
  f"F1 {ev[V2A]['general']['f1']:.2f} con mayor precisión ({ev[V2A]['general']['precision']:.2f}) y menor exhaustividad.")

h("5. Versión 3: clases unidas y detector YOLO11s")
p("Se probaron dos cambios por separado. Primero, con la arquitectura FOMO, se reetiquetaron en Edge Impulse las "
  "muestras de bache y piel de cocodrilo como daño de pavimento y se volvió a entrenar (70 ciclos). El F1 general quedó "
  f"en {evu[V3F]['general']['f1']:.2f}: unir clases no bastó. Después se cambió la arquitectura a YOLO11s, con pesos "
  "preentrenados en COCO, entrenado en la GPU de la laptop del equipo porque el plan gratuito de Edge Impulse corta los "
  "trabajos a la hora.")
tabla([["Parámetro", "Valor"], ["Arquitectura", "YOLO11s (Ultralytics 8.4), detector de cajas"],
       ["Entrada", "640 x 640 px, relleno gris (letterbox)"],
       ["Datos", "dataset v2 con pavimento unido: 3,188 imágenes de entrenamiento, 349 de validación (15 % de las "
        "imágenes originales, sin variantes) y las mismas 592 de prueba"],
       ["Épocas", f"{len(yres)} (lote 8, AdamW, tasa coseno, precisión mixta)"],
       ["Aumentos", "rotación de hasta 10 grados, espejo, mosaico, cambios de color (además de las rotaciones del v2)"],
       ["Hardware y tiempo", "NVIDIA RTX 3050 Laptop 6 GB, unas 2 h 8 min"],
       ["Inferencia", "unos 0.1 s por imagen en el procesador (ONNX Runtime), sin GPU"]])
fig_("modelo_yolo_curva.png", "Figura 5. Precisión, exhaustividad y mAP50 en validación por época (YOLO11s).")
filas = [["Clase", "FOMO v1", "FOMO v2", "FOMO v3", "YOLO11s v3", "Precisión YOLO", "Exhaustividad YOLO"]]
for c in CL4 + ["general"]:
    y = yo["con_umbral_elegido"].get(c, {})
    filas.append([NOM.get(c, "General").split(" (")[0] if c != "general" else "General"]
                 + [f"{m.get(c, {}).get('f1', 0):.2f}" for _, m in mods]
                 + [f"{y.get('precision', 0):.2f}", f"{y.get('recall', 0):.2f}"])
tabla(filas)
fig_("modelo_f1_v3.png", f"Figura 6. F1 por clase de los cuatro modelos sobre las {yo['n_imagenes']} imágenes no vistas, "
     "con bache y piel de cocodrilo contados como una sola clase.")
p("Calibración del umbral. Para cada clase se barrió el umbral de confianza de 0.05 a 0.95 y se eligió el menor que "
  "diera una precisión de 0.9 o más (con al menos 3 aciertos); si ninguno la alcanzaba, el de mejor F1.")
filas = [["Clase", "Umbral (prueba)", "¿Alcanza 0.9?", "Umbral en campo"]]
for c in CL4:
    filas.append([NOM[c].split(" (")[0], f"{yo['umbral_elegido'][c]['umbral']:.2f}",
                  "sí" if yo["umbral_elegido"][c]["alcanza_meta"] else "no", f"{umb['umbrales_campo'][c]:.2f}"])
tabla(filas)
p("Prueba en campo. El modelo se corrió sobre las 1,130 imágenes de calle de Mapillary, que se parecen poco a las fotos "
  "de entrenamiento (tomadas de cerca). En una revisión visual de muestras, cerca de la mitad de las alcantarillas y del "
  "daño de pavimento eran reales; los falsos positivos fueron portones, pintura vial y tapas de registro. Con umbral 0.5 "
  "el modelo marcaba árboles sanos, mientras que los de confianza 0.8 o más mostraban ramas sobre cables. Por eso en "
  "campo se usan umbrales más estrictos (tabla anterior) y toda detección pasa por validación humana. Como referencia, "
  "el FOMO v1 había dejado 158 baches candidatos en las mismas imágenes, casi todos puntos sobre pavimento liso.")
p("Despliegue en el borde. El ONNX corre en el procesador de una laptop o de una computadora pequeña a bordo del "
  "vehículo. La laptop del equipo (Ryzen 5 8645HS) tiene además una NPU XDNA; con ONNX Runtime y el proveedor de AMD "
  "Ryzen AI el mismo modelo puede ejecutarse en ella con menor consumo. Esa ruta queda como siguiente paso y no se "
  "midió en este trabajo.")

h("6. Versión 4: más datos, escenas de calle y filtro adaptativo")
p("Antes de reentrenar se analizaron los errores de la v3. El pavimento omitía 125 de 184 cajas, casi todas pequeñas "
  "(menos del 2 % de la imagen), y los árboles 41 de 55. También se corrigió una confusión de nombres: la clase "
  "alcantarilla_tapada es una rejilla en buen estado, que solo amerita limpieza preventiva, y alcantarilla_riesgo es la "
  "obstruida, abierta o dañada. Para medir en campo de forma honesta se reservaron las imágenes de 133 instituciones "
  "(265 imágenes) que ningún modelo usa para entrenar.")
tabla([["Cambio", "Detalle"],
       ["Más pavimento", f"{filt['rdd_mas']} imágenes nuevas de RDD2022 con bache o piel de cocodrilo; se descartaron "
        f"{filt['rdd_mas_casi_duplicadas']} casi idénticas a imágenes ya usadas o de prueba (hash de diferencia)"],
       ["Escenas de calle", f"116 imágenes de Guadalajara revisadas a mano: {filt['campo_con_objetos']} con objetos y "
        f"{filt['campo_negativos']} negativos difíciles (falsos positivos del modelo anterior)"],
       ["Rejillas", f"{filt['alcantarillas_nuevas']} rejillas nuevas revisadas a mano"],
       ["Filtro adaptativo", "mide brillo, contraste y nitidez de cada imagen y solo corrige lo que falta: contraste "
        "menor a 45 (estiramiento con 1 % de recorte), brillo menor a 85 (gamma 0.75), mayor a 175 (gamma 1.3), "
        "nitidez menor a 60 (máscara de enfoque). Se aplica igual al entrenar y en la cámara"],
       ["Imágenes filtradas", ", ".join(f"{k} {v:,}" for k, v in filt["filtros"].items())],
       ["Entrenamiento", f"afinado desde la v3, 35 épocas, AdamW con tasa 0.0005, 1 época de calentamiento; "
        f"{filt['train']:,} imágenes de entrenamiento y {filt['val']} de validación, unas 1 h 40 min por variante"]])
p("Se entrenaron dos variantes idénticas, con y sin filtro, para saber si el filtro aporta. Un primer intento con tasa "
  "0.002 borró lo aprendido por la v3 (F1 0.21) y se descartó.")
filas = [["Clase", "v3", "v4 sin filtro", "v4 con filtro", "Precisión v4f", "Exhaustividad v4f"]]
for c in CL4 + ["general"]:
    z = y4f["con_umbral_elegido"].get(c, {})
    filas.append([NOM.get(c, "General").split(" (")[0] if c != "general" else "General"]
                 + [f"{m['con_umbral_elegido'].get(c, {}).get('f1', 0):.2f}" for m in (yo, y4, y4f)]
                 + [f"{z.get('precision', 0):.2f}", f"{z.get('recall', 0):.2f}"])
tabla(filas)
p("La v4 con filtro gana en general y sobre todo en daño de pavimento. El arbolado baja porque, para sostener 0.9 de "
  "precisión, el umbral sube a 0.6 y el modelo reporta menos árboles. Umbrales de la v4 con filtro:")
filas = [["Clase", "Umbral (prueba)", "¿Alcanza 0.9?", "Umbral en campo"]]
for c in CL4:
    filas.append([NOM[c].split(" (")[0], f"{umb4['umbrales'][c]:.2f}", "sí" if umb4["alcanza_meta"][c] else "no",
                  f"{umb4['umbrales_campo'][c]:.2f}"])
tabla(filas)
p("Prueba en campo honesta. En las imágenes de las 133 instituciones reservadas, con los umbrales de campo, 10 de 20 "
  "candidatos fueron reales: pavimento 3 de 4, rejillas 5 de 11 y árboles 2 de 5 (la v3, con umbrales más estrictos, "
  "dejaba 7 candidatos y 4 eran reales). Los falsos positivos más comunes fueron rejillas de ventilación del tablero del "
  "auto reflejadas en el parabrisas; subir el umbral no los separa. La muestra es chica, así que estas cifras son "
  "orientativas. Por eso toda detección sigue pasando por validación humana.")

h("7. Versión 5: clima adverso, drones y evaluación sin sesgo")
r5 = json.load(open(os.path.join(BASE, "dataset_yolo_v5", "resumen.json"), encoding="utf-8"))
ev_ = lambda n: json.load(open(os.path.join(BASE, "modelo", n), encoding="utf-8"))["con_umbrales_fijos"]  # noqa: E731
COND = [("calib", "Limpia (261 imágenes)"), ("lluvia", "Lluvia simulada"), ("noche", "Noche simulada"),
        ("niebla", "Niebla simulada"), ("movimiento", "Desenfoque de movimiento"),
        ("dron", f"Dron ({r5['prueba_dron']} reservadas)"), ("moto", f"Motocicleta ({r5['prueba_moto']} reservadas)"),
        ("japon", f"Japón ({r5['prueba_japon']} reservadas)")]
umb5 = json.load(open(os.path.join(BASE, "modelo", "entorno_seguro_v5_yolo11s.umbrales.json"), encoding="utf-8"))
p("El modelo se cargará en drones y vehículos que recorren las vías, también en temporal. Para eso la v5 se afinó 30 "
  "épocas desde la v4 con filtro y cambió cuatro cosas, cada una contra un sesgo medido en la v4:")
tabla([["Cambio", "Sesgo que atiende"],
       ["Etiquetas: revisión a mano con minería de errores (modelo contra etiqueta); "
        f"{r5['cajas_quitadas']} cajas equivocadas fuera y {r5['cajas_agregadas']} objetos sin etiqueta dentro",
        "Errores de etiqueta que enseñan a omitir"],
       [f"Validación: {r5['pasadas_a_val']} imágenes de alcantarillas y árboles pasaron de entrenamiento a validación",
        "La v4 validaba con 17 alcantarillas de riesgo y 23 árboles: el umbral se elegía casi solo por pavimento"],
       [f"Punto de vista: RDD2022 China_Drone, China_MotorBike y Japan ({r5['China_Drone_train'] + r5['China_MotorBike_train'] + r5['Japan_train']:,} "
        "para entrenar; 20 % de cada uno reservado como prueba aparte)", "Solo cámara de auto y pocos países"],
       ["Clima: variantes de lluvia " + f"{r5['clima_lluvia']}, noche {r5['clima_noche']}, niebla {r5['clima_niebla']} y "
        f"movimiento {r5['clima_movimiento']}, más 480 extra de alcantarillas y árboles, todas con el filtro adaptativo",
        "Entrenada solo con buen tiempo"]])
p("Evaluación sin sesgo. Antes los umbrales se elegían sobre la misma prueba que se reportaba, lo que infla la cifra. "
  "Ahora se calibran en la validación (974 imágenes, sin clima) y se dejan fijos para todas las pruebas. Con ese método "
  "la v4 baja de 0.60 a 0.51 de F1 en limpio. F1 general (precisión) por condición:")
filas = [["Condición", "v4 con filtro", "v5 clima"]]
for k, t in COND:
    a, b = ev_(f"eval_v4f_{k}.json")["general"], ev_(f"eval_v5_{k}.json")["general"]
    filas.append([t, f"{a['f1']:.2f} ({a['precision']:.2f})", f"{b['f1']:.2f} ({b['precision']:.2f})"])
tabla(filas)
p("La v5 iguala a la v4 en limpio y la supera en lluvia, noche, movimiento y, sobre todo, en vista de dron, motocicleta "
  "y otro país; solo pierde en niebla. La precisión queda en 0.79 o más en todas las condiciones. La meta de 0.8 se "
  "cumple en precisión, no en F1: el modelo es confiable cuando marca, pero todavía omite objetos. Por clase, en limpio:")
v5c = ev_("eval_v5_calib.json")
filas = [["Clase", "Umbral calibrado", "Precisión", "Exhaustividad", "F1"]]
for c in CL4:
    z = v5c[c]
    filas.append([NOM[c].split(" (")[0], f"{umb5['umbrales'][c]:.2f}", f"{z['precision']:.2f}", f"{z['recall']:.2f}",
                  f"{z['f1']:.2f}"])
tabla(filas)
s5 = json.load(open(os.path.join(BASE, "modelo", "sesgos_v5.json"), encoding="utf-8"))
ex, fa = s5["exhaustividad"], s5["falsas_alarmas_por_imagen"]
p(f"Análisis de sesgos (sesgos_v5.json). Por luz: {fa['luz oscura (<85)']['valor']:.2f} falsas alarmas por imagen en "
  f"imágenes oscuras ({fa['luz oscura (<85)']['imagenes']} imágenes) contra {fa['luz normal']['valor']:.2f} con luz "
  f"normal; de noche conviene exigir más confianza o sumar iluminación. Por tamaño: el daño de pavimento pequeño (menos "
  f"del 1 % de la imagen) se encuentra en {ex['dano_pavimento · pequeño (<1 %)']['valor']:.2f} de los casos y el "
  f"grande en {ex['dano_pavimento · grande (>5 %)']['valor']:.2f}; un dron debe volar bajo o usar más resolución. "
  f"En imágenes sin objetos solo hay {fa['sin objetos']['valor']:.2f} falsas alarmas por imagen. El arbolado sigue "
  "siendo la clase más débil por su etiquetado en cuadrícula gruesa.")
p("Prueba en campo de la v5. Con el mismo método de la sección 6, en las 133 instituciones reservadas 5 de 17 "
  "candidatos fueron reales (pavimento 1 de 2, rejillas 2 de 7, árboles 2 de 8), contra 10 de 20 de la v4. De los 10 "
  "hallazgos reales de la v4, la v5 marca 5; a cuatro no les da puntaje, así que bajar el umbral no los recupera. La v5 "
  "se queda como modelo único por su robustez en clima y en vista de dron, y el costo es menos acierto en cámara de "
  "auto sobre calles locales; la siguiente mejora es entrenar con fotos propias de Guadalajara.")

h("7.1 Versión 8: fotos recientes de Guadalajara")
p("La v5 resistía bien el clima y el dron, pero en cámara de auto sobre calles de Guadalajara solo 5 de 17 candidatos "
  "eran reales. Para corregirlo se bajaron fotos recientes de Mapillary alrededor de las instituciones (sin tocar las 133 "
  "reservadas) y se minaron etiquetas: los modelos anteriores propusieron candidatos con confianza baja (0.2) y cada uno "
  "se revisó a mano en láminas de 24 recortes. Lo real se volvió caja de entrenamiento y lo falso, ejemplo negativo. "
  "Criterio: rejilla pluvial visible; bache o piel de cocodrilo; árbol con cables que cruzan la copa o tronco claramente "
  "inclinado (las tapas redondas de registro no cuentan). Cada foto entra cuatro veces: original, espejo, lluvia y noche. "
  "La separación entre entrenamiento y validación se hizo por institución.")
tabla([["Versión", "Punto de partida", "Fotos GDL nuevas en entrenamiento", "Objetos reales confirmados"],
       ["v6", "v5", "182 escenas", "—"], ["v7", "v6", "285 (80 con objetos)", "105"],
       ["v8", "v5", "las de v6 y v7 + 230 (62 con objetos)", "105 + 86 = 191"]])
p("La v7 partió de la v6 y mejoró en calle, pero perdió robustez (F1 en dron 0.33). La v8 vuelve a partir de la v5 con "
  "todas las fotos, 15 épocas con tasa de aprendizaje 0.0005. Umbrales: se calibraron en validación buscando 0.9 de "
  "precisión. Rejillas (0.45), alcantarillas de riesgo (0.7) y pavimento (0.45) la alcanzan; arbolado solo llega a 0.9 "
  "con un umbral de 0.8 que casi no detecta nada, así que se fijó en 0.5 (precisión 0.80 en validación). Queda registrado "
  "en entorno_seguro_v8_yolo11s.umbrales.json.")
filas8 = [["Condición", "v5 clima", "v8 GDL"]]
for c, nom in COND:
    a5, a8 = ev_(f"eval_v5_{c}.json")["general"], ev_(f"eval_v8b_{c}.json")["general"]
    filas8.append([nom, f"{a5['f1']:.2f} ({a5['precision']:.2f})", f"{a8['f1']:.2f} ({a8['precision']:.2f})"])
tabla(filas8)
p("Prueba de campo en las calles de las 133 instituciones reservadas (candidatos revisados a mano):")
tabla([["Modelo", "Reales / candidatos", "Detalle"],
       ["v4 con filtro", "10 / 20", "—"], ["v5 clima", "5 / 17", "pavimento 1/2, rejillas 2/7, árboles 2/8"],
       ["v7", "10 / 17", "—"], ["v8", "11 / 18", "árboles 6/8, rejillas 4/7, pavimento 1/3"]])
p("Dos de los árboles de la v8 parecen ser el mismo árbol en dos fotos, así que la cifra real está entre 10 y 11 de 18. "
  "La v8 pierde algo en limpio (0.46 contra 0.51) y de noche (0.36 contra 0.41), y gana en calle, en dron y en "
  "motocicleta.")

h("7.2 Versión 9: más épocas sobre la v8 (modelo integrado)")
p("Al terminar sus 15 épocas, la v8 seguía mejorando en validación. La v9 parte de sus pesos con los mismos datos, "
  "30 épocas más, AdamW con tasa de aprendizaje 0.0003, una época de calentamiento y paciencia de 12. En validación "
  "llegó a su mejor punto entre las épocas 8 y 12 (mAP50 0.69, igual que la v8; mAP50-95 de 0.375 a 0.393) y después "
  "empezó a memorizar: con este dataset, más épocas ya no dan más. Los umbrales se calibraron con la misma regla y el "
  "mismo conjunto que la v8: rejillas (0.7) y pavimento (0.5) alcanzan 0.9 de precisión; alcantarillas de riesgo y "
  "arbolado no, y usan 0.5. Queda registrado en entorno_seguro_v9_yolo11s.umbrales.json.")
filas9 = [["Condición", "v8 GDL", "v9"]]
for c, nom in COND:
    a8, a9 = ev_(f"eval_v8b_{c}.json")["general"], ev_(f"eval_v9_{c}.json")["general"]
    filas9.append([nom, f"{a8['f1']:.2f} ({a8['precision']:.2f})", f"{a9['f1']:.2f} ({a9['precision']:.2f})"])
tabla(filas9)
tabla([["Modelo", "Reales / candidatos", "Detalle"],
       ["v8", "11 / 18", "árboles 6/8, rejillas 4/7, pavimento 1/3"],
       ["v9 (integrada)", "11 / 16", "árboles 7/10, pavimento 3/4, rejillas 1/2"]])
p("En las mismas calles reservadas la v9 encuentra lo mismo que la v8 con dos falsas alarmas menos. Como su umbral "
  "de rejillas subió a 0.7, muestra menos rejillas: de las 6 que deja de marcar, 4 se habían revisado como falsas y 1 "
  "como real. Cuatro veredictos de la v9 fueron dudosos y dos de sus árboles parecen ser el mismo en dos fotos. En "
  "laboratorio gana en 5 de 8 condiciones y pierde con desenfoque de movimiento (0.33 contra 0.35) y en Japón (0.46 "
  "contra 0.49). Con ella el Coordinador genera 494 órdenes en 373 instituciones.")

h("Arquitectura del modelo integrado", 2)
p("La v9 es un YOLO11s de Ultralytics: una red convolucional de una sola etapa que en una pasada localiza los "
  "objetos y los clasifica. Tiene tres partes (Figura 7). El backbone convierte la foto en mapas de rasgos con "
  "convoluciones de paso 2 y bloques C3k2 (versión ligera del cuello de botella con atajos de CSP); al final, SPPF junta "
  "contexto de varias escalas con tres max-pool en cadena y C2PSA agrega atención espacial para que la red pese las "
  "zonas relevantes, como la copa de un árbol cruzada por cables. El cuello FPN-PAN sube y baja la resolución y "
  "concatena mapas de 80 x 80, 40 x 40 y 20 x 20 celdas, así ve tanto una grieta chica como un árbol completo. La "
  "cabeza Detect, sin anclas y desacoplada, predice en cada una de las 8,400 posiciones la caja (regresión con DFL) y "
  "la probabilidad de las 4 clases. Las cifras de la tabla se midieron sobre los pesos de la v9.")
tabla([["Parte", "Módulos (índice)", "Bloques", "Parámetros"],
       ["Backbone", "0-10", "Conv x5, C3k2 x4, SPPF, C2PSA", "5,441,984"],
       ["Cuello FPN-PAN", "11-22", "Upsample x2, Concat x4, C3k2 x4, Conv x2", "3,166,400"],
       ["Cabeza Detect", "23", "3 escalas (pasos 8, 16 y 32), sin anclas", "820,956"],
       ["Total", "24 módulos, 181 capas", "21.7 GFLOPs por imagen de 640 x 640", "9,429,340"]])
tabla([["Elemento", "Valor"],
       ["Entrada", "640 x 640 px RGB, letterbox gris; antes, filtro adaptativo de brillo, contraste y nitidez"],
       ["Salida cruda", "8,400 propuestas x (4 coordenadas de caja + 4 clases)"],
       ["Posproceso (agente Inspector)", "umbral por clase (rejilla 0.7, alcantarilla de riesgo 0.5, árbol 0.5, "
        "pavimento 0.5) y supresión de no máximos con IoU 0.5"],
       ["Origen de los pesos", "COCO → v3 → v4 → v5 (clima y dron) → v8 (15 épocas con fotos de Guadalajara) → v9 (30 épocas más)"],
       ["Formato de despliegue", "ONNX (opset 12), 38 MB; ONNX Runtime en CPU, unos 0.1 s por imagen"]])
fig_("fig2_arquitectura_yolo.png", "Figura 7. Arquitectura del detector YOLO11s v9.", ancho=11)

h("Uso del detector en el tablero en vivo", 2)
p("El tablero en vivo (entregables/tablero_vivo) recibe las detecciones de este modelo sobre las fotos de Mapillary. "
  "Por cada foto toma el candidato de mayor confianza que pasa el umbral calibrado de su clase y el filtro adaptativo: "
  "127 candidatos de árboles, pavimento y alcantarillas. Cada uno aparece con su foto en la pestaña Validación IA y "
  "se queda como pendiente hasta que un operador lo confirma o lo descarta; la confianza indica certeza de la clase, "
  "no gravedad del daño. Las 494 órdenes ya generadas por el Coordinador aparecen en el mapa (Figura 8), y su prioridad "
  "se ajusta con el pronóstico del SMN en vivo: lluvia de 60% o 5 mm sube rejillas y alcantarillas (x1.35) y pavimento "
  "(x1.2); viento de 40 km/h o más sube árboles y cableado (x1.5). Son umbrales piloto, no criterios oficiales.")
fig_("fig6_tablero_ordenes.jpg", "Figura 8. Tablero en vivo: órdenes priorizadas sobre el mapa de Guadalajara. "
     "Mapa base © Esri; límites © INEGI.")

h("8. Limitaciones")
for t in ["El conjunto de prueba de alcantarillas de riesgo y de árboles es chico (decenas de objetos); sus cifras "
          "pueden variar varios puntos con otra muestra.",
          "Piel de cocodrilo (v1 y v2): F1 de 0 en los tres modelos FOMO. FOMO marca centros en una cuadrícula de 40 x 40 y una grieta "
          "extensa se parece a un bache a esa escala; el modelo la absorbe como bache. Para el municipio ambas van a "
          "Pavimentos, así que una opción es unirlas en una clase de daño de pavimento; otra, subir la entrada a 480 px.",
          "Exhaustividad baja (0.35 en v3, 0.46 en v4): el modelo omite muchos objetos. Hacen falta fotos propias del "
          "equipo, de 50 a 100 por clase, tomadas a la altura de la cámara del vehículo, sobre todo de árboles y "
          "alcantarillas de riesgo.",
          "Hasta la v4 los umbrales se calibraron sobre la misma prueba que se reportaba (cifras optimistas). Desde la "
          "v5 se calibran en la validación; las cifras de la sección 7 son las honestas.",
          "Lluvia, noche y niebla son simuladas; falta validarlas con video real de dron o vehículo en temporal.",
          "Licencia: Ultralytics YOLO11 es AGPL-3.0. Para un despliegue municipal cerrado se necesita licencia "
          "empresarial de Ultralytics o publicar el código del sistema con la misma licencia.",
          "Las etiquetas de alcantarillas y árboles las hizo el equipo, sin revisión de especialistas.",
          "En campo, toda detección pasa por la validación del operador antes de convertirse en orden."]:
    d.add_paragraph(t, style="List Bullet")

h("9. Cómo reproducirlo")
for t in ["python entrenamiento/rdd2022_nuevos.py  ·  python entrenamiento/preparar_yolo_v5.py",
          ".venv_yolo/Scripts/python entrenamiento/entrenar_yolo.py --datos dataset_yolo_v5 --nombre v5_clima "
          "--pesos modelo/yolo/v4_con_filtro/weights/best.pt --epocas 30 --paciencia 30 --lr0 0.0005 --calentamiento 1",
          ".venv_yolo/Scripts/python entrenamiento/evaluar_yolo.py modelo/yolo/v5_clima/weights/best.pt --prueba "
          "calibracion --salida calib_v5.json  ·  después --filtro --umbrales modelo/calib_v5.json con --clima "
          "lluvia|noche|niebla|movimiento o --prueba prueba_dron|prueba_moto|prueba_japon",
          ".venv_yolo/Scripts/python entrenamiento/analisis_sesgos.py modelo/yolo/v5_clima/weights/best.pt "
          "modelo/calib_v5.json --filtro --salida sesgos_v5.json",
          "v8: python entrenamiento/preparar_yolo_v8.py  ·  entrenar_yolo.py --datos dataset_yolo_v8 --nombre v8_gdl "
          "--pesos modelo/yolo/v5_clima/weights/best.pt --epocas 15 --paciencia 15 --lr0 0.0005 --calentamiento 1",
          "v9: entrenar_yolo.py --datos dataset_yolo_v8 --nombre v9_gdl --pesos modelo/yolo/v8_gdl/weights/best.pt "
          "--epocas 30 --paciencia 12 --lr0 0.0003 --calentamiento 1",
          "python agente/inspector.py --modelo entrenamiento/modelo/entorno_seguro_v9_yolo11s.onnx --mixto "
          "--umbral-guardar 0.25 --salida agente/salida/detecciones_yolo.json"]:
    q = d.add_paragraph(style="List Number")
    r = q.add_run(t)
    r.font.name, r.font.size = "Consolas", Pt(8.5)
p("Créditos: RDD2022 (Arya et al., 2022), CC BY 4.0 · Imágenes © Mapillary y sus autores, CC BY-SA 4.0 · Edge Impulse · "
  "Ultralytics YOLO11, AGPL-3.0.",
  it=True, size=8.5)
d.save(OUT)
print("ficha:", OUT, "| curva:", len(curva), "épocas")
