"""Genera el Manual de Usuario (MU): entregables/MU_Manual_de_Usuario_SIVIA.docx

Uso:  python agente/manual_usuario.py
"""
import json
import os

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAIZ = os.path.dirname(BASE)
FIG = os.path.join(RAIZ, "entregables", "figuras")
OUT = os.path.join(RAIZ, "entregables", "MU_Manual_de_Usuario_SIVIA.docx")
N = "SIVIA"
R = json.load(open(os.path.join(BASE, "agente", "salida", "resumen.json"), encoding="utf-8"))

d = docx.Document()
st = d.styles["Normal"]
st.font.name, st.font.size = "Calibri", Pt(11)
for s in d.sections:
    s.left_margin = s.right_margin = Cm(2.2)


def h(t, n=1):
    q = d.add_heading(t, level=n)
    for r in q.runs:
        r.font.color.rgb = RGBColor(0x1f, 0x3d, 0x35)


def p(t, it=False, size=None):
    q = d.add_paragraph()
    r = q.add_run(t)
    r.italic = it
    if size:
        r.font.size = Pt(size)
    return q


def lista(items, estilo="List Bullet"):
    for i, t in enumerate(items, 1):
        if estilo == "List Number":  # numeración propia: Word continúa la de la lista anterior
            q = d.add_paragraph(f"{i}. {t}")
            q.paragraph_format.left_indent = Cm(0.6)
        else:
            d.add_paragraph(t, style=estilo)


def fig(archivo, pie):
    q = d.add_paragraph()
    q.alignment = WD_ALIGN_PARAGRAPH.CENTER
    q.add_run().add_picture(os.path.join(FIG, archivo), width=Cm(16))
    p(pie, it=True, size=9)


def tabla(filas):
    t = d.add_table(rows=len(filas), cols=len(filas[0]))
    t.style = "Light Grid Accent 1"
    for i, f in enumerate(filas):
        for j, v in enumerate(f):
            c = t.cell(i, j)
            c.text = v
            for r in c.paragraphs[0].runs:
                r.font.size, r.bold = Pt(10), i == 0
    d.add_paragraph()


# Identificador gráfico del Hackathon en el encabezado de cada página (lo pide el kit del reto)
_logo = os.path.join(RAIZ, "entregables", "figuras", "logos", "hackathon_jalisco_2026.jpg")
if os.path.exists(_logo):
    _hp = d.sections[0].header.paragraphs[0]
    _hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _hp.add_run().add_picture(_logo, width=Cm(8))

d.add_heading(f"{N}: manual de usuario", 0)
p("Hackathon Jalisco Internacional 2026 · Reto 01 Ciudades Inteligentes · Guadalajara, Jalisco", it=True)

h("1. Qué es y quién lo usa")
p(f"{N} revisa con inteligencia artificial las imágenes de calle alrededor de 1,646 escuelas, guarderías y hospitales "
  "de Guadalajara, detecta fallas (árboles con ramas sobre cables, baches, rejillas pluviales, alcantarillas abiertas, "
  "postes y falta de cruce peatonal) y genera órdenes de trabajo con prioridad y explicación para cada dependencia.")
tabla([["Usuario", "Qué hace en el sistema"],
       ["Operador de la Coordinación de Servicios Públicos",
        "Revisa los candidatos del modelo, confirma o descarta y reparte las órdenes"],
       ["Dependencia (Parques y Jardines, Pavimentos, Movilidad, Alumbrado / CFE, SIAPA)",
        "Ve sus órdenes por prioridad, con foto, dirección y ruta sugerida; imprime la orden"],
       ["Mandos y planeación", "Consulta la línea base, el clima y los indicadores en la pestaña Análisis"]])
p(f"Línea base actual: {R['instituciones_inspeccionadas']} instituciones inspeccionadas, "
  f"{R['instituciones_con_hallazgos']} con hallazgos y {R['hallazgos']} órdenes de trabajo.")

