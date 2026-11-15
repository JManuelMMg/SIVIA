#!/usr/bin/env python3
"""
Servidor del tablero en vivo con base de datos.

Extiende smn_server.py (clima SMN, GOES, radar, INEGI, SSN, USGS; sin cambios) con la plataforma:
  GET  /api/bd/estado                 conexión y conteos
  GET  /api/candidatos                {id: estado} de los candidatos del modelo
  POST /api/candidatos/<id>           {"estado": "confirmado"|"descartado"|"pendiente"}
  GET  /api/ordenes?dependencia=...   órdenes con su estado
  POST /api/ordenes/<id>              {"estado": "asignada"|"en_atencion"|"resuelta"|"descartada"|"pendiente"}
  GET  /api/evidencia/<archivo>       redirige a una liga firmada del bucket (si está configurado)

Credenciales SOLO por variables de entorno, nunca en archivos:
  DATABASE_URL                       PostgreSQL
  AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_ENDPOINT_URL_S3, AWS_REGION, BUCKET (por defecto "reportbucket")
Sin DATABASE_URL el tablero funciona como antes, guardando las validaciones en el navegador.

Uso: python servidor.py [--port 8000] [--no-browser]
"""
import json
import os
import re
import sys
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import smn_server  # noqa: E402

DB = os.environ.get("DATABASE_URL")
BUCKET = os.environ.get("BUCKET", "reportbucket")
EST_CAND = {"pendiente", "confirmado", "descartado"}
EST_ORD = {"pendiente", "asignada", "en_atencion", "resuelta", "descartada"}
ID_OK = re.compile(r"^[A-Za-z0-9_:.\-]{1,120}$")


def con():
    import psycopg
    return psycopg.connect(DB, connect_timeout=10)


def s3():
    if not (os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY")):
        return None
    import boto3
    from botocore.config import Config
    return boto3.client("s3", endpoint_url=os.environ.get("AWS_ENDPOINT_URL_S3") or os.environ.get("AWS_ENDPOINT_URL"),
                        config=Config(s3={"addressing_style": "path"}))


class Handler(smn_server.Handler):
    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _cuerpo(self):
        n = min(int(self.headers.get("Content-Length") or 0), 10_000)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def do_GET(self):
        u = urlsplit(self.path)
        if not u.path.startswith(("/api/bd/", "/api/candidatos", "/api/ordenes", "/api/evidencia/")):
            return super().do_GET()
        if not DB:
            return self._json({"ok": False, "error": "sin base de datos (DATABASE_URL)"}, 503)
        try:
            if u.path == "/api/bd/estado":
                with con() as c:
                    n = c.execute("SELECT (SELECT count(*) FROM ordenes), (SELECT count(*) FROM candidatos), "
                                  "(SELECT count(*) FROM candidatos WHERE estado <> 'pendiente')").fetchone()
                return self._json({"ok": True, "ordenes": n[0], "candidatos": n[1], "revisados": n[2],
                                   "bucket": bool(s3())})
            if u.path == "/api/candidatos":
                with con() as c:
                    filas = c.execute("SELECT id, estado FROM candidatos").fetchall()
                return self._json({"ok": True, "estados": dict(filas)})
            if u.path == "/api/ordenes":
                dep = parse_qs(u.query).get("dependencia", [None])[0]
                q = ("SELECT o.id, o.dependencia, o.hallazgo, o.prioridad, o.estado, i.nombre, i.zona, o.actualizada_en "
                     "FROM ordenes o LEFT JOIN instituciones i ON i.id = o.institucion_id")
                with con() as c:
                    filas = c.execute(q + (" WHERE o.dependencia = %s" if dep else "") + " ORDER BY o.prioridad DESC",
                                      (dep,) if dep else ()).fetchall()
                cols = ["id", "dependencia", "hallazgo", "prioridad", "estado", "institucion", "zona", "actualizada_en"]
                return self._json({"ok": True, "ordenes": [dict(zip(cols, f)) for f in filas]})
            if u.path.startswith("/api/evidencia/"):
                archivo = unquote(u.path.rsplit("/", 1)[1])
                cli = s3()
                if not ID_OK.match(archivo) or not cli:
                    return self._json({"ok": False, "error": "sin bucket o archivo inválido"}, 404)
                with con() as c:
                    fila = c.execute("SELECT bucket_key FROM imagenes WHERE archivo = %s", (archivo,)).fetchone()
                if not fila or not fila[0]:
                    return self._json({"ok": False, "error": "imagen no subida al bucket"}, 404)
                liga = cli.generate_presigned_url("get_object", Params={"Bucket": BUCKET, "Key": fila[0]}, ExpiresIn=3600)
                self.send_response(302)
                self.send_header("Location", liga)
                self.end_headers()
                return None
        except Exception as e:  # la base no responde: el tablero sigue con el navegador
            return self._json({"ok": False, "error": type(e).__name__}, 502)
        return self._json({"ok": False, "error": "ruta desconocida"}, 404)

    def do_POST(self):
        u = urlsplit(self.path)
        m = re.match(r"^/api/(candidatos|ordenes)/([^/]+)$", u.path)
        if not m:
            return self._json({"ok": False, "error": "ruta desconocida"}, 404)
        if not DB:
            return self._json({"ok": False, "error": "sin base de datos (DATABASE_URL)"}, 503)
        tabla, rid = m.group(1), unquote(m.group(2))
        estado = str(self._cuerpo().get("estado", ""))
        if not ID_OK.match(rid) or estado not in (EST_CAND if tabla == "candidatos" else EST_ORD):
            return self._json({"ok": False, "error": "dato inválido"}, 400)
        extra = "revisado_en = now()" if tabla == "candidatos" else "actualizada_en = now()"
        try:
            with con() as c:
                n = c.execute(f"UPDATE {tabla} SET estado = %s, {extra} WHERE id = %s", (estado, rid)).rowcount
                if n:
                    c.execute("INSERT INTO eventos (tabla, registro, estado, usuario) VALUES (%s, %s, %s, %s)",
                              (tabla, rid, estado, "tablero"))
        except Exception as e:
            return self._json({"ok": False, "error": type(e).__name__}, 502)
        return self._json({"ok": bool(n), "id": rid, "estado": estado}, 200 if n else 404)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Tablero en vivo con base de datos")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"Tablero: http://{a.host}:{a.port}/index.html")
    print("Base de datos:", "conectada por DATABASE_URL" if DB else "no configurada (validaciones en el navegador)")
    print("Bucket:", f"'{BUCKET}' configurado" if s3() else "no configurado")
    print("Presiona Ctrl+C para detener el servidor.")
    try:
        if not a.no_browser:
            webbrowser.open(f"http://{a.host}:{a.port}/index.html")
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
