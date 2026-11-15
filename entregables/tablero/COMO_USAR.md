# Tablero de inspección urbana: cómo usarlo

## Opción 1: sin instalar nada
Abre `index.html` con doble clic. Funciona todo: mapa, órdenes, clima SMN, validación y análisis.
En la pestaña **En vivo**, el botón **▶ Reproducir recorrido** repite el recorrido grabado del vehículo con las detecciones reales del modelo.
Necesitas internet para ver el mapa base. La carpeta `img/` debe quedar junto a `index.html`.

## Opción 2: demo en tiempo real (cámara → centro de control → tablero)
Necesitas Python 3, `pip install numpy pillow onnxruntime` y las imágenes de Mapillary en `prototipo/entrenamiento/mapillary/images/` (se bajan con `bajar_mapillary.ps1` y un token propio). Corre los comandos desde la carpeta `prototipo/`. Este recorrido es una **simulación** con fotos de Mapillary: así hay que presentarlo.

1. Arranca el centro de control:
   ```
   python agente/centro_control.py
   ```
2. Abre http://localhost:8765 y entra a la pestaña **En vivo**. Debe decir "Conectado al centro de control".
3. En otra terminal, arranca la cámara del vehículo:
   ```
   python agente/camara_simulada.py --pausa 1.0
   ```
   La cámara recorre la zona con 70 imágenes reales de calle. En cada cuadro corre el detector YOLO11s v8 (unos 100 ms por cuadro) y solo envía eventos: la posición y lo que detectó.

El centro de control asocia cada detección a la institución más cercana. Si el mismo objeto ya se vio a 15 m o menos, no lo duplica: suma un avistamiento. Calcula la prioridad con los accidentes del INEGI y el clima del SMN.

## Qué hace el operador
- **En vivo:** a cada detección le aplica Confirmar → Asignar a cuadrilla → Iniciar atención → Marcar resuelto, o la descarta.
- **Órdenes:** abre una orden, cambia su estado (Pendiente, Asignada, En atención, Resuelta) e imprime la orden de trabajo.
- **Validación IA:** confirma o descarta los candidatos del modelo y exporta los confirmados.
- **Clima (arriba):** compara el pronóstico actual con el escenario de evento extremo; las prioridades se recalculan al momento.

Los estados se guardan en el navegador del operador. En un piloto real se guardarían en el servidor del municipio.
