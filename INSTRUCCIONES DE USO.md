# SIVIA · Entregable técnico

Hackathon Jalisco Internacional 2026 · Reto 01 Ciudades Inteligentes · Guadalajara, Jalisco.

Sistema de cinco agentes que inspecciona el entorno de 1,646 escuelas, guarderías y hospitales con
imágenes de calle y un detector YOLO11s, y emite órdenes de trabajo priorizadas por dependencia.

## 1. Probarlo en 1 minuto (sin instalar nada)

- **Tablero de operación:** abre `entregables/tablero/index.html` en Chrome o Edge.
- **Tablero en vivo** (clima SMN, satélite, radar, sismos): necesita Python 3 e internet.
  Doble clic en `entregables/tablero_vivo/iniciar_tablero.bat` o ejecuta
  `python entregables/tablero_vivo/smn_server.py` y entra a `http://127.0.0.1:8000/index.html`.

## 2. Correr los agentes

Python 3.12 en Windows, macOS o Linux (solo CPU):

```
pip install -r requirements.txt
cd prototipo
python agente/vigia_smn.py --sin-red      # Vigía: umbrales de lluvia y pronóstico (agente/salida/clima_smn.json)
python agente/coordinador.py              # Clasificador + Evaluador + Coordinador: órdenes de trabajo
python agente/coordinador.py --clima extremo   # escenario de evento extremo
python agente/tablero_vivo.py             # vuelve a armar el tablero en vivo
python agente/reporte.py                  # regenera el reporte científico (necesita el formato .docx oficial)
```

El Coordinador parte de las detecciones que el Inspector ya calculó con el modelo v9
(`agente/salida/detecciones_yolo.json`). Para volver a correr el Inspector hacen falta las imágenes
de Mapillary (no se incluyen por tamaño y licencia):

```
powershell -File prototipo/entrenamiento/bajar_mapillary.ps1      # pide tu token de Mapillary sin guardarlo
python agente/inspector.py --modelo entrenamiento/modelo/entorno_seguro_v9_yolo11s.onnx --mixto --umbral-guardar 0.25 --salida agente/salida/detecciones_yolo.json
python agente/tablero.py                  # tablero de operación con las imágenes reducidas
```

## 2b. Plataforma con base de datos y bucket

`prototipo/plataforma/` lleva la línea base a PostgreSQL y las evidencias a un bucket S3:

- `esquema.sql`: instituciones (DENUE + ATUS), imágenes, detecciones, candidatos, órdenes con su estado,
  bitácora de cambios, pronósticos SMN y la vista `cobertura_zona` (indicador de cobertura por zona).
- `cargar_bd.py`: carga o actualiza todo y conserva lo que las personas ya validaron o asignaron.
- `servidor.py`: el servidor del tablero en vivo con API (`/api/candidatos`, `/api/ordenes`,
  `/api/evidencia/<archivo>` con liga firmada del bucket). Sin base, funciona como antes.
- `subir_evidencias.py`: sube las fotos de evidencia al bucket y anota su llave.
- `iniciar_con_bd.ps1`: pide las credenciales ocultas, las usa solo en esa ventana y las borra al terminar.
  Ninguna credencial se guarda en archivos ni viaja en este paquete.

```
powershell -File prototipo/plataforma/iniciar_con_bd.ps1 -Accion cargar
powershell -File prototipo/plataforma/iniciar_con_bd.ps1 -Accion subir
powershell -File entregables/tablero_vivo/iniciar_con_bd.ps1
```

## 3. Qué hay en cada carpeta

| Carpeta | Contenido |
|---|---|
| `prototipo/agente/` | Inspector, Coordinador (con Clasificador y Evaluador), Vigía, tableros, centro de control y reporte |
| `prototipo/agente/colab_b/` | Plantilla y servidor del tablero en vivo (SMN, GOES, radar, INEGI, SSN, USGS) |
| `prototipo/datos/` | Datos procesados de los datasets del catálogo: DENUE (#09), ATUS (#08) y SMN (#45) |
| `prototipo/agente/salida/` | Detecciones del modelo, hallazgos, órdenes de trabajo y resumen de la línea base |
| `prototipo/entrenamiento/` | Scripts de datos, entrenamiento, evaluación sin sesgo y análisis de sesgos |
| `prototipo/entrenamiento/modelo/` | Modelo integrado `entorno_seguro_v9_yolo11s.onnx` (38 MB), umbrales y todas las evaluaciones |
| `prototipo/entrenamiento/campo/` | Revisión a mano de candidatos y prueba en calles reservadas |
| `entregables/` | Los dos tableros, listos para abrir |

## 4. Modelo

- YOLO11s (Ultralytics), 4 clases: alcantarilla de riesgo, rejilla pluvial, árbol de riesgo y daño de pavimento.
- Entrada 640 x 640 px; ONNX; unos 0.1 s por imagen en el procesador de una laptop, sin GPU.
- Umbrales por clase en `entorno_seguro_v9_yolo11s.umbrales.json`, calibrados en validación buscando
  0.9 de precisión (arbolado y alcantarillas de riesgo no la alcanzan y usan 0.5).
- Precisión 0.85 en 261 imágenes no vistas y 0.86 en vista de dron. En calles reservadas de
  Guadalajara, 11 de 16 candidatos fueron reales.
- Reentrenar: `preparar_yolo_v8.py` y `entrenar_yolo.py` (la v9 sigue entrenando la v8 con el mismo dataset) (ver la ficha técnica). Se necesitan
  `ultralytics` y una GPU.

## 5. Qué está simulado y qué falta

- **Las imágenes son de Mapillary (2019-2025)**, no de una cámara propia. La cámara en camiones
  municipales es la propuesta; `agente/camara_simulada.py` reproduce un recorrido con esas fotos y
  así se debe presentar.
- **Lluvia, noche, niebla y movimiento** del entrenamiento son sintéticos.
- **Los factores de clima** del tablero (lluvia ≥ 60% o 5 mm; viento ≥ 40 km/h) son umbrales piloto,
  no criterios oficiales de alerta.
- **Las detecciones son candidatas**: una persona confirma cada una antes de que sea orden.

## 6. Licencias y créditos

Código del equipo. Ultralytics YOLO11 es AGPL-3.0 (un despliegue cerrado necesita licencia
empresarial). Imágenes © Mapillary y sus autores, CC BY-SA 4.0. RDD2022 (Arya et al., 2022), CC BY 4.0.
DENUE y ATUS: INEGI. Clima: SMN/CONAGUA. Satélite: NOAA/NESDIS. Radar: RainViewer. Sismos: SSN/UNAM.
Placas: USGS. Mapa base © Esri. Se usó un asistente de IA (Claude, de Anthropic) para escribir código,
procesar datos y redactar la documentación; el equipo revisó los resultados.
