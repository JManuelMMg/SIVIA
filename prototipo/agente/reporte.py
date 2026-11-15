"""Genera el reporte científico sobre el Formato_Reporte_Avanzado_Cientifico.docx, con figuras y tablas.

Uso:  python agente/reporte.py
Salida: entregables/Reporte_Cientifico_SIVIA.docx  y  entregables/figuras/*.png
"""
import copy
import csv
import json
import os
import sys

import docx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm, Pt  # noqa: E402
from docx.text.paragraph import Paragraph  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAIZ = os.path.dirname(BASE)
SAL = os.path.join(BASE, "agente", "salida")
FIG = os.path.join(RAIZ, "entregables", "figuras")
SRC = r"C:\Users\jmedi\Downloads\Formato_Reporte_Avanzado_Cientifico.docx"
OUT = os.path.join(RAIZ, "entregables", "Reporte_Cientifico_SIVIA.docx")
N = "SIVIA"
ANCHO = Cm(7.4)  # el cuerpo del formato va a dos columnas
os.makedirs(FIG, exist_ok=True)


def leer(p, enc="utf-8"):
    with open(p, encoding=enc) as fh:
        return list(csv.DictReader(fh))


clima = json.load(open(os.path.join(SAL, "clima_smn.json"), encoding="utf-8"))
ordenes = leer(os.path.join(SAL, "ordenes_trabajo.csv"), "utf-8-sig")
inst = leer(os.path.join(BASE, "datos", "denue_gdl_instituciones.csv"))
sin = {r["id"]: r for r in leer(os.path.join(BASE, "datos", "instituciones_siniestralidad.csv"))}
atus = leer(os.path.join(BASE, "datos", "atus_gdl_2022_2024.csv"))

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.titlesize": 8.5})
VERDE, AMBAR, ROJO, AZUL, GRIS = "#2e8a57", "#d39317", "#c73b3b", "#2f6db5", "#9aa3a0"

# --- Figura 1: arquitectura -----------------------------------------------------------------
fig, ax = plt.subplots(figsize=(3.4, 4.3), dpi=220)
ax.axis("off")
cajas = [("Datos abiertos", "DENUE #09 · ATUS #08 · SMN #45\nimágenes de calle Mapillary", "#e8eef7"),
         ("Inspector", "detector YOLO11s (ONNX)\nsobre cada imagen", "#dcefe8"),
         ("Clasificador", "tipo de falla y dependencia\nresponsable", "#dcefe8"),
         ("Evaluador de impacto", "tipo y tamaño de la institución,\naccidentes a 200 m", "#dcefe8"),
         ("Vigía", "umbrales históricos de lluvia\ny pronóstico municipal SMN", "#dcefe8"),
         ("Coordinador", "Prioridad = Gravedad x Impacto\nx Riesgo x Clima", "#dcefe8"),
         ("Validación humana y tablero", "órdenes por dependencia,\ncandidatos por confirmar", "#fbeed2")]
for i, (t, s, c) in enumerate(cajas):
    y = 1 - i * 0.142
    ax.add_patch(plt.Rectangle((0.04, y - 0.11), 0.92, 0.1, color=c, ec="#55605c", lw=0.6, transform=ax.transAxes))
    ax.text(0.5, y - 0.036, t, ha="center", va="center", fontsize=7.6, weight="bold", transform=ax.transAxes)
    ax.text(0.5, y - 0.08, s, ha="center", va="center", fontsize=6.2, color="#333", transform=ax.transAxes)
    if i < len(cajas) - 1:
        ax.text(0.5, y - 0.126, "▼", ha="center", va="center", fontsize=5.5, color="#55605c", transform=ax.transAxes)
fig.savefig(os.path.join(FIG, "fig1_arquitectura.png"), bbox_inches="tight")
plt.close(fig)

# --- Figura 2: arquitectura del detector YOLO11s (cifras medidas sobre los pesos v9) -----------
fig, ax = plt.subplots(figsize=(3.4, 4.6), dpi=220)
ax.axis("off")
capas = [("Entrada", "foto de calle a 640 x 640 px (letterbox)\ny filtro adaptativo de brillo y nitidez", "#e8eef7"),
         ("Backbone (5.4 M parámetros)", "Conv con paso 2 y bloques C3k2;\nSPPF (contexto a varias escalas)\ny C2PSA (atención espacial)", "#dcefe8"),
         ("Cuello FPN-PAN (3.2 M)", "sube y baja la resolución y une mapas\nde 80x80, 40x40 y 20x20 celdas", "#dcefe8"),
         ("Cabeza de detección (0.8 M)", "sin anclas, a 3 escalas: en 8,400\nposiciones predice caja y 4 clases", "#dcefe8"),
         ("Salida y agente Inspector", "umbral calibrado por clase y supresión\nde cajas repetidas (IoU 0.5)", "#fbeed2")]
for i, (t, s_, c) in enumerate(capas):
    y = 1 - i * 0.185
    ax.add_patch(plt.Rectangle((0.04, y - 0.16), 0.92, 0.15, color=c, ec="#55605c", lw=0.6, transform=ax.transAxes))
    ax.text(0.5, y - 0.04, t, ha="center", va="center", fontsize=7.4, weight="bold", transform=ax.transAxes)
    ax.text(0.5, y - 0.105, s_, ha="center", va="center", fontsize=6.0, color="#333", linespacing=1.2,
            transform=ax.transAxes)
    if i < len(capas) - 1:
        ax.text(0.5, y - 0.172, "▼", ha="center", va="center", fontsize=5.5, color="#55605c", transform=ax.transAxes)
ax.text(0.5, 1 - 5 * 0.185 + 0.005, "YOLO11s: 181 capas · 9.4 M parámetros · 21.7 GFLOPs · ONNX de 38 MB",
        ha="center", va="center", fontsize=6.0, style="italic", color="#333", transform=ax.transAxes)
fig.savefig(os.path.join(FIG, "fig2_arquitectura_yolo.png"), bbox_inches="tight")
plt.close(fig)

# --- Figura 3: mapa de instituciones y accidentes ---------------------------------------------
por_inst = {}
for o in ordenes:
    por_inst.setdefault(o["institucion_id"], []).append(o)