h("2. Requisitos")
lista(["Una computadora con Windows, macOS o Linux y un navegador actual (Chrome o Edge).",
       "Internet, para el mapa base y las capas de clima, satélite y sismos.",
       "Python 3 solo para el tablero en vivo y para actualizar los datos (no hace falta instalar paquetes para el "
       "tablero en vivo)."])

h("3. Abrir el sistema")
h("Tablero en vivo (recomendado)", 2)
lista(["Abre la carpeta entregables/tablero_vivo.",
       "Doble clic en iniciar_tablero.bat. Si Windows pregunta, permite que Python se ejecute.",
       "Se abre el navegador en http://127.0.0.1:8000/index.html. Deja abierta la ventana negra mientras lo uses.",
       "Para cerrar, presiona Ctrl+C en esa ventana."], "List Number")
p("Si no tienes Python, abre index.html con doble clic: funcionan el mapa, las órdenes y la validación, pero no el "
  "clima en vivo, el satélite, el radar ni los sismos.")
h("Tablero de operación", 2)
p("Abre entregables/tablero/index.html con doble clic. Incluye el mapa de riesgo de las 1,646 instituciones, el mapa de "
  "calor de accidentes, las órdenes con su estado (pendiente, asignada, en atención, resuelta), la orden imprimible y "
  "la reproducción de un recorrido grabado del vehículo. Ese recorrido es una simulación con fotos de Mapillary.")

h("4. Recorrido por el tablero en vivo")
p("Arriba están los indicadores: instituciones en inventario, hallazgos en el tablero, órdenes generadas, prioridad "
  "alta y media, candidatos por validar y estado de la conexión con el SMN. A la izquierda está el mapa y a la derecha "
  "cinco pestañas.")
fig("fig6_tablero_ordenes.jpg", "Figura 1. Pestaña Órdenes: cada punto es una institución; el color indica la prioridad "
                                "(rojo alta, amarillo media, verde baja).")
h("Órdenes", 2)
lista(["La lista está ordenada de mayor a menor prioridad. Escribe en el buscador un lugar, un tipo de daño o una "
       "dependencia.",
       "Elige una dependencia en el selector para ver solo sus órdenes y su ruta sugerida (línea punteada en el mapa, "
       "hasta 10 paradas cercanas desde la más urgente).",
       "Haz clic en una orden para centrar el mapa; en el mapa, haz clic en un punto para ver su foto de evidencia, la "
       "explicación de la prioridad y los accidentes a 200 m."])
h("Validación IA", 2)
fig("fig7_tablero_validacion.jpg", "Figura 2. Pestaña Validación IA: cada candidato del modelo con su foto, clase y "
                                   "confianza.")
lista(["Mira la foto antes de decidir. La confianza indica qué tan seguro está el modelo de la clase, no qué tan grave "
       "es el daño.",
       "Confirmar: es real (por ejemplo, ramas que tocan los cables o una rejilla tapada). Descartar: no lo es (sombras, "
       "tapas redondas de registro, reflejos del tablero del auto).",
       "Filtra por Pendientes, Confirmados o Descartados. Lo que decides se guarda en este navegador.",
       "Exportar confirmados descarga un CSV. Con él se vuelven a calcular las órdenes (sección 6). Un candidato no se "
       "convierte en orden hasta que alguien lo confirma."])
h("Clima SMN", 2)
fig("fig5_tablero_clima.jpg", "Figura 3. Pestaña Clima SMN: pronóstico oficial para Guadalajara, imagen del satélite "
                              "GOES y factores de clima.")
lista(["El tablero consulta el pronóstico del SMN cada 15 minutos y lo muestra como un punto sobre Guadalajara.",
       "Si se pronostica lluvia de 60% o más, o 5 mm o más, suben las órdenes de rejillas y alcantarillas (x1.35) y de "
       "pavimento (x1.2). Con viento de 40 km/h o más suben árboles y cableado (x1.5).",
       "Arriba a la derecha puedes elegir Pronóstico SMN, Extremo manual (simula una tormenta para planear) o Sin clima.",
       "En Capas del mapa puedes activar el radar de lluvia, que reproduce las últimas 2 horas junto con el satélite."])
