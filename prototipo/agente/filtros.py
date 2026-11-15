"""
Filtro adaptativo por imagen (preprocesamiento) para el detector.

Cada imagen se mide (brillo, contraste y nitidez) y solo recibe la corrección que le hace falta:
  - contraste bajo (desviación de gris < 45)  -> estiramiento de histograma con 1 % de recorte
  - oscura (brillo medio < 85)                -> gamma 0.75 (aclara sombras)
  - sobreexpuesta (brillo medio > 175)        -> gamma 1.3 (recupera detalle en zonas claras)
  - borrosa (varianza del laplaciano < 60)    -> máscara de enfoque suave
Una imagen bien expuesta y nítida pasa sin cambios. Se usa igual al construir el dataset y en la cámara,
para que el modelo vea en campo lo mismo que vio al entrenar. Solo depende de PIL y numpy.
"""
import numpy as np
from PIL import Image, ImageFilter, ImageOps

UMBRALES = {"contraste": 45.0, "oscura": 85.0, "clara": 175.0, "nitidez": 60.0}


def medir(img):
    """Brillo, contraste y nitidez sobre una versión de 512 px (las medidas no dependen del tamaño)."""
    g = img.convert("L")
    g.thumbnail((512, 512))
    a = np.asarray(g, dtype=np.float32)
    lap = a[1:-1, 1:-1] * -4 + a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:]
    return {"brillo": float(a.mean()), "contraste": float(a.std()), "nitidez": float(lap.var())}


def _gamma(img, g):
    tabla = [round(255 * (i / 255) ** g) for i in range(256)] * 3
    return img.point(tabla)


def filtrar(img):
    """Devuelve (imagen corregida, lista de filtros aplicados, medidas originales)."""
    img = img.convert("RGB")
    m = medir(img)
    hechos = []
    if m["contraste"] < UMBRALES["contraste"]:
        img = ImageOps.autocontrast(img, cutoff=1)
        hechos.append("contraste")
    b = medir(img)["brillo"] if hechos else m["brillo"]
    if b < UMBRALES["oscura"]:
        img = _gamma(img, 0.75)
        hechos.append("aclarar")
    elif b > UMBRALES["clara"]:
        img = _gamma(img, 1.3)
        hechos.append("oscurecer")
    if m["nitidez"] < UMBRALES["nitidez"]:
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=80, threshold=3))
        hechos.append("enfoque")
    return img, hechos, m