niv = {0: [], 1: [], 2: []}
for r in inst:
    s = sin.get(r["id"], {})
    acc, peat = int(s.get("accidentes_200m_3a", 0) or 0), int(s.get("accidentes_con_peaton_200m", 0) or 0)
    hs = por_inst.get(r["id"], [])
    n = 2 if (hs and peat > 0) or any(h["clave"] == "sin_cruce" for h in hs) else 1 if (hs or peat > 0 or acc >= 15) else 0
    niv[n].append((float(r["longitud"]), float(r["latitud"])))
fig, ax = plt.subplots(figsize=(3.4, 3.4), dpi=220)
ax.scatter([float(a["LONGITUD"]) for a in atus], [float(a["LATITUD"]) for a in atus], s=0.3, c=GRIS, alpha=.35,
           lw=0, label="Accidente 2022-2024")
for n, c, lab, sz in ((0, VERDE, "Sin hallazgos", 2.5), (1, AMBAR, "Nivel medio", 4), (2, ROJO, "Nivel alto", 6)):
    xs = niv[n]
    ax.scatter([x for x, _ in xs], [y for _, y in xs], s=sz, c=c, lw=0, label=f"{lab} ({len(xs)})")
ax.set_xlim(-103.42, -103.26)
ax.set_ylim(20.60, 20.75)
ax.set_aspect(1 / 0.936)
ax.set_xticks([])
ax.set_yticks([])
for sp in ax.spines.values():
    sp.set_visible(False)
ax.legend(loc="lower left", fontsize=5.8, markerscale=2.2, frameon=True, framealpha=.9)
fig.savefig(os.path.join(FIG, "fig2_mapa_riesgo.png"), bbox_inches="tight")
plt.close(fig)

# --- Figura 4: climatología SMN ---------------------------------------------------------------
fig, ax = plt.subplots(figsize=(3.4, 2.2), dpi=220)
mes = list("EFMAMJJASOND")
ax.bar(range(12), clima["climatologia_mensual_mm"], color=AZUL, width=.7, label="Lluvia mensual promedio (mm)")
ax.set_xticks(range(12), mes)
ax.set_ylabel("mm")
ax2 = ax.twinx()
ax2.plot(range(12), clima["eventos_extremos_por_mes"], color=ROJO, marker="o", ms=2.5, lw=1.2,
         label=f"Días con lluvia ≥ {clima['umbrales_mm']['p95']} mm")
ax2.set_ylabel("días (1981-2026)")
ax2.spines["top"].set_visible(False)
h1, l1 = ax.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, fontsize=5.8, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2, frameon=False)
fig.savefig(os.path.join(FIG, "fig3_clima_smn.png"), bbox_inches="tight")
plt.close(fig)

# --- Figura 5: evidencia del modelo (la alcantarilla con mayor confianza) -----------------------
det = json.load(open(os.path.join(SAL, "detecciones_modelo.json"), encoding="utf-8"))
meta = {r["archivo"]: r for r in leer(os.path.join(BASE, "entrenamiento", "mapillary", "imagenes.csv"))}
alc = sorted(((d["score"], f, d) for f, v in det.items() for d in v if d["label"].startswith("alcantarilla")),
             key=lambda t: -t[0])
_, f_ev, d_ev = next(t for t in alc if t[1] == "mly_1301025204365863.jpg")  # rejilla con escombro (revisada a mano)
im = Image.open(os.path.join(BASE, "entrenamiento", "mapillary", "images", f_ev)).convert("RGB")
dr = ImageDraw.Draw(im)
pad = 12
dr.rectangle([d_ev["x"] - pad, d_ev["y"] - pad, d_ev["x"] + d_ev["w"] + pad, d_ev["y"] + d_ev["h"] + pad],
             outline=(0, 220, 240), width=8)
cx, cy = d_ev["x"] + d_ev["w"] / 2, d_ev["y"] + d_ev["h"] / 2
L = max(380, 5 * max(d_ev["w"], d_ev["h"]))
x0, y0 = max(0, cx - L * 0.8), max(0, cy - L / 2)
im.crop((int(x0), int(y0), int(min(im.width, x0 + 1.6 * L)), int(min(im.height, y0 + L)))).save(
    os.path.join(FIG, "fig4_evidencia_alcantarilla.jpg"), quality=88)
autor_ev, fecha_ev = meta.get(f_ev, {}).get("autor_mapillary", ""), meta.get(f_ev, {}).get("captura", "")

# --- Textos -----------------------------------------------------------------------------------
LLV = clima["lluvia_vs_accidentes"]
U = clima["umbrales_mm"]
ext = clima["eventos_extremos_por_mes"]
pct_temporal = round(100 * sum(ext[5:9]) / sum(ext))
TITULO = f"{N}: inspección preventiva con inteligencia artificial en el entorno de escuelas, guarderías y hospitales de Guadalajara"

