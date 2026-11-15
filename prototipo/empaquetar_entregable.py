"""
Arma el Entregable Técnico (ET) del Hackathon: entregables/ET_Entregable_Tecnico.zip

Incluye el código de los agentes y del entrenamiento, el modelo integrado (v9, ONNX), los datos ya
procesados de los datasets del catálogo, las salidas del sistema, los dos tableros listos para abrir
y las evaluaciones. No incluye las imágenes de entrenamiento ni los pesos intermedios (pesan GB):
se reconstruyen con los scripts y un token propio de Mapillary, que nunca se guarda en archivos.

Uso:  python prototipo/empaquetar_entregable.py
"""
import glob
import os
import re
import shutil
import zipfile

BASE = os.path.dirname(os.path.abspath(__file__))          # prototipo/
RAIZ = os.path.dirname(BASE)
ENT = os.path.join(RAIZ, "entregables")
OUT = os.path.join(ENT, "ET_Entregable_Tecnico.zip")
DIR = "ET_Entregable_Tecnico"

ARCHIVOS = (
    ["prototipo/instituciones_zonas.py", "prototipo/empaquetar_entregable.py"]
    + glob.glob("prototipo/agente/*.py", root_dir=RAIZ)
    + ["prototipo/agente/tablero_plantilla.html"]
    + glob.glob("prototipo/agente/colab_b/*", root_dir=RAIZ)
    + glob.glob("prototipo/plataforma/*", root_dir=RAIZ)
    + glob.glob("prototipo/datos/*.csv", root_dir=RAIZ)
    + glob.glob("prototipo/datos/smn/**/*", root_dir=RAIZ, recursive=True)
    + [f"prototipo/agente/salida/{f}" for f in ("detecciones_yolo.json", "detecciones_modelo.json", "hallazgos.csv",
                                                 "ordenes_trabajo.csv", "resumen.json", "clima_smn.json",
                                                 "detecciones_v9_campo.json")]
    + glob.glob("prototipo/entrenamiento/*.py", root_dir=RAIZ)
    + glob.glob("prototipo/entrenamiento/campo/*.py", root_dir=RAIZ)
    + ["prototipo/entrenamiento/campo/reservado/estados.json", "prototipo/entrenamiento/campo/reservado/v8_00.jpg", "prototipo/entrenamiento/campo/reservado/v9_00.jpg",
       "prototipo/entrenamiento/campo/v7/revision.json", "prototipo/entrenamiento/campo/v8/revision.json",
       "prototipo/entrenamiento/mapillary/imagenes.csv", "prototipo/entrenamiento/bajar_mapillary.ps1"]
    + ["prototipo/entrenamiento/modelo/entorno_seguro_v9_yolo11s.onnx",
       "prototipo/entrenamiento/modelo/entorno_seguro_v9_yolo11s.umbrales.json",
       "prototipo/entrenamiento/modelo/campo_reservado.json"]
    + glob.glob("prototipo/entrenamiento/modelo/*.json", root_dir=RAIZ)
    + glob.glob("entregables/tablero/**/*", root_dir=RAIZ, recursive=True)
    + glob.glob("entregables/tablero_vivo/**/*", root_dir=RAIZ, recursive=True)
)
EXTRA = {"LEEME.md": os.path.join(BASE, "LEEME_entregable.md"),
         "requirements.txt": os.path.join(BASE, "requirements.txt")}

# Ninguna llave ni token debe viajar en el paquete
SECRETO = re.compile(rb"MLY\|\d|AIza[0-9A-Za-z_-]{20}|ei_[0-9a-f]{20}|sk-[A-Za-z0-9]{20}|npg_[A-Za-z0-9]{8}|"
                     rb"postgres(?:ql)?://[^\s:@/]+:[^\s@]+@|AKIA[0-9A-Z]{16}")


def main():
    vistos, total = set(), 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for rel in (r.replace("\\", "/") for r in ARCHIVOS):
            src = os.path.join(RAIZ, rel)
            if rel in vistos or not os.path.isfile(src) or "__pycache__" in rel:
                continue
            vistos.add(rel)
            if src.endswith((".py", ".json", ".csv", ".md", ".html", ".ps1", ".bat", ".txt", ".sql")):
                with open(src, "rb") as fh:
                    if SECRETO.search(fh.read()):
                        raise SystemExit(f"posible llave en {rel}: revisar antes de empaquetar")
            z.write(src, f"{DIR}/{rel}")
            total += os.path.getsize(src)
        for nombre, src in EXTRA.items():
            z.write(src, f"{DIR}/{nombre}")
    print(f"{OUT} | archivos {len(vistos) + len(EXTRA)} | {total / 1e6:.0f} MB sin comprimir | "
          f"{os.path.getsize(OUT) / 1e6:.0f} MB comprimido")


if __name__ == "__main__":
    main()
