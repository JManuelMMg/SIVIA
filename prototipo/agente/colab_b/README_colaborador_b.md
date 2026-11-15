# Entorno Seguro GDL — Colaborador B

Evaluador de impacto + Vigía + Coordinador + Tablero. Solo usa Python estándar (no hay que instalar nada).

## Probar hoy con datos de prueba
```
python generar_prueba.py --salida datos_prueba
python priorizar.py --hallazgos datos_prueba/hallazgos_prueba.csv \
  --denue datos_prueba/denue_prueba.csv --ageb datos_prueba/ageb_prueba.csv \
  --accidentes datos_prueba/accidentes_prueba.csv --salida resultados_b
```
Para ver el mapa y conectar el SMN, el satélite GOES, el radar y las placas tectónicas, sirve el tablero por HTTP. En Windows puedes iniciar todo con doble clic en `iniciar_tablero.bat`; el script abre el tablero cuando el servidor ya está listo y deja la consola abierta para mostrar el estado:

```powershell
python generar_prueba.py --salida datos_prueba
python priorizar.py --hallazgos datos_prueba/hallazgos_prueba.csv `
  --denue datos_prueba/denue_prueba.csv --ageb datos_prueba/ageb_prueba.csv `
  --accidentes datos_prueba/accidentes_prueba.csv --salida resultados_b
python smn_server.py
```

Si prefieres la terminal, ejecuta `python smn_server.py` (o `py -3 smn_server.py`) desde la carpeta del proyecto. El servidor abre el tablero en `http://127.0.0.1:8000/resultados_b/tablero.html`; deja la consola abierta mientras lo usas y presiona `Ctrl+C` para detenerlo. El mapa, el pronóstico y las capas remotas requieren internet. Si no tienes Python instalado, `iniciar_tablero.bat` te lo indicará.

## Servicio Meteorológico Nacional (SMN)

`smn_server.py` consulta el servicio oficial **Pronóstico por municipios a 48 horas** de CONAGUA, filtra Guadalajara, Jalisco, y expone los datos al tablero mediante `/api/clima`. El servidor conserva una caché local durante 15 minutos para evitar consultas repetidas. El panel muestra temperatura, probabilidad y cantidad de lluvia, viento, ráfagas y humedad; el tablero vuelve a consultar cada 15 minutos y actualiza el punto del pronóstico y los puntajes visibles en el mapa sin recargar la página. Cuando la pestaña Clima está abierta, revisa la hora GOES y la metadata del radar cada 5 minutos; la capa de radar solo se descarga visualmente cuando está activada. Al volver a la ventana o recuperar la conexión, consulta de nuevo las fuentes. Se incluye el enlace de atribución al SMN.

El pronóstico también se representa como un punto de Guadalajara en el mapa. Al abrir la pestaña **Clima SMN**, el tablero activa la imagen GOES reciente y el punto del pronóstico SMN; el control **Capas** permite apagarlos o sumar el radar. Al salir de esa pestaña, oculta las capas meteorológicas.

### Capas meteorológicas y tectónicas del mapa