TXT = {
 10: "Hackathon Jalisco Internacional 2026 (SOLACYT) · Reto 01: Ciudades Inteligentes",
 13: TITULO,
 15: "Núm. de Proyecto: [PENDIENTE]",
 16: "Autor(es): [PENDIENTE]", 17: "Asesor: [PENDIENTE]", 18: "Escuela: [PENDIENTE]",
 20: "Nivel Educativo: [PENDIENTE]", 21: "Categoría: Hackathon · Ciudades Inteligentes", 22: "Sede: [PENDIENTE]",
 24: "Guadalajara, Jalisco, noviembre de 2026",
 28: TITULO,
 30: ("En Guadalajara, una falla en la calle entra a la agenda municipal cuando alguien la reporta. Así funcionan el 070, "
      "Ciudapp y GuaZap, y el propio Ayuntamiento reconoce rezagos en el seguimiento de esos reportes. Lo que nadie "
      "reporta se queda sin revisar, aunque esté frente a un preescolar o a la entrada de un hospital. Este proyecto "
      "propone invertir el orden: que la ciudad inspeccione primero. Con el Directorio Estadístico Nacional de Unidades "
      "Económicas (DENUE, INEGI 05/2026) ubicamos 1,646 escuelas, guarderías y hospitales del municipio. Al cruzarlos con "
      "los accidentes de tránsito georreferenciados del INEGI (2022-2024) encontramos que 7,301 de 11,568 accidentes, el "
      "63%, ocurrieron a 200 m o menos de alguna de esas instituciones; lo mismo pasó con 159 de los 270 accidentes con "
      "peatones. Sobre esa base construimos un sistema de cinco agentes de software. El Inspector revisa imágenes de calle "
      "de Mapillary con un detector entrenado en Edge Impulse. El Clasificador asigna cada hallazgo a la dependencia "
      "responsable y el Evaluador de impacto pondera el tipo y tamaño de la institución junto con la siniestralidad "
      "cercana. El Vigía usa 45 años de registros diarios de lluvia y el pronóstico municipal del Servicio Meteorológico "
      "Nacional (SMN) para subir la prioridad antes de un evento extremo, y el Coordinador emite órdenes de trabajo con "
      "su explicación. En la primera inspección se revisaron 539 instituciones con imágenes disponibles: 373 tuvieron al "
      "menos un hallazgo y se generaron 494 órdenes, entre ellas 116 escuelas y guarderías sin cruce peatonal visible en "
      f"calles con atropellamientos. La serie del SMN muestra que el {pct_temporal}% de los días con lluvia extrema "
      f"({U['p95']} mm o más) cae entre junio y septiembre. Esa es la ventana para el mantenimiento preventivo. El "
      "detector YOLO11s, entrenado en una laptop con un filtro adaptativo y lluvia, noche y movimiento simulados, "
      "alcanza 0.85 de precisión en imágenes no vistas y 0.86 en vista de dron; en calles de Guadalajara que no vio, 11 de "
      "sus 16 candidatos fueron reales. Como todavía "
      "omite casos, sus detecciones pasan por validación humana antes de convertirse en orden. El resultado es un tablero operativo con mapa de riesgo, "
      "órdenes filtrables por dependencia, pronóstico del SMN en vivo y validación de candidatos. La propuesta usa cuadrillas y "
      "plataformas que el municipio ya tiene y puede pilotearse en una zona antes del temporal de 2027."),
 34: ("Una coladera tapada no es noticia hasta que la calle se inunda. Un bache frente a una primaria tampoco, hasta que "
      "alguien cae. La infraestructura urbana suele atenderse después del daño porque el municipio depende de que la "
      "ciudadanía vea el problema y lo reporte. Este trabajo explora otra ruta: usar datos abiertos e inteligencia "
      "artificial para revisar de forma sistemática el entorno de los lugares donde se concentran niñas, niños, pacientes "
      "y personas mayores."),
 35: ("Primero se plantean la justificación y el problema. Siguen el contexto teórico, la metodología con los datos y "
      "modelos empleados, los resultados de la primera inspección y su discusión. El documento cierra con el trabajo a "
      "futuro y las conclusiones."),
 38: ("La siniestralidad vial de Guadalajara se concentra cerca de las instituciones sensibles. Entre 2022 y 2024, el 95% "
      "de las 1,646 instituciones registró al menos un accidente a 200 m o menos, y 322 (20%) tuvieron al menos un "
      "atropellamiento cercano. A eso se suma el temporal. Según la Base de Datos Climatológica Nacional, julio promedia "
      f"{round(clima['climatologia_mensual_mm'][6])} mm de lluvia, y el 13 de junio de 2022 cayeron "
      f"{round(clima['maximo_historico']['mm'])} mm en un solo día. Con lluvias así, una alcantarilla obstruida o un árbol "
      "inclinado dejan de ser un detalle de mantenimiento."),
 39: ("El proyecto combina tres áreas de conocimiento. La inteligencia artificial y la ciencia de datos aportan los "
      "agentes, la visión por computadora y la integración de datos. La planeación urbana y la ingeniería civil definen "
      "qué cuenta como falla en pavimento, drenaje, arbolado y seguridad peatonal. La administración pública y la gestión "
      "de riesgos ordenan el flujo: qué dependencia atiende cada caso, cómo se prioriza y cuánto cuesta operarlo."),
 42: ("¿Se pueden identificar y priorizar de forma automática, con datos abiertos e inteligencia artificial, las fallas "
      "de infraestructura en el entorno de las escuelas, guarderías y hospitales de Guadalajara antes de que la "
      "ciudadanía las reporte, y ajustar esa prioridad según el riesgo climático?"),
 44: ("Delimitación: municipio de Guadalajara, Jalisco; 1,646 instituciones educativas y de salud registradas en el "
      "DENUE; fallas visibles desde la calle (baches, alcantarillas, arbolado de riesgo y cruces peatonales); imágenes de "
      "2019 a 2025, accidentes de 2022 a 2024 y series de lluvia desde 1981. Usuarios: las dependencias que atienden "
      "cada hallazgo (Parques y Jardines, Pavimentos, Movilidad, Alumbrado Público y SIAPA) y la Coordinación General de "
      "Servicios Públicos Municipales, que reparte las órdenes. Indicadores de mejora: (1) instituciones con su entorno "
      "inspeccionado en el último año, con línea base de 539 de 1,646 (33%); (2) días entre que una falla queda "
      "registrada y se atiende, comparados con los reportes del 070 y Ciudapp; (3) rejillas y árboles de riesgo "
      "atendidos antes del 1 de junio, inicio del temporal."),
 31: "", 47: "",
 50: ("Un sistema de agentes que combine imágenes de calle, un detector de objetos y datos oficiales de siniestralidad y "
      "clima puede generar una línea base del estado de la infraestructura frente a las instituciones sensibles de "
      "Guadalajara y priorizar órdenes de trabajo por dependencia, con un costo de operación al alcance del presupuesto "
      "municipal."),
 51: "", 52: "",
 55: ("Preguntas complementarias. ¿Qué tanto se concentra la siniestralidad vial alrededor de las instituciones? ¿Qué "
      "precisión logra un detector ligero entrenado con datos abiertos y locales? ¿En qué meses el riesgo climático "
      "justifica adelantar el mantenimiento?"),
 56: "",
 59: ("Objetivo general: desarrollar un prototipo de agentes de inteligencia artificial que inspeccione el entorno de las "
      "instituciones sensibles de Guadalajara y genere órdenes de trabajo priorizadas y explicadas. Objetivos "
      "específicos: (1) integrar el inventario de instituciones del DENUE; (2) medir la siniestralidad a 200 m con los "
      "accidentes georreferenciados del INEGI; (3) calcular umbrales de lluvia extrema y un factor de clima con datos del "
      "SMN; (4) reunir imágenes de calle y entrenar un detector de fallas en Edge Impulse; (5) asignar cada hallazgo a su "
      "dependencia con una prioridad verificable; (6) presentar la línea base en un tablero de operación."),
 62: ("Las plataformas de reporte ciudadano, como el 070, Ciudapp y GuaZap en Guadalajara, organizan la atención "
      "municipal, pero solo registran lo que alguien decide reportar. La detección automática de daños en pavimento con "
      "visión por computadora tiene una base amplia: el conjunto RDD2022 (Arya et al., 2022) reúne más de 47,000 imágenes "
      "de seis países con daños etiquetados. Mapillary publica imágenes de calle colaborativas con licencia CC BY-SA 4.0, "
      "junto con detecciones automáticas de mobiliario urbano como postes y pasos peatonales. Los modelos ligeros para "
      "dispositivos, como FOMO de Edge Impulse, detectan objetos en hardware de bajo costo; con ellos sería posible montar "
      "cámaras en vehículos municipales que ya recorren la ciudad. En climatología, la lluvia extrema suele definirse con "
      "percentiles de la serie local. Así, un pronóstico se compara con lo que es raro en esa ciudad y no con un umbral "
      "nacional."),
 65: ("Se trata de una investigación aplicada de enfoque mixto, con alcance descriptivo y correlacional, organizada en "
      "seis etapas. (1) Inventario. Del DENUE (sectores 61 y 62) se extrajeron 1,646 instituciones del municipio; 1,271 son "
      "preescolares, primarias, guarderías u hospitales. (2) Siniestralidad. De los accidentes georreferenciados del INEGI "
      "2022-2024 se tomaron los 11,568 de Guadalajara. Para cada institución se contaron los ocurridos a 200 m o menos, "
      "con personas heridas, fallecidas y peatones."),
 66: ("(3) Clima. Se descargaron las series diarias de las estaciones 14065 Guadalajara (OBS) y 14066 Guadalajara (DGE) "
      f"de la Base de Datos Climatológica Nacional: {clima['dias_con_dato']:,} días con dato entre 1981 y 2026. Con los "
      "días de lluvia se calcularon los percentiles 90, 95 y 99, y se consultó el pronóstico diario por municipio del SMN. "
      "El agente Vigía clasifica cada día pronosticado como normal, fuerte o extremo y multiplica la prioridad de los "
      "hallazgos sensibles al agua o al viento. (4) Imágenes y etiquetado. Se reunieron 1,130 imágenes de calle de "
      "Mapillary (2048 px) a 50 m o menos de las instituciones y recortes de 3,464 alcantarillas de la ciudad. Se usaron "
      "3,161 imágenes de daño de pavimento de RDD2022; el equipo etiquetó 475 alcantarillas, 265 imágenes de árboles y "
      "revisó a mano 116 imágenes de calle de Guadalajara, cuyos falsos positivos se usaron como ejemplos negativos. Las "
      "imágenes de 133 instituciones se reservaron solo para medir en campo."),
 67: ("(5) Entrenamiento. Primero se entrenó un modelo FOMO MobileNetV2 0.35 en Edge Impulse (320 x 320 px). Al no "
      "superar un F1 de 0.33, se unieron bache y piel de cocodrilo en una clase (daño de pavimento) y se entrenó un "
      "detector YOLO11s de cajas en una GPU RTX 3050 (640 px, 80 épocas, rotaciones y mosaico), que después se afinó con los datos nuevos (35 épocas, tasa "
      "de aprendizaje 0.0005). La v5 (30 épocas más) sumó 1,891 imágenes de RDD2022 tomadas desde dron, "
      "motocicleta y vehículos de Japón, corrigió 16 etiquetas tras una revisión a mano y agregó 2,468 variantes "
      "sintéticas de lluvia, noche, niebla y desenfoque de movimiento, porque el modelo se cargará en drones y vehículos "
      "que recorren las vías también en temporal. La v8 (15 épocas más desde la v5) sumó 515 fotos "
      "recientes de calles de Guadalajara (Mapillary), revisadas a mano: se confirmaron 191 objetos reales y los "
      "candidatos falsos quedaron como ejemplos negativos; ninguna foto es de las 133 instituciones reservadas. La versión integrada (v9) partió de la v8 con los mismos datos, "
      "30 épocas más y tasa de aprendizaje 0.0003, porque la v8 seguía mejorando en validación al terminar. Se probó un filtro adaptativo por imagen que mide brillo, contraste y nitidez y solo "
      "corrige lo que falta (estiramiento de contraste, gamma o enfoque), entrenando una versión con filtro y otra sin "
      "él. Ambos se evaluaron con "
      "las mismas 261 imágenes de prueba que ningún modelo vio. Para no sobreestimar el resultado, el umbral de cada "
      "clase se calibró buscando 0.9 de precisión en un conjunto de validación aparte (974 imágenes) y se dejó fijo para "
      "medir en la prueba, en cuatro climas simulados y en tres conjuntos reservados de dron, motocicleta y Japón. "
      "Arquitectura del detector (Figura 2): YOLO11s de Ultralytics es una red convolucional de una sola etapa con tres "
      "partes. El backbone extrae rasgos con bloques C3k2, una capa SPPF que reúne contexto a varias escalas y un bloque "
      "de atención espacial C2PSA. El cuello, de tipo FPN-PAN, combina mapas de 80 x 80, 40 x 40 y 20 x 20 celdas para "
      "ver objetos chicos y grandes. La cabeza, sin anclas, predice para cada una de las 8,400 posiciones una caja y la "
      "probabilidad de las 4 clases. Suma 181 capas y 9.4 millones de parámetros (5.4 en el backbone, 3.2 en el cuello y "
      "0.8 en la cabeza) y requiere 21.7 GFLOPs por imagen; se parte de pesos preentrenados en COCO y se exporta a ONNX "
      "(38 MB) para correr en CPU. "
      "También se midió el acierto por tamaño del objeto, luz de la imagen y fuente, para detectar sesgos. (6) Agentes. El Inspector detecta, el "
      "Clasificador asigna la dependencia, el Evaluador de impacto pondera tipo, tamaño y siniestralidad, el Vigía aplica "
      "el factor de clima y el Coordinador emite las órdenes con la regla Prioridad = Gravedad x Impacto x Riesgo x Clima "
      "(Figura 1). Las detecciones del modelo en escenas completas se tratan como candidatos: una persona las confirma o "
      "descarta en el tablero antes de que generen una orden. La Tabla 1 resume las fuentes."),
 70: ("Siniestralidad. 7,301 de los 11,568 accidentes (63%) ocurrieron a 200 m o menos de una institución. 1,569 "
      "instituciones (95%) tuvieron al menos uno y 322 (20%) al menos un atropellamiento cercano (Figura 3)."),
 73: ("La concentración de accidentes cerca de las instituciones respalda la decisión de priorizarlas, aunque mide "
      "exposición y no causa: las escuelas están repartidas por toda la ciudad y muchas se ubican sobre avenidas con "
      "tránsito intenso. Cambiar de FOMO a un detector de cajas fue lo que más mejoró el resultado: FOMO marca puntos y "
      "no distingue bien objetos largos como troncos o grietas. En el conjunto de prueba, la v9 acierta en 85 de cada 100 "
      "detecciones, pero todavía omite casos. En escenas completas de calle el panorama cambia: portones, pintura vial, tapas de "
      "registro y hasta las rejillas de ventilación del tablero del auto se confunden con alcantarillas, porque el modelo aprendió con fotos tomadas de cerca. Por eso el "
      "flujo incluye una validación humana antes de emitir la orden."),
 78: ("Ampliar el etiquetado de arbolado y de alcantarillas de riesgo con fotos propias, y entrenar con recortes de "
      "escenas de calle para reducir los falsos positivos. Montar una cámara con Raspberry Pi en camiones recolectores "
      "para actualizar la inspección cada semana. Llevar al Vigía de días a horas con los avisos de tormenta del SMN. "
      "Conectar las órdenes con Ciudapp y el 070, y sumar los datos del censo por AGEB para ponderar la población "
      "infantil de cada zona."),
 81: ("La hipótesis se confirma en parte. Con datos abiertos fue posible construir una línea base del entorno de las "
      "1,646 instituciones, emitir 494 órdenes priorizadas y explicadas y ajustar esas prioridades con 45 años de "
      "registros de lluvia y el pronóstico del SMN. El detector propio sirve, con validación humana, para "
      "rejillas pluviales, daño de pavimento y arbolado: en calles que no vio, 11 de cada 16 candidatos fueron reales. La "
      "meta de 0.9 de precisión se alcanzó en pavimento (0.91) y no en arbolado (0.83) ni en alcantarillas (0.67 y 0.73). La propuesta es viable para el municipio: no requiere un área nueva, usa "
      "las cuadrillas existentes y su costo de infraestructura estimado va de 100 a 500 dólares al mes, cifra que debe "
      "confirmarse en un piloto. Al año son de 1,200 a 6,000 dólares; con un tipo de cambio supuesto de 20 pesos por "
      "dólar, entre 24 mil y 120 mil pesos, menos del 0.003% de los 4,752 millones que el Presupuesto de Egresos 2026 de "
      "Guadalajara asigna a Servicios y Espacios Públicos, de un total de 13,016 millones (Crónica Jalisco, 2025). A eso "
      "se suma el equipo de cada vehículo (computadora, cámara, GPS y módem), que debe cotizarse para el piloto."),
 82: ("Limitaciones: cobertura de imágenes desigual (539 de 1,646 instituciones), fechas de captura variables, "
      "etiquetado hecho por el equipo sin revisión de especialistas, el límite de una hora de cómputo por entrenamiento "
      "del plan gratuito de Edge Impulse y condiciones de lluvia y noche simuladas, que falta validar con video real de "
      "dron o vehículo en temporal."),
 83: ("Declaración de uso de IA: Se utilizó un asistente de inteligencia artificial "
      "(Claude, de Anthropic) como apoyo para escribir código, procesar datos y redactar este documento. El equipo revisó "
      "los resultados y es responsable de su contenido. El prototipo, además, usa modelos de IA para detectar objetos y "
      "coordinar a los agentes."),
}
# --- Equidad: cobertura de imágenes por zona (zonas aproximadas por cercanía a su centro) ---------
sys.path.insert(0, BASE)
from instituciones_zonas import ZONAS, zona_de  # noqa: E402
_det = json.load(open(os.path.join(SAL, "detecciones_modelo.json"), encoding="utf-8"))
_insp = {r["institucion_id"] for r in leer(os.path.join(BASE, "entrenamiento", "mapillary", "imagenes.csv"))
         if r["archivo"] in _det}
