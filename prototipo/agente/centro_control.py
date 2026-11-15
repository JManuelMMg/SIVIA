"""
Centro de control (demo): sirve el tablero y recibe en vivo los eventos de las cámaras de los vehículos.

La cámara solo manda eventos (no video): posición del vehículo y cada detección del modelo.
El centro de control:
  - asocia la detección a la institución más cercana (DENUE),
  - no duplica: si el mismo tipo de falla ya se vio a 15 m o menos, suma un avistamiento,
  - calcula la prioridad con el Evaluador de impacto (ATUS) y el factor de clima del Vigía (SMN),
  - publica los mensajes para el tablero (pestaña "En vivo").

Uso:  python agente/centro_control.py            (abre http://localhost:8765)
      python agente/camara_simulada.py          (en otra terminal: el vehículo empieza a recorrer)
API:  POST /api/posicion  POST /api/deteccion  GET /api/mensajes?desde=N  POST /api/reiniciar  GET /api/estado
"""
import csv
import json
import math
import os
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from agente.coordinador import impacto  # noqa: E402

RAIZ = os.path.dirname(BASE)
WEB = os.path.join(RAIZ, "entregables", "tablero")
SAL = os.path.join(BASE, "agente", "salida")

GRAVEDAD = {"bache": 1.0, "dano_pavimento": 0.9, "arbol_riesgo": 1.0, "grieta_cocodrilo": 0.6, "alcantarilla_tapada": 0.25, "alcantarilla_riesgo": 1.0,
            "rama_riesgo": 0.9, "rama_sobre_cable": 0.9, "tronco_inclinado": 1.0}
DEPENDENCIA = {"bache": "Dirección de Pavimentos", "dano_pavimento": "Dirección de Pavimentos",
               "arbol_riesgo": "Parques y Jardines", "grieta_cocodrilo": "Dirección de Pavimentos",
               "alcantarilla_tapada": "Agua y Drenaje (SIAPA)", "alcantarilla_riesgo": "Agua y Drenaje (SIAPA)",
               "rama_riesgo": "Parques y Jardines", "rama_sobre_cable": "Parques y Jardines / CFE",
               "tronco_inclinado": "Parques y Jardines"}


def metros(la1, ln1, la2, ln2):
    x = math.radians(ln2 - ln1) * math.cos(math.radians((la1 + la2) / 2))
    return 6371000 * math.hypot(x, math.radians(la2 - la1))


class Enriquecedor:
    """Convierte una detección cruda de la cámara en un evento listo para el operador."""

    def __init__(self, radio=15):
        with open(os.path.join(BASE, "datos", "denue_gdl_instituciones.csv"), encoding="utf-8") as fh:
            self.inst = list(csv.DictReader(fh))
        with open(os.path.join(BASE, "datos", "instituciones_siniestralidad.csv"), encoding="utf-8") as fh:
            self.sin = {r["id"]: r for r in csv.DictReader(fh)}
        try:
            with open(os.path.join(SAL, "clima_smn.json"), encoding="utf-8") as fh:
                self.clima = json.load(fh)["factores_actuales"]
        except (OSError, KeyError):
            self.clima = {}
        self.radio = radio
        self.eventos = []

    def cercana(self, la, ln):
        r = min(self.inst, key=lambda r: metros(la, ln, float(r["latitud"]), float(r["longitud"])))
        return r, metros(la, ln, float(r["latitud"]), float(r["longitud"]))

    def procesar(self, d):
        k = d["k"]
        for e in self.eventos:  # mismo objeto visto otra vez
            if e["k"] == k and metros(d["la"], d["ln"], e["la"], e["ln"]) <= self.radio:
                e["vistas"] += 1
                e["s"] = max(e["s"], d["s"])
                return dict(e, tipo="det")
        r, dist = self.cercana(d["la"], d["ln"])
        tipo, imp, riesgo, acc, peat = impacto(r, self.sin.get(r["id"], {}))
        cerca = 1.0 if dist <= 100 else 0.7 if dist <= 200 else 0.4
        prio = round(100 * GRAVEDAD.get(k, 0.6) * imp * riesgo * cerca * self.clima.get(k, 1.0), 1)
        e = {"id": f"ev{len(self.eventos) + 1:04d}", "veh": d.get("veh", "GDL-01"), "la": d["la"], "ln": d["ln"],
             "f": d["f"], "k": k, "s": d["s"], "caja": d["caja"], "t": d.get("t", ""), "vistas": 1,
             "iid": r["id"], "inst": r["nom_estab"].strip().title()[:60], "tipo_inst": tipo, "dist": round(dist),
             "acc": acc, "peat": peat, "dep": DEPENDENCIA.get(k, "Servicios Públicos"), "prio": prio}
        self.eventos.append(e)
        return dict(e, tipo="det")


class Centro:
    def __init__(self):
        self.lock = threading.Lock()
        self.reiniciar()

    def reiniciar(self):
        with getattr(self, "lock", threading.Lock()):
            self.enr = Enriquecedor()
            self.msgs = []

    def agregar(self, m):
        with self.lock:
            self.msgs.append(m)


CENTRO = Centro()


class Manejador(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/estado":
            return self._json({"ok": True, "mensajes": len(CENTRO.msgs), "eventos": len(CENTRO.enr.eventos)})
        if u.path == "/api/mensajes":
            desde = int(parse_qs(u.query).get("desde", ["0"])[0])
            with CENTRO.lock:
                return self._json({"desde": desde, "mensajes": CENTRO.msgs[desde:]})
        return super().do_GET()

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        try:
            d = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return self._json({"error": "JSON inválido"}, 400)
        if self.path == "/api/posicion":
            CENTRO.agregar(dict(d, tipo="pos"))
            return self._json({"ok": True})
        if self.path == "/api/deteccion":
            with CENTRO.lock:
                m = CENTRO.enr.procesar(d)
                CENTRO.msgs.append(m)
            return self._json({"ok": True, "id": m["id"], "vistas": m["vistas"]})
        if self.path == "/api/reiniciar":
            CENTRO.reiniciar()
            CENTRO.agregar({"tipo": "reinicio"})
            return self._json({"ok": True})
        return self._json({"error": "ruta desconocida"}, 404)


def main():
    puerto = int(os.environ.get("PUERTO", "8765"))
    srv = ThreadingHTTPServer(("127.0.0.1", puerto), partial(Manejador, directory=WEB))
    print(f"Centro de control en http://localhost:{puerto}  (Ctrl+C para salir)", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
