"""Láminas de revisión de candidatos_v8.json: 24 recortes por hoja (6 x 4), con la caja en amarillo."""
import json, os
from PIL import Image, ImageDraw, ImageFont
B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
c = json.load(open(os.path.join(B, "campo", "candidatos_v8.json")))
orden = {"alcantarilla_riesgo": 0, "alcantarilla_tapada": 1, "dano_pavimento": 2, "arbol_riesgo": 3}
items = sorted(((f, x) for f, v in c.items() for x in v), key=lambda t: (orden[t[1]["clase"]], t[0]))
AB = {"arbol_riesgo": "ARB", "alcantarilla_tapada": "ALC", "alcantarilla_riesgo": "ALCr", "dano_pavimento": "PAV"}
font = ImageFont.truetype("arialbd.ttf", 20)
out = os.path.join(B, "campo", "v8"); os.makedirs(out, exist_ok=True)
mapa = {}
S = 250
for L in range((len(items) + 23) // 24):
    hoja = Image.new("RGB", (6 * S, 4 * S))
    for i, (f, x) in enumerate(items[L * 24:(L + 1) * 24]):
        im = Image.open(os.path.join(B, "mapillary", "images", f)).convert("RGB")
        x0, y0, x1, y1 = x["caja"]; w, h = x1 - x0, y1 - y0
        lado = max(w, h) * 1.8 + 150; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        a, b = max(0, cx - lado / 2), max(0, cy - lado / 2)
        cr = im.crop((int(a), int(b), int(min(im.width, a + lado)), int(min(im.height, b + lado))))
        d = ImageDraw.Draw(cr)
        d.rectangle([x0 - a, y0 - b, x1 - a, y1 - b], outline="yellow", width=max(3, int(lado / 110)))
        cr.thumbnail((S, S))
        d = ImageDraw.Draw(cr); d.rectangle([0, 0, 95, 22], fill="black")
        d.text((3, 0), f"{i} {AB[x['clase']]}", fill="white", font=font)
        hoja.paste(cr, ((i % 6) * S, (i // 6) * S))
        mapa[f"{L:02d}-{i}"] = [f, x]
    hoja.save(os.path.join(out, f"h_{L:02d}.jpg"), quality=85)
json.dump(mapa, open(os.path.join(out, "mapa.json"), "w"))
print("candidatos", len(items), "hojas", (len(items) + 23) // 24)