_sin = {r["id"]: r for r in leer(os.path.join(BASE, "datos", "instituciones_siniestralidad.csv"))}
_ord = {}
for r in leer(os.path.join(SAL, "ordenes_trabajo.csv"), "utf-8-sig"):
    _ord[r["zona"]] = _ord.get(r["zona"], 0) + 1
_z = {}
for r in leer(os.path.join(BASE, "datos", "denue_gdl_instituciones.csv")):
    z = ZONAS[zona_de(float(r["latitud"]), float(r["longitud"]))][0]
    t = _z.setdefault(z, [0, 0, 0])
    t[0] += 1
    t[1] += r["id"] in _insp
    t[2] += int(_sin.get(r["id"], {}).get("accidentes_con_peaton_200m", 0) or 0)
TABLA3 = [("Zona", "Instit.", "Con fotos", "Órdenes")]
for z in sorted(_z):
    n, i, pe = _z[z]
    TABLA3.append((z.split(" · ")[1], f"{n}", f"{i} ({round(100 * i / n)}%)", f"{_ord.get(z, 0)}"))
_cob = sorted(((v[1] / v[0], k.split(" · ")[1]) for k, v in _z.items()))

RESULTADOS = [
    ("p", "Inspección. Con el detector v9 se analizaron 539 instituciones con imágenes disponibles. 373 presentaron "
          "hallazgos y el Coordinador generó 494 órdenes de trabajo: 271 de postes y cableado por revisar (Alumbrado Público y CFE), "
          "116 de escuelas o guarderías sin cruce peatonal visible en zonas con atropellamientos (Dirección de Movilidad), "
          "77 de árboles con ramas sobre cables (Parques y Jardines), 13 de rejillas pluviales para limpieza preventiva y "
          "2 de alcantarillas dañadas (SIAPA) y 15 de daño en el pavimento. El tablero clasifica 152 instituciones en nivel "
          "alto y 544 en nivel medio. Las zonas Minerva (127 órdenes) y Centro (125) concentran la mayor carga."),
    ("fig", "fig2_mapa_riesgo.png", "Figura 3. Instituciones por nivel de riesgo y accidentes de tránsito 2022-2024 en "
                                    "Guadalajara. Fuente: elaboración propia con DENUE e INEGI."),
    ("p", f"Clima. Los umbrales de lluvia diaria resultaron de {U['p90']} mm (percentil 90), {U['p95']} mm (percentil 95) "
          f"y {U['p99']} mm (percentil 99). De los {sum(ext)} días que superaron el percentil 95, {sum(ext[5:9])} "
          f"({pct_temporal}%) cayeron entre junio y septiembre (Figura 4). El pronóstico vigente al 11 de noviembre de "
          "2026 es normal, así que hoy ninguna prioridad cambia. En el escenario de evento extremo, las órdenes de "
          "alcantarillas y arbolado se multiplican por 1.6, las de postes por 1.4 y las de baches por 1.35. Al cruzar la "
          f"lluvia mensual con los accidentes, la correlación fue baja (r = {LLV['pearson_r']:.2f}) y el promedio mensual "
          f"en temporal apenas superó al del resto del año ({round(LLV['accidentes_promedio_temporal_jun_sep'])} contra "
          f"{round(LLV['accidentes_promedio_resto'])}). La lluvia, por sí sola, no explica los accidentes."),
    ("fig", "fig3_clima_smn.png", "Figura 4. Lluvia mensual promedio y días con lluvia extrema en Guadalajara, "
                                  "1981-2026. Fuente: elaboración propia con datos de SMN/CONAGUA."),
    ("p", "Detector. YOLO11s superó al mejor modelo FOMO (F1 0.33) desde su primera versión, y el filtro adaptativo "
          "aportó 6 puntos de F1 frente a la misma versión sin filtro. Un intento de afinado con tasa de aprendizaje 0.002 "
          "borró lo aprendido (F1 0.21) y se descartó. Al calibrar los umbrales fuera de la prueba, el F1 de la v4 quedó "
          "en 0.51 y no en el 0.60 medido antes con umbrales elegidos sobre la misma prueba; esa es la cifra honesta. La "
          "v5 mantiene F1 0.51 con precisión 0.86 en las 261 imágenes limpias, pero resiste mucho mejor las "
          "condiciones de operación (Tabla 2): en lluvia simulada pasó de 0.43 a 0.46, con desenfoque de movimiento de "
          "0.26 a 0.36, y en los conjuntos reservados de dron de 0.06 a 0.41, de motocicleta de 0.11 a 0.74 y de Japón "
          "de 0.31 a 0.51. Solo en niebla bajó (0.56 a 0.50). La precisión se mantuvo en 0.79 o más en todas las "
          "condiciones, y las falsas alarmas bajaron de 0.11 a 0.08 por imagen. El análisis de sesgos muestra lo que "
          "falta: en imágenes oscuras hay 0.29 falsas alarmas por imagen, contra 0.05 con luz normal; los baches pequeños "
          "(menos del 1% de la imagen) se encuentran mucho menos que los grandes (0.14 contra 0.51), y el arbolado sigue "
          "siendo la clase más débil (F1 0.38: acierta siempre que marca, pero encuentra solo 1 de cada 4 árboles). El "
          "modelo pesa 38 MB en formato ONNX y analiza una imagen en unos 0.1 s en el procesador de una laptop, sin GPU. "
          "Para medir en campo de forma honesta, se revisaron a mano las detecciones de la v5 en las imágenes de 133 "
          "instituciones reservadas: 5 de 17 candidatos fueron reales (pavimento 1 de 2, rejillas 2 de 7, árboles 2 de "
          "8), contra 10 de 20 de la v4. La v5 gana robustez en clima y en vista de dron, pero en cámara de auto sobre "
          "calles de Guadalajara deja de ver algunos objetos que la v4 encontraba y marca más árboles sin riesgo. Para recuperar "
          "acierto en calle se entrenó la v8 desde la v5 con 515 fotos recientes de Guadalajara revisadas a mano. En las "
          "mismas calles reservadas, 11 de sus 18 candidatos fueron reales (árboles 6 de 8, rejillas 4 de 7, pavimento 1 "
          "de 3), contra 10 de 17 de una versión intermedia (v7) que partió de menos fotos. Como la v8 seguía mejorando en validación, se "
          "entrenó la v9 desde ella con los mismos datos (30 épocas, tasa 0.0003). En las mismas calles reservadas acertó lo "
          "mismo con menos falsas alarmas: 11 de 16 candidatos reales (árboles 7 de 10, pavimento 3 de 4, rejillas 1 de 2). "
          "Su umbral calibrado para rejillas subió a 0.7, por lo que muestra menos rejillas: la mayoría de las que dejó de "
          "marcar eran falsas, pero perdió una real. En laboratorio (Tabla 2) mejora en 5 de 8 condiciones: F1 0.48 en "
          "imágenes limpias con precisión 0.85, 0.38 de noche, 0.45 en dron y 0.80 en motocicleta; baja con desenfoque de "
          "movimiento (0.33) y en Japón (0.46). Arbolado y alcantarillas de riesgo no llegan a 0.9 de precisión con una "
          "exhaustividad útil, así que su umbral se fijó en 0.5. La v9 es el modelo integrado al sistema. Los falsos positivos más comunes fueron rejillas de ventilación del "
          "tablero del auto reflejadas en el parabrisas. Entre las rejillas destacó una coladera con escombro junto a la "
          "banqueta (Figura 5)."),
    ("tab2",),
    ("fig", "fig4_evidencia_alcantarilla.jpg", f"Figura 5. Rejilla pluvial con escombro detectada por el modelo. Imagen de "
                                               f"Mapillary ({fecha_ev}), © {autor_ev}, CC BY-SA 4.0."),
    ("p", "Tablero en vivo. El tablero se sirve desde un servidor local que consulta fuentes oficiales con caché: el "
          "pronóstico municipal del SMN cada 15 minutos; la imagen GeoColor del satélite GOES y el radar de lluvia de "
          "RainViewer cada 5 minutos; los límites municipales del Marco Geoestadístico del INEGI, y los últimos sismos "
          "reportados por el SSN (Figura 6). Si el pronóstico llega a 60% de probabilidad de lluvia o a 5 mm, las órdenes "
          "de rejillas y alcantarillas se multiplican por 1.35 y las de pavimento por 1.2; con viento de 40 km/h o más, "
          "las de árboles y cableado se multiplican por 1.5. Son umbrales piloto, no criterios oficiales de alerta, y sin "
          "datos recientes del SMN no se aplica ningún ajuste. El 14 de noviembre de 2026 el pronóstico era despejado, así "
          "que ningún factor se activó. El satélite, el radar, los sismos y los límites de placas tectónicas del USGS son "
          "capas de contexto: no cambian prioridades ni predicen eventos. En el mismo tablero, un operador revisa la foto "
          "de cada uno de los 127 candidatos del detector y lo confirma o lo descarta; solo lo confirmado se vuelve orden."),
    ("fig", "fig5_tablero_clima.jpg", "Figura 6. Tablero en vivo: pronóstico SMN, imagen GOES y factores piloto de clima. "
                                      "Mapa base © Esri; límites © INEGI."),
    ("p", "Equidad de la cobertura. Las imágenes abiertas no cubren la ciudad por igual (Tabla 3). En "
          f"{_cob[-1][1]} hay imágenes del {round(100 * _cob[-1][0])}% de las instituciones; en {_cob[1][1]} y "
          f"{_cob[0][1]}, solo del {round(100 * _cob[1][0])}% y el {round(100 * _cob[0][0])}%. Como el sistema solo "
          "genera órdenes donde hay fotos, una zona con pocas imágenes recibe menos órdenes aunque sus fallas sean "
          "iguales o peores: el número de órdenes refleja, en parte, dónde se tomaron fotos y no solo dónde hay daño. "
          "Para no repetir la brecha que señala el reto, las primeras rutas de cámara propia deben ir a las zonas con "
          "menor cobertura. Las zonas se aproximaron por cercanía al centro de cada una."),
    ("tab3",),
]
DISCUSION_EXTRA = (
    "El arbolado fue la clase más débil: con la v5, menos de la mitad de los árboles marcados en calle tenía ramas "
    "sobre cables o tronco inclinado; con fotos de Guadalajara revisadas a mano, la v8 subió a 6 de 8 y la v9 "
    "a 7 de 10, con precisión de 0.83 en la prueba. Las rejillas en buen estado "
    "no son una falla: generan una orden de limpieza preventiva de baja gravedad antes del temporal. El hallazgo \"sin cruce visible\" depende de una o "
    "dos imágenes por institución y debe verificarse en campo. El SMN aporta algo que los reportes ciudadanos no pueden "
    "dar: saber con días de anticipación cuándo conviene adelantar la limpieza de alcantarillas o la poda. Su efecto "
    "sobre la prioridad se justifica por el daño físico que causan el agua y el viento, no por un aumento de "
    "accidentes, que en los datos mensuales fue mínimo. Por último, las imágenes de Mapillary van de 2019 a 2025, y una "
    "operación real necesita imágenes recientes.")
