"""Láminas para medir la precisión en campo: detecciones que llegarían al tablero (inspector.confiable) en las
imágenes de instituciones reservadas, que ningún modelo usó para entrenar.
Uso: python campo/laminas_reservado.py agente/salida/detecciones_X.json etiqueta   (desde prototipo/)"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, ".")
from agente.inspector import confiable  # noqa: E402

R = "entrenamiento/"
det, tag = sys.argv[1], sys.argv[2]
hold = set(json.load(open(R + "modelo/campo_reservado.json"))["imagenes"])
d = json.load(open(det, encoding="utf-8"))
cands = []
for f in sorted(hold):
    vis = []
    with Image.open(R + "mapillary/images/" + f) as im:
        W, H = im.size
    for x in sorted(d.get(f, []), key=lambda x: -x["score"]):
        if "u" not in x or not confiable(x, W, H):
            continue
        cx, cy = x["x"] + x["w"] / 2, x["y"] + x["h"] / 2
        if any(y["label"] == x["label"] and abs(y["x"] + y["w"] / 2 - cx) < 50 and abs(y["y"] + y["h"] / 2 - cy) < 50 for y in vis):
            continue
        vis.append(x)
    cands += [(f, x) for x in vis]
AB = {"arbol_riesgo": "ARB", "alcantarilla_tapada": "ALC-t", "alcantarilla_riesgo": "ALC-r", "dano_pavimento": "PAV"}
font = ImageFont.truetype("arialbd.ttf", 22)
out = R + "campo/reservado/"
mapa = {}
for L in range((len(cands) + 19) // 20):
    hoja = Image.new("RGB", (1500, 1200))
    for i, (f, x) in enumerate(cands[L * 20:(L + 1) * 20]):
        im = Image.open(R + "mapillary/images/" + f).convert("RGB")
        lado = max(x["w"], x["h"]) * 2.2 + 120
        cx, cy = x["x"] + x["w"] / 2, x["y"] + x["h"] / 2
        a, b = max(0, cx - lado / 2), max(0, cy - lado / 2)
        c = im.crop((int(a), int(b), int(min(im.width, a + lado)), int(min(im.height, b + lado))))
        dr = ImageDraw.Draw(c)
        dr.rectangle([x["x"] - a, x["y"] - b, x["x"] + x["w"] - a, x["y"] + x["h"] - b], outline="yellow", width=max(2, int(lado / 120)))
        s = 300 / max(c.size)
        c = c.resize((max(1, round(c.width * s)), max(1, round(c.height * s))))
        dr = ImageDraw.Draw(c)
        dr.rectangle([0, 0, 120, 26], fill="black")
        dr.text((3, 0), f"{i} {AB[x['label']]}", fill="white", font=font)
        hoja.paste(c, ((i % 5) * 300, (i // 5) * 300))
        mapa[f"{L:02d}-{i}"] = [f, x]
    hoja.save(f"{out}{tag}_{L:02d}.jpg", quality=85)
json.dump(mapa, open(f"{out}{tag}_mapa.json", "w", encoding="utf-8"))
print(tag, "detecciones:", len(cands), "láminas:", (len(cands) + 19) // 20)
