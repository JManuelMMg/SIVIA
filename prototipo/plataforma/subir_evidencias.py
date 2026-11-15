"""
Sube al bucket S3 las fotos de evidencia (copia reducida a 720 px de entregables/tablero/img) y anota su
llave en la tabla imagenes. Solo sube lo que falta.

Credenciales SOLO por entorno: DATABASE_URL, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
AWS_ENDPOINT_URL_S3 (o AWS_ENDPOINT_URL), AWS_REGION y BUCKET (por defecto "reportbucket").
Uso: plataforma\\iniciar_con_bd.ps1 -Accion subir
"""
import os

import boto3
import psycopg
from botocore.config import Config

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(os.path.dirname(BASE), "entregables", "tablero", "img")
BUCKET = os.environ.get("BUCKET", "reportbucket")
PREFIJO = "evidencias/mapillary/"


def main():
    for v in ("DATABASE_URL", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
        if not os.environ.get(v):
            raise SystemExit(f"Falta {v} en el entorno (usa plataforma/iniciar_con_bd.ps1 -Accion subir).")
    s3 = boto3.client("s3", endpoint_url=os.environ.get("AWS_ENDPOINT_URL_S3") or os.environ.get("AWS_ENDPOINT_URL"),
                      config=Config(s3={"addressing_style": "path"}))
    with psycopg.connect(os.environ["DATABASE_URL"]) as con:
        faltan = [r[0] for r in con.execute("SELECT archivo FROM imagenes WHERE bucket_key IS NULL ORDER BY archivo")]
        subidas = 0
        for i, f in enumerate(faltan, 1):
            ruta = os.path.join(IMG, f)
            if not os.path.exists(ruta):
                continue
            llave = PREFIJO + f
            with open(ruta, "rb") as fh:
                s3.put_object(Bucket=BUCKET, Key=llave, Body=fh, ContentType="image/jpeg")
            con.execute("UPDATE imagenes SET bucket_key = %s WHERE archivo = %s", (llave, f))
            subidas += 1
            if i % 50 == 0:
                con.commit()
                print(f"  {i}/{len(faltan)}", flush=True)
        con.commit()
    print(f"evidencias subidas: {subidas} de {len(faltan)} pendientes, bucket '{BUCKET}', prefijo {PREFIJO}")


if __name__ == "__main__":
    main()