BIBLIO = [
    "Arya, D., Maeda, H., Ghosh, S. K., Toshniwal, D., & Sekimoto, Y. (2022). RDD2022: A multi-national image dataset for automatic road damage detection [Conjunto de datos]. figshare. https://doi.org/10.6084/m9.figshare.21431547",
    "Comisión Nacional del Agua, Servicio Meteorológico Nacional. (2026a). Base de Datos Climatológica Nacional: registro diario histórico, estaciones 14065 y 14066 [Conjunto de datos]. https://smn.conagua.gob.mx/es/climatologia/informacion-climatologica/informacion-estadistica-climatologica",
    "Comisión Nacional del Agua, Servicio Meteorológico Nacional. (2026b). Pronóstico meteorológico por municipio [Servicio web]. https://smn.conagua.gob.mx/es/web-service-api",
    "Crónica Jalisco. (2025, 18 de diciembre). Aprueban Presupuesto para Guadalajara 2026 por más de 13 mil millones de pesos. https://www.cronica.com.mx/jalisco/guadalajara/2025/12/18/guadalajara-aprueba-presupuesto-2026-por-mas-de-13-mil-millones-de-pesos/",
    "Edge Impulse. (2026). Edge Impulse Studio [Software]. https://studio.edgeimpulse.com",
    "Gobierno de Guadalajara. (s. f.). Segundo Plan de Acción Local de Gobierno Abierto. https://transparencia.guadalajara.gob.mx",
    "Instituto Nacional de Estadística y Geografía. (2025). Accidentes de tránsito terrestre en zonas urbanas y suburbanas (ATUS), bases georreferenciadas 2022-2024 [Conjunto de datos]. https://www.inegi.org.mx/programas/accidentes/",
    "Instituto Nacional de Estadística y Geografía. (2026a). Directorio Estadístico Nacional de Unidades Económicas (DENUE), 05/2026 [Conjunto de datos]. https://www.inegi.org.mx/app/descarga/",
    "Instituto Nacional de Estadística y Geografía. (2026b). Marco Geoestadístico, servicio web de áreas geoestadísticas [Servicio web]. https://gaia.inegi.org.mx/wscatgeo/v2/geo",
    "Jocher, G., & Qiu, J. (2024). Ultralytics YOLO11 (Versión 11) [Software]. AGPL-3.0. https://github.com/ultralytics/ultralytics",
    "Mapillary. (2026). Mapillary API v4 e imágenes de calle, CC BY-SA 4.0. https://www.mapillary.com/developer",
    "National Oceanic and Atmospheric Administration, NESDIS. (2026). GOES GeoColor, últimas 24 horas [Servicio de imágenes]. https://satellitemaps.nesdis.noaa.gov/arcgis/rest/services/MERGEDGC_Last_24hr/ImageServer",
    "RainViewer. (2026). Weather Maps API [Servicio web]. https://www.rainviewer.com/api.html",
    "Servicio Sismológico Nacional. (2026). Últimos sismos [Fuente RSS]. Universidad Nacional Autónoma de México. http://www.ssn.unam.mx/rss/ultimos-sismos.xml",
    "U.S. Geological Survey. (s. f.). Tectonic plate boundaries [Servicio de mapas]. https://earthquake.usgs.gov/arcgis/rest/services/eq/map_plateboundaries/MapServer",
]
TABLA1 = [("Fuente", "Periodo y cobertura", "Uso en el sistema"),
          ("DENUE, INEGI (catálogo #09)", "05/2026; municipal, Guadalajara", "Inventario de 1,646 instituciones (problema y prioridad)"),
          ("Accidentes de tránsito georreferenciados (ATUS), INEGI (catálogo #08)", "2022-2024; municipal, Guadalajara",
           "11,568 accidentes; riesgo vial a 200 m (problema y prioridad)"),
          ("Series de lluvia y eventos extremos, SMN/CONAGUA (catálogo #45)", "1981-2026; estaciones 14065 y 14066, Guadalajara",
           "Umbrales extremos y temporada (diseño del Vigía)"),
          ("Pronóstico por municipio, SMN/CONAGUA", "48 h, vigente; municipal", "Factor de clima en el tablero (complementaria)"),
          ("Mapillary, CC BY-SA 4.0", "2019-2025; alrededor de las instituciones",
           "1,130 imágenes de inspección y 515 recientes para entrenar (complementaria)"),
          ("GOES (NOAA), RainViewer, SSN, USGS y Marco Geoestadístico INEGI", "En vivo; regional y nacional",
           "Capas de contexto del tablero (complementarias)"),
          ("RDD2022, CC BY 4.0", "2022; varios países", "3,161 imágenes de daño de pavimento (complementaria)"),
          ("Etiquetado propio", "2026; Guadalajara", "475 alcantarillas, 265 árboles, 116 escenas y 191 objetos en fotos recientes")]