h("Sismos SSN y Análisis", 2)
lista(["Sismos SSN muestra los últimos sismos reportados por el Servicio Sismológico Nacional y los límites de placas. "
       "Es solo monitoreo: no predice sismos ni cambia prioridades.",
       "Análisis resume la prioridad promedio, el avance de la revisión humana, los hallazgos por categoría y dos series "
       "de Jalisco: accidentes (INEGI) y lluvia anual (SMN)."])

h("5. Flujo de trabajo sugerido")
lista(["Cada mañana, el operador abre el tablero en vivo y revisa la pestaña Clima SMN.",
       "Revisa los candidatos nuevos en Validación IA y exporta los confirmados.",
       "Actualiza las órdenes (sección 6) y cada dependencia filtra las suyas y sigue la ruta sugerida.",
       "Antes del temporal (junio a septiembre) se atienden primero rejillas, alcantarillas y árboles de riesgo."],
      "List Number")

h("6. Actualizar los datos (personal técnico)")
p("Desde la carpeta prototipo, con Python 3.12 y pip install -r requirements.txt:", size=10)
for t in ["python agente/vigia_smn.py                 # pronóstico y umbrales de lluvia",
          "python agente/coordinador.py               # órdenes de trabajo priorizadas",
          "python agente/tablero_vivo.py              # vuelve a armar el tablero en vivo",
          "python agente/inspector.py --modelo entrenamiento/modelo/entorno_seguro_v9_yolo11s.onnx --mixto "
          "--umbral-guardar 0.25 --salida agente/salida/detecciones_yolo.json   # requiere imágenes nuevas"]:
    q = d.add_paragraph()
    r = q.add_run(t)
    r.font.name, r.font.size = "Consolas", Pt(8.5)
p("El detalle de cada comando está en LEEME.md del entregable técnico.")
h("Validaciones compartidas con base de datos", 2)
p("Sin base de datos, cada navegador guarda sus propias validaciones. Con base de datos, lo que un operador confirma "
  "o descarta queda en PostgreSQL y lo ven todos, junto con el estado de cada orden y una bitácora de cambios. Para "
  "abrirlo así, en PowerShell dentro de entregables/tablero_vivo ejecuta iniciar_con_bd.ps1: pide la cadena de "
  "conexión sin mostrarla, la usa solo en esa ventana y la borra al cerrar. Las fotos de evidencia pueden guardarse "
  "en un bucket S3 con plataforma/subir_evidencias.py.")

h("7. Limitaciones")
lista(["Las fotos son de Mapillary (2019 a 2025), no de una cámara propia, y cubren 539 de las 1,646 instituciones. "
       "Algunas fallas pueden ya estar reparadas o ser nuevas.",
       "El detector acierta 81 de cada 100 veces en fotos de prueba, pero en calles que no vio 11 de 18 candidatos "
       "fueron reales, y todavía omite casos. Por eso toda detección se confirma a mano.",
       "Árboles: el modelo marca la copa; confirma solo si hay ramas sobre cables o el tronco está inclinado.",
       "Postes y falta de cruce peatonal vienen de las detecciones de Mapillary y de los accidentes del INEGI; se "
       "verifican en campo.",
       "Los factores de clima son umbrales piloto, no alertas oficiales. Ante una emergencia, sigue a Protección Civil.",
       "Las decisiones de validación se guardan en el navegador del operador. En un piloto se guardarían en un servidor "
       "del municipio.",
       "El recorrido del vehículo en el tablero de operación es una simulación con fotos de Mapillary."])

h("8. Privacidad y créditos")
p("El sistema no usa datos personales. Las fotos de calle pueden mostrar personas o placas: en un despliegue real se "
  "difuminarían antes de guardarlas. Fuentes: DENUE y ATUS (INEGI), SMN/CONAGUA, NOAA/NESDIS (GOES), RainViewer, "
  "SSN/UNAM, USGS, mapa base © Esri, imágenes © Mapillary y sus autores (CC BY-SA 4.0). Se usó un asistente de IA "
  "(Claude, de Anthropic) para escribir código y redactar este manual; el equipo revisó el contenido.", size=10)

d.save(OUT)
print("manual:", OUT)
