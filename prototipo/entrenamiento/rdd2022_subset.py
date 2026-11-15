"""
Entorno Seguro GDL - Extrae un subconjunto del dataset RDD2022 sin descargar los 13 GB.

RDD2022 (Arya et al., CRDDC 2022), figshare 21431547, licencia CC BY 4.0.
https://figshare.com/articles/dataset/RDD2022_-_The_multi-national_Road_Damage_Dataset_released_through_CRDDC_2022/21431547

El ZIP se lee de forma remota con peticiones HTTP por rangos: primero el índice, luego las
anotaciones (XML Pascal VOC) de los países elegidos, y al final solo las imágenes útiles.

Uso:
    python rdd2022_subset.py listar
    python rdd2022_subset.py extraer --paises India United_States Czech --baches 900 --negativas 300
"""
import argparse
import io
import os
import random
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

URL = "https://ndownloader.figshare.com/files/38030910"
UA = {"User-Agent": "hackaton-entorno-seguro/1.0"}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rdd2022_subset")
# Clases RDD2022: D00 grieta longitudinal, D10 transversal, D20 piel de cocodrilo, D40 bache
CLASES = {"D40": "bache", "D20": "grieta_cocodrilo"}


class HttpRangeFile(io.RawIOBase):
    """Archivo de solo lectura sobre HTTP con caché por bloques (para zipfile)."""

    def __init__(self, url, block=4 * 1024 * 1024):
        self.origen = url
        self._resolver()
        self.pos, self.block, self.cache, self.requests = 0, block, {}, 0

    def _resolver(self):
        """El enlace firmado al que redirige figshare caduca; se vuelve a pedir cuando hace falta."""
        req = urllib.request.Request(self.origen, headers={**UA, "Range": "bytes=0-0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            self.url = r.geturl()
            self.size = int(r.headers["Content-Range"].split("/")[1])

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: self.size + off}[whence]
        return self.pos

    def _get_block(self, i):
        if i not in self.cache:
            a, b = i * self.block, min(self.size, (i + 1) * self.block) - 1
            for intento in range(5):
                req = urllib.request.Request(self.url, headers={**UA, "Range": f"bytes={a}-{b}"})
                try:
                    with urllib.request.urlopen(req, timeout=120) as r:
                        self.cache[i] = r.read()
                    break
                except urllib.error.HTTPError as e:
                    if e.code in (400, 401, 403) and intento < 4:
                        self._resolver()  # enlace firmado caducado
                        continue
                    raise
                except Exception:
                    if intento == 4:
                        raise
            self.requests += 1
            if len(self.cache) > 64:  # máx ~256 MB en memoria
                self.cache.pop(next(iter(self.cache)))
        return self.cache[i]

    def readinto(self, b):
        n = min(len(b), self.size - self.pos)
        if n <= 0:
            return 0
        out, p = bytearray(), self.pos
        while len(out) < n:
            i = p // self.block
            blk = self._get_block(i)
            off = p - i * self.block
            chunk = blk[off: off + (n - len(out))]
            out += chunk
            p += len(chunk)
        b[:n] = out
        self.pos += n
        return n


class Ventana(io.RawIOBase):
    """Vista de solo lectura de un tramo [base, base+size) de otro archivo."""

    def __init__(self, raw, base, size):
        self.raw, self.base, self.size, self.pos = raw, base, size, 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: self.size + off}[whence]
        return self.pos

    def readinto(self, b):
        n = min(len(b), self.size - self.pos)
        if n <= 0:
            return 0
        self.raw.seek(self.base + self.pos)
        got = self.raw.readinto(memoryview(b)[:n])
        self.pos += got
        return got


def abrir():
    f = HttpRangeFile(URL)
    print(f"ZIP remoto: {f.size / 1e9:.1f} GB")
    return f, zipfile.ZipFile(io.BufferedReader(f, buffer_size=1024 * 1024))


def abrir_pais(f, z, pais):
    """Abre el ZIP de un país (almacenado sin comprimir) sin descargarlo completo."""
    info = z.getinfo(f"RDD2022/{pais}.zip")
    f.seek(info.header_offset)
    hdr = f.read(30) if hasattr(f, "read") else None
    import struct
    n_name, n_extra = struct.unpack("<HH", hdr[26:30])
    base = info.header_offset + 30 + n_name + n_extra
    return zipfile.ZipFile(io.BufferedReader(Ventana(f, base, info.compress_size), buffer_size=1024 * 1024))


def listar():
    f, z = abrir()
    names = z.namelist()
    from collections import Counter
    tops = Counter("/".join(n.split("/")[:4]) for n in names if not n.endswith("/"))
    for k, v in sorted(tops.items()):
        print(f"{v:6d}  {k}")
    print(f"peticiones HTTP: {f.requests}")