TABLA2 = [("Condición de prueba", "v4", "v5 (clima)", "v8 (GDL)", "v9 (integrada)"),
          ("Limpia, 261 imágenes", "0.51 (0.84)", "0.51 (0.86)", "0.46 (0.81)", "0.48 (0.85)"),
          ("Lluvia simulada", "0.43 (0.81)", "0.46 (0.88)", "0.42 (0.85)", "0.42 (0.86)"),
          ("Noche simulada", "0.39 (0.83)", "0.41 (0.83)", "0.36 (0.80)", "0.38 (0.88)"),
          ("Niebla simulada", "0.56 (0.80)", "0.50 (0.83)", "0.49 (0.83)", "0.48 (0.85)"),
          ("Desenfoque de movimiento", "0.26 (0.66)", "0.36 (0.79)", "0.35 (0.78)", "0.33 (0.81)"),
          ("Dron, 72 imágenes reservadas", "0.06 (0.20)", "0.41 (0.76)", "0.43 (0.92)", "0.45 (0.86)"),
          ("Motocicleta, 127 reservadas", "0.11 (1.00)", "0.74 (1.00)", "0.78 (1.00)", "0.80 (1.00)"),
          ("Japón, 343 reservadas", "0.31 (0.73)", "0.51 (0.95)", "0.49 (0.93)", "0.46 (0.93)")]