- **Mapa base Satélite · Esri:** el tablero inicia centrado en Guadalajara, limita el alejamiento para evitar copias repetidas del mundo y conserva las capas de topónimos y vialidades. Al abrir **Clima SMN**, la vista regresa al encuadre regional de Guadalajara si está demasiado alejada o en otro punto; desde **Capas del mapa** puedes cambiar a **Calles · Esri**. La capa GOES solicita imagen PNG con transparencia para ocultar píxeles negros sin datos.
- **Límites nacionales y nombres de lugares · Esri:** referencia transparente encima de la imagen satelital con fronteras nacionales y nombres de localidades. **Calles y vialidades · Esri** añade el trazado y los nombres de carreteras/calles. Ambas capas comienzan activas y se pueden ocultar desde **Capas del mapa**.
- **Límite estatal y límites municipales de Jalisco · INEGI:** geometrías del Marco Geoestadístico de INEGI cargadas mediante `/api/limites` y guardadas en caché por 24 horas. El límite estatal se dibuja en turquesa y las divisiones municipales en amarillo; los nombres municipales aparecen al acercar el mapa. Son referencias geoestadísticas, no un deslinde legal de límites políticos.
- **Satélite GOES GeoColor · NOAA/NESDIS:** el tablero consulta `/api/satelite/historial`, que lista las horas de adquisición disponibles en el archivo móvil de 24 horas. Al reproducir RainViewer, el sistema asocia cada fotograma de radar con la escena GOES más cercana, precarga esas imágenes y cambia ambas capas juntas a 1 fotograma por segundo. NOAA publica escenas cada 10–15 minutos, por lo que una imagen de nubes puede repetirse durante varios fotogramas del radar. Al desactivar el radar queda visible la escena GOES más reciente. Esto representa observaciones históricas, no video continuo ni pronóstico; se conserva visible la atribución a NOAA/NESDIS.
- **Pronóstico municipal · SMN:** punto con las condiciones del pronóstico vigente para Guadalajara. Es un pronóstico municipal, no una observación distinta para cada calle. La [documentación oficial del SMN](https://smn.conagua.gob.mx/es/web-service-api) describe sus datos por municipio y actualización aproximada cada 75 minutos.
- **Radar de lluvia · RainViewer:** al activar la casilla precarga los mosaicos y las escenas GOES históricas del mismo encuadre y reproduce precipitación y nubosidad sincronizadas a 1 fotograma por segundo con transición entre cuadros. Para cada hora RainViewer se usa la adquisición GOES disponible más próxima; si no hay escena en el intervalo del archivo, se conserva la última nube cargada. En el encuadre nacional limita la capa a México y ajusta el zoom nativo para mantener la precarga del radar por debajo de 85 solicitudes; al acercar el mapa puede usar mayor detalle. RainViewer entrega hasta 2 horas de observaciones en pasos aproximados de 10 minutos, no un pronóstico/nowcast. Solo se conserva la paleta Universal Blue (ID `2`). La escala dBZ es orientativa, no equivale directamente a mm/h ni a una alerta oficial. La cobertura depende de los radares disponibles. Se muestra atribución a [RainViewer](https://www.rainviewer.com/api.html); su uso gratuito está dirigido a proyectos personales, educativos y comunitarios pequeños, sin garantía de disponibilidad.
- **Límites de placas · USGS:** al activar la capa o abrir **Sismos SSN**, el mapa consulta la geometría regional de límites tectónicos por `/api/placas`; se guarda en caché por 24 horas porque describe un modelo geológico de referencia, no datos que cambien minuto a minuto. La fuente es el servicio [USGS Tectonic Plate Boundaries](https://earthquake.usgs.gov/arcgis/rest/services/eq/map_plateboundaries/MapServer).

Estas capas son informativas. El radar es precipitación detectada y reciente, no un pronóstico ni una alerta; los límites tectónicos no señalan cuándo ocurrirá un sismo ni representan por sí solos el riesgo de una colonia.

## Monitoreo sísmico (SSN)

La pestaña **Sismos SSN** consulta los últimos reportes del [feed oficial del Servicio Sismológico Nacional](http://www.ssn.unam.mx/rss/ultimos-sismos.xml) mediante el endpoint local `/api/sismos`. El tablero consulta este endpoint automáticamente cada 5 minutos y el servidor conserva la respuesta durante 5 minutos; al volver a la pestaña o recuperar la conexión, solicita los datos de nuevo sin recargar la página. La capa de epicentros se actualiza con cada respuesta y solo dibuja reportes con coordenadas válidas. Si la fuente falla, puede mostrar la última respuesta guardada hasta por 6 horas. El [catálogo sísmico oficial](http://www2.ssn.unam.mx:8080/catalogo/) queda disponible desde la pestaña.

Esta función es de monitoreo de reportes observados para México. **No predice sismos, no es una alerta oficial, no calcula riesgo por colonia y no aumenta las prioridades del mapa.** El RSS puede omitir coordenadas estructuradas en algunos reportes; esos eventos permanecen en la lista, pero no se inventa una ubicación para dibujarlos en el mapa. El [SSN explica que no opera un sistema de alerta sísmica](https://www.ssn.unam.mx/sismicidad/reportes-especiales/2024/SSNMX_rep_esp_20240926_CuencaDeMex_M29.pdf); para emergencias se deben seguir las indicaciones de Protección Civil y autoridades locales. La pestaña requiere abrir el tablero a través de `smn_server.py` y tener acceso a internet; si el RSS no responde, mostrará un aviso y un enlace al catálogo.

En `Pronóstico actual`, el prototipo aplica un factor de viento a árboles/cables si el pronóstico alcanza 40 km/h, y un factor de lluvia a alcantarillas/baches si la probabilidad llega a 60% o la precipitación a 5 mm. Son umbrales exploratorios configurados en `tablero_plantilla.html`, no criterios oficiales de alerta meteorológica. `Evento extremo` permanece como escenario manual; `Sin clima` desactiva ajustes. Cuando no hay datos recientes del SMN, no se aplica automáticamente ningún multiplicador.

Para usar `resultados_b/tablero.html` sin ejecutar `smn_server.py`, el resto del tablero abre como archivo estático, pero el pronóstico, la hora del satélite, el radar, los límites de INEGI, las placas y el monitoreo sísmico no podrán consultar sus endpoints locales ni cambiarán las prioridades.

## Con tus datos reales
1. Hallazgos de prueba con instituciones reales de DENUE:
   `python generar_prueba.py --salida datos_prueba --denue TU_DENUE.csv`
2. Cuando el colaborador A entregue `hallazgos.csv`, solo cambia `--hallazgos`.
3. Si tus columnas tienen otros nombres, usa `--denue-id`, `--denue-lat`, `--denue-lon`,
   `--denue-codigo`, `--denue-ageb`, `--denue-mun`, `--acc-lat`, `--acc-lon`.

## Cómo se calcula la prioridad
`prioridad = severidad × institución × accidentes × población × tormenta`

| Factor | Valores |
|---|---|
| Severidad | crítica 3 · alta 2 · media 1 |
| Institución (SCIAN) | hospital 1.5 · guardería 1.5 · clínica 1.3 · escuela 1.2 |
| Accidentes a 200 m | 1 + accidentes/10 (tope ×3) |
| Población de la AGEB | 1.0 a 1.5 según la población |
| Tormenta (Vigía) | árboles y cables ×1.5 cuando está activo |

Los pesos están al inicio de `priorizar.py` para ajustarlos.

## Salidas
- `prioridades.csv`: cada hallazgo con su puntaje y el desglose de factores.
- `ordenes_<dependencia>.csv`: órdenes de trabajo por dependencia, de la más urgente a la menos.
- `ruta_ejemplo.csv`: hasta 10 paradas cercanas, empezando por la más urgente (`--dependencia-ruta`).
- `tablero.html`: mapa, pestañas por dependencia con su ruta, indicadores y botón de modo tormenta.

El tablero usa una vista de mapa a la izquierda y un panel de cinco pestañas a la derecha (Órdenes, Validación IA, Clima SMN, Sismos SSN y Análisis). En **Órdenes** puedes buscar por lugar, categoría, descripción o dependencia; en **Validación IA** puedes buscar detecciones sin perder el filtro de estado. **Análisis** muestra prioridad alta operativa, promedio, cobertura de coordenadas y avance de revisión humana. También compara dos series históricas: **ATUS/INEGI**, accidentes viales en Jalisco 2021–2025, y **SMN/CONAGUA**, precipitación anual estimada en Jalisco 2019–2025 en milímetros. Son gráficos descriptivos; no modifican el mapa ni los puntajes. La serie de precipitación representa el estado completo y no debe interpretarse como medición de Guadalajara o de una estación concreta; el SMN advierte que sus valores pueden cambiar al actualizar la base. ATUS muestra una nota por la revisión de certificados cero publicada en 2025. Fuentes: [tabulados ATUS](https://www.inegi.org.mx/app/tabulados/interactivos/?pxq=ATUS_ATUS_1_53fef2cc-0d30-497a-b292-f2d32d882113), [precipitación SMN 2019](https://smn.conagua.gob.mx/tools/DATA/Climatolog%C3%ADa/Pron%C3%B3stico%20clim%C3%A1tico/Temperatura%20y%20Lluvia/PREC/2019.pdf), [2020](https://smn.conagua.gob.mx/tools/DATA/Climatolog%C3%ADa/Pron%C3%B3stico%20clim%C3%A1tico/Temperatura%20y%20Lluvia/PREC/2020.pdf), [2021](https://smn.conagua.gob.mx/tools/DATA/Climatolog%C3%ADa/Pron%C3%B3stico%20clim%C3%A1tico/Temperatura%20y%20Lluvia/PREC/2021.pdf), [2022](https://smn.conagua.gob.mx/tools/DATA/Climatolog%C3%ADa/Pron%C3%B3stico%20clim%C3%A1tico/Temperatura%20y%20Lluvia/PREC/2022.pdf), [2023](https://smn.conagua.gob.mx/tools/DATA/Climatolog%C3%ADa/Pron%C3%B3stico%20clim%C3%A1tico/Temperatura%20y%20Lluvia/PREC/2023.pdf), [2024](https://smn.conagua.gob.mx/tools/DATA/Climatolog%C3%ADa/Diagn%C3%B3stico%20Atmosf%C3%A9rico/Reporte%20del%20Clima%20en%20M%C3%A9xico/Anual2024.pdf) y [2025](https://smn.conagua.gob.mx/tools/DATA/Climatolog%C3%ADa/Pron%C3%B3stico%20clim%C3%A1tico/Temperatura%20y%20Lluvia/PREC/2025.pdf). Desde Validación IA puedes confirmar o descartar candidatos y exportar los confirmados a CSV. El estado se guarda en el navegador cuando este permite almacenamiento local; la exportación conserva una copia portable.

## Integración de IA (Edge Impulse)

El proyecto incluye `edge_impulse_scan.py` para ejecutar el detector sobre fotos geolocalizadas y `procesar_edge_impulse.py` para automatizar inferencia → priorización → tablero. No se necesita una API key de Edge Impulse en el tablero: la inferencia se ejecuta localmente con el `.eim` desplegado. **El archivo `.eim` entrenado no está incluido en esta carpeta**; debes descargarlo de Edge Impulse Studio y copiarlo al dispositivo que ejecutará la inferencia.

Se mapean las nueve etiquetas de YOLO-Pro: `alcantarilla_riesgo`, `alcantarilla_tapada`, `arbol`, `bache`, `grieta_cocodrilo`, `poste_cableado`, `rama_riesgo`, `rama_sobre_cable` y `tronco_inclinado`. Cada detección empieza como candidata pendiente. No aparece como orden operativa hasta que se confirme en Validación IA; después exporta los confirmados y vuelve a ejecutar `priorizar.py` para actualizar los CSV de órdenes.

### Alternativa aislada: DenseNet121

La carpeta [`modelo_densenet121`](modelo_densenet121/README.md) incorpora entrenamiento por transferencia, ajuste fino, evaluación opcional en `test/` e inferencia de fotos geolocalizadas para las clases `bache`, `grieta_cocodrilo` y `alcantarilla_tapada`. Mantiene el flujo actual sin cambios y produce un CSV compatible con `priorizar.py`. DenseNet121 clasifica la foto completa; no produce bounding boxes como el detector de Edge Impulse.

### Preparar el modelo para Raspberry Pi 5

1. Como la página indica que es un proyecto público, usa **Clone this project** para crear una copia en tu cuenta. La propia página indica que hace falta clonar para volver a entrenar o desplegar.
2. En **Deployment**, genera el ejecutable `.eim` para `Linux (AARCH64)`, que corresponde a Raspberry Pi 5 con sistema de 64 bits. Descárgalo y cópialo como `modelos/gdl.eim`. Edge Impulse genera binarios para arquitecturas concretas; el Linux Python SDK también documenta el uso desde WSL. Un `.eim` AARCH64 de Raspberry Pi no corre directamente en Windows ni en WSL x86_64. Consulta la [guía oficial de descarga y ejecución](https://docs.edgeimpulse.com/tools/libraries/sdks/inference/linux/python).
3. En la Raspberry Pi instala OpenCV del sistema y el SDK de inferencia. Por ejemplo:

   ```bash
   sudo apt update
   sudo apt install python3-opencv python3-venv
   python3 -m venv --system-site-packages .venv
   source .venv/bin/activate
   python -m pip install edge_impulse_linux
   ```

   Ejecuta el flujo desde esa terminal con el entorno `.venv` activo. Para Windows, usa WSL con un `.eim` Linux x86_64; la inferencia no se ejecuta en Python nativo de Windows.

### Preparar fotos y coordenadas

Cada foto debe corresponder a una ubicación de Guadalajara y tener coordenadas GPS verificadas. Crea `capturas_gdl.csv` con estas columnas; las rutas de imagen pueden ser relativas al CSV:

```csv
imagen,latitud,longitud,fecha
fotos/centro_001.jpg,20.676700,-103.347500,2026-11-11T10:30:00
```

Las coordenadas de arriba son solo un ejemplo de formato. Sustitúyelas por las coordenadas reales de cada captura. El modelo detecta el objeto en la imagen; el CSV asocia esa detección con la ubicación GPS de la captura.

### Inferir y generar el tablero en un paso

```bash
python3 procesar_edge_impulse.py \
  --manifest capturas_gdl.csv \
  --modelo modelos/gdl.eim \
  --denue datos/denue.csv \
  --ageb datos/ageb.csv \
  --accidentes datos/accidentes.csv \
  --salida resultados_b \
  --umbral 0.55
```

El comando produce `resultados_b/hallazgos_edge_impulse.csv`, las evidencias y `resultados_b/tablero.html`. Las detecciones geolocalizadas se conservan aunque no correspondan a una institución DENUE. Empiezan con severidad `media` y revisión `pendiente`: la confianza expresa certeza de clase, no gravedad del daño.

El tablero presenta los candidatos y sus miniaturas en **Validación IA**. Las detecciones pendientes o descartadas no entran a los CSV de órdenes ni a la ruta. Tras confirmar casos, usa **Exportar confirmados** y vuelve a priorizar:

```bash
python3 priorizar.py \
  --hallazgos resultados_b/hallazgos_ia_confirmados.csv \
  --denue datos/denue.csv \
  --ageb datos/ageb.csv \
  --accidentes datos/accidentes.csv \
  --salida resultados_b
```

El tablero debe servirse por HTTP para mostrar el pronóstico SMN, el radar, las placas y las miniaturas locales; ejecuta `python3 smn_server.py` en la Raspberry Pi. Las capturas y coordenadas del manifiesto deben ser reales y verificadas.

### Validación en Guadalajara

La captura del proyecto muestra clases útiles para vialidades, pero varios ejemplos visibles parecen estar en India. Eso no demuestra que el modelo falle en GDL, aunque sí implica un cambio de entorno (tipo de pavimento, iluminación, cámaras, señalización y alcantarillas). Antes de usarlo para priorizar trabajo real, captura y etiqueta fotos locales de día/noche, lluvia/seco y distintos tipos de calle; separa imágenes de prueba que no se usaron al entrenar y mide precisión y falsos positivos por clase. Ajusta el umbral con ese conjunto local y vuelve a entrenar con ejemplos de Guadalajara cuando haga falta.
