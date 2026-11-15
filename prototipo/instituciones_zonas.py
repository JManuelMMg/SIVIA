"""
Zonas administrativas de Guadalajara para agrupar instituciones y órdenes.

La asignación es APROXIMADA: cada punto va a la zona cuyo centro está más cerca.
Para una operación real conviene usar los polígonos oficiales.
"""
import math

ZONAS = {
    1: ("Zona 1 · Centro", (20.6767, -103.3475)),
    2: ("Zona 2 · Minerva", (20.6850, -103.3850)),
    3: ("Zona 3 · Huentitán", (20.7250, -103.3200)),
    4: ("Zona 4 · Oblatos", (20.6950, -103.3000)),
    5: ("Zona 5 · Olímpica", (20.6550, -103.3350)),
    6: ("Zona 6 · Tetlán", (20.6450, -103.2900)),
    7: ("Zona 7 · Cruz del Sur", (20.6300, -103.3750)),
}


def distancia_m(a, b):
    """Distancia en metros entre dos puntos (lat, lng) con la fórmula del haversine."""
    la1, lo1, la2, lo2 = map(math.radians, (float(a[0]), float(a[1]), float(b[0]), float(b[1])))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def zona_de(lat, lng):
    return min(ZONAS, key=lambda z: distancia_m((lat, lng), ZONAS[z][1]))