# --- Documento --------------------------------------------------------------------------------
d = docx.Document(SRC)
ps = d.paragraphs


def poner(p, t):
    for h in p._p.findall(qn("w:hyperlink")):
        p._p.remove(h)
    for r in p.runs[1:]:
        r.text = ""
    (p.runs[0] if p.runs else p.add_run()).text = t


def despues(ancla, t="", molde=None):
    nuevo = copy.deepcopy((molde or ancla)._p)
    ancla._p.addnext(nuevo)
    p = Paragraph(nuevo, ancla._parent)
    poner(p, t)
    return p


def figura(ancla, archivo, pie):
    p = despues(ancla)
    poner(p, "")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.runs[0].add_picture(os.path.join(FIG, archivo), width=ANCHO)
    c = despues(p, pie)
    for r in c.runs:
        r.italic, r.font.size = True, Pt(8)
    return c


def tabla(ancla, filas, titulo):
    t_p = despues(ancla, titulo)
    for r in t_p.runs:
        r.italic, r.font.size = True, Pt(8)
    t = d.add_table(rows=len(filas), cols=len(filas[0]))
    try:
        t.style = d.styles["Table Grid"]
    except KeyError:
        pass
    for i, fila in enumerate(filas):
        for j, v in enumerate(fila):
            cel = t.cell(i, j)
            cel.text = v
            for r in cel.paragraphs[0].runs:
                r.font.size, r.bold = Pt(8), i == 0
    t_p._p.addnext(t._tbl)
    vacio = copy.deepcopy(ancla._p)
    t._tbl.addnext(vacio)
    p = Paragraph(vacio, ancla._parent)
    poner(p, "")
    return p