def extraer(paises, n_baches, n_neg, semilla=7):
    import json
    f, z = abrir()
    zips = {p: abrir_pais(f, z, p) for p in paises}
    cand_path = os.path.join(OUT, "candidatos.json")
    if os.path.exists(cand_path):
        with open(cand_path, encoding="utf-8") as fh:
            cand = json.load(fh)
        con = [((p, i), [tuple(o) for o in objs]) for (p, i), objs in cand["con"] if p in paises]
        sin = [((p, i), [tuple(o) for o in objs]) for (p, i), objs in cand["sin"] if p in paises]
        print(f"Candidatas guardadas: {len(con)} con bache, {len(sin)} sin bache")
    else:
        con, sin = escanear(f, zips)
        os.makedirs(OUT, exist_ok=True)
        with open(cand_path, "w", encoding="utf-8") as fh:
            json.dump({"con": con, "sin": sin}, fh)
    elegir_y_bajar(f, zips, con, sin, n_baches, n_neg, semilla)


def escanear(f, zips):
    con, sin = [], []
    for pais, zp in zips.items():
        names = set(zp.namelist())
        xmls = [n for n in names if n.endswith(".xml") and "/annotations/xmls/" in n]
        print(f"{pais}: {len(xmls)} anotaciones")
        for k, n in enumerate(sorted(xmls), 1):
            root = ET.fromstring(zp.read(n))
            objs = []
            for o in root.iter("object"):
                c = o.findtext("name")
                if c in CLASES:
                    bb = o.find("bndbox")
                    objs.append((CLASES[c], *(int(float(bb.findtext(t))) for t in ("xmin", "ymin", "xmax", "ymax"))))
            img = n.replace("/annotations/xmls/", "/images/").rsplit(".", 1)[0] + ".jpg"
            if img not in names:
                continue
            (con if any(o[0] == "bache" for o in objs) else sin).append(((pais, img), objs))
            if k % 2000 == 0:
                print(f"  {k}/{len(xmls)} | con bache: {len(con)} | peticiones: {f.requests}")
    return con, sin


def elegir_y_bajar(f, zips, con, sin, n_baches, n_neg, semilla):
    random.seed(semilla)
    random.shuffle(con)
    random.shuffle(sin)
    elegidas = con[:n_baches] + [(i, []) for i, o in sin if not o][:n_neg]
    print(f"Imágenes con bache disponibles: {len(con)} | elegidas: {min(len(con), n_baches)} + {n_neg} negativas")

    os.makedirs(os.path.join(OUT, "images"), exist_ok=True)
    import json
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed
    local = threading.local()
    paises = sorted({p for (p, _), _ in elegidas})

    def zips_del_hilo():
        # cada hilo tiene su propia conexión y sus propios ZIP (zipfile no es seguro entre hilos)
        if not hasattr(local, "zips"):
            fh = HttpRangeFile(URL, block=512 * 1024)
            zo = zipfile.ZipFile(io.BufferedReader(fh, buffer_size=1024 * 1024))
            local.zips = {p: abrir_pais(fh, zo, p) for p in paises}
        return local.zips

    def bajar(item):
        (pais, img), objs = item
        nombre = pais + "_" + os.path.basename(img)
        dst = os.path.join(OUT, "images", nombre)
        if not os.path.exists(dst):
            data = zips_del_hilo()[pais].read(img)
            with open(dst + ".tmp", "wb") as fh:
                fh.write(data)
            os.replace(dst + ".tmp", dst)
        return nombre, [{"label": c, "x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0}
                        for c, x0, y0, x1, y1 in objs]

    labels = {"version": 1, "type": "bounding-box-labels", "boundingBoxes": {}}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(bajar, it) for it in elegidas]
        for k, fu in enumerate(as_completed(futs), 1):
            try:
                nombre, cajas = fu.result()
                labels["boundingBoxes"][nombre] = cajas
            except Exception as exc:
                print(f"  error bajando una imagen: {exc}")
            if k % 100 == 0:
                print(f"  {k}/{len(elegidas)} imágenes")
    with open(os.path.join(OUT, "images", "bounding_boxes.labels"), "w", encoding="utf-8") as fh:
        json.dump(labels, fh)
    n_cajas = sum(len(v) for v in labels["boundingBoxes"].values())
    print(f"\nListo: {len(elegidas)} imágenes, {n_cajas} cajas en {OUT}")
    pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("accion", choices=["listar", "extraer"])
    ap.add_argument("--paises", nargs="+", default=["India", "United_States", "Czech"])
    ap.add_argument("--baches", type=int, default=900)
    ap.add_argument("--negativas", type=int, default=300)
    a = ap.parse_args()
    listar() if a.accion == "listar" else extraer(a.paises, a.baches, a.negativas)
