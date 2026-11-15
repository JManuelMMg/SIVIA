"""
Condiciones adversas sintéticas para entrenar y medir el detector como lo verá un dron o un vehículo en temporal.

  lluvia      cielo cubierto (más oscuro y con menos contraste), rayas de lluvia inclinadas, gotas borrosas en el
              lente y un ligero desenfoque
  noche       gamma alta (oscurece), tinte frío del alumbrado y ruido del sensor
  niebla      velo claro que crece hacia la parte alta de la imagen (lo lejano se pierde primero)
  movimiento  desenfoque horizontal de vehículo o de dron en avance

Cada función recibe una imagen PIL RGB y un generador numpy (para que la variante sea reproducible) y no cambia el
tamaño, así que las cajas siguen siendo válidas. Solo depende de PIL y numpy.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

TIPOS = ("lluvia", "noche", "niebla", "movimiento")


def lluvia(img, rng):
    w, h = img.size
    img = ImageEnhance.Brightness(img).enhance(rng.uniform(0.55, 0.8))
    img = ImageEnhance.Contrast(img).enhance(rng.uniform(0.65, 0.85))
    capa = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(capa)
    largo = max(8, int(h * rng.uniform(0.03, 0.07)))
    ang = rng.uniform(-0.35, 0.35)
    for _ in range(int(w * h / rng.uniform(900, 2200))):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        d.line([(x, y), (x + largo * ang, y + largo)], fill=int(rng.uniform(90, 170)), width=1)
    capa = capa.filter(ImageFilter.GaussianBlur(0.7))
    img = Image.composite(Image.new("RGB", (w, h), (215, 220, 228)), img, capa.point(lambda v: v * 0.55))
    # gotas en el lente: zonas pequeñas más borrosas
    borrosa = img.filter(ImageFilter.GaussianBlur(max(2, w // 250)))
    mascara = Image.new("L", (w, h), 0)
    dm = ImageDraw.Draw(mascara)
    for _ in range(int(rng.integers(6, 25))):
        r = rng.uniform(0.01, 0.035) * w
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        dm.ellipse([x - r, y - r, x + r, y + r * rng.uniform(0.8, 1.3)], fill=255)
    img = Image.composite(borrosa, img, mascara.filter(ImageFilter.GaussianBlur(3)))
    return img.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 0.9)))


def noche(img, rng):
    g = rng.uniform(1.8, 2.6)
    tabla = [round(255 * (i / 255) ** g) for i in range(256)]
    img = img.point(tabla * 3)
    a = np.asarray(img, dtype=np.float32)
    a *= np.array([0.9, 0.95, 1.08], dtype=np.float32)  # alumbrado frío
    a += rng.normal(0, rng.uniform(4, 9), a.shape).astype(np.float32)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def niebla(img, rng):
    w, h = img.size
    fuerza = rng.uniform(0.35, 0.6)
    grad = np.linspace(fuerza, fuerza * 0.25, h, dtype=np.float32)[:, None, None]
    a = np.asarray(img, dtype=np.float32)
    velo = np.full_like(a, rng.uniform(190, 225))
    return Image.fromarray(np.clip(a * (1 - grad) + velo * grad, 0, 255).astype(np.uint8))


def movimiento(img, rng):
    k = int(rng.integers(5, 13))
    a = np.asarray(img, dtype=np.float32)
    acc = np.zeros_like(a)
    for s in range(k):
        acc += np.roll(a, s - k // 2, axis=1)
    return Image.fromarray((acc / k).astype(np.uint8))


FUNCIONES = {"lluvia": lluvia, "noche": noche, "niebla": niebla, "movimiento": movimiento}


def aplicar(img, tipo, semilla):
    return FUNCIONES[tipo](img.convert("RGB"), np.random.default_rng(semilla))