for i, t in TXT.items():
    poner(ps[i], t)

# Bibliografía (86-90 en el formato, el resto se inserta después)
for k, i in enumerate(range(86, 91)):
    poner(ps[i], BIBLIO[k])
ult = ps[90]
for ref in BIBLIO[5:]:
    ult = despues(ult, ref)

# Discusión: segundo párrafo
despues(ps[73], DISCUSION_EXTRA)

# Resultados: párrafos, figuras y tabla después del párrafo 70
ult = ps[70]
for item in RESULTADOS:
    if item[0] == "p":
        ult = despues(ult, item[1], molde=ps[70])  # formato de párrafo normal, no el del pie de figura
    elif item[0] == "fig":
        ult = figura(ult, item[1], item[2])
    elif item[0] == "tab3":
        ult = tabla(ult, TABLA3, "Tabla 3. Cobertura de imágenes y órdenes por zona de Guadalajara (DENUE, Mapillary e INEGI).")
    elif item[0] == "tab2":
        ult = tabla(ult, TABLA2, "Tabla 2. F1 general (y precisión) por condición, con umbrales calibrados fuera de la prueba.")

# Metodología: tabla de fuentes y figura de arquitectura después del párrafo 67
ult = tabla(ps[67], TABLA1, "Tabla 1. Fuentes de datos: periodo, cobertura y uso. Las tres primeras son del catálogo oficial del Hackathon.")
ult = figura(ult, "fig1_arquitectura.png", "Figura 1. Flujo de los cinco agentes, de los datos a la orden de trabajo.")
figura(ult, "fig2_arquitectura_yolo.png", "Figura 2. Arquitectura del detector YOLO11s v9, con las cifras medidas sobre "
                                          "sus pesos.")

# Anexos
poner(ps[102], "Anexo A. Tablero de operación (entregables/tablero/index.html), tablero en vivo con clima, satélite y "
               "sismos (entregables/tablero_vivo, se abre con iniciar_tablero.bat), código del prototipo y proyecto "
               "público de Edge Impulse (ID 1161125).")
for i in range(103, 138):
    if i < len(ps):
        poner(ps[i], "")
poner(ps[104], "Anexo B. El proyecto no involucra investigación con seres humanos, animales vertebrados ni agentes "
               "peligrosos.")
d.save(OUT)

# Texto plano para revisión de estilo
dd = docx.Document(OUT)
with open(os.path.join(FIG, "texto_reporte.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(p.text for p in dd.paragraphs if len(p.text) > 60))
print("reporte:", OUT, "| palabras del resumen:", len(TXT[30].split()))
