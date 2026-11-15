"""Muestra el avance del entrenamiento en una sola barra que se actualiza (lee el registro de YOLO).
Uso: python ver_progreso.py [log_v6.txt]"""
import os
import re
import sys
import time

log = sys.argv[1] if len(sys.argv) > 1 else "log_v6.txt"
ansi = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
ultima = ""
while True:
    with open(log, "rb") as fh:
        fh.seek(max(0, os.path.getsize(log) - 4000))
        txt = ansi.sub("", fh.read().decode("utf-8", "ignore"))
    trozos = [t.strip() for t in re.split(r"[\r\n]", txt) if t.strip()]
    linea = next((t for t in reversed(trozos) if "it/s" in t or "/15" in t), trozos[-1] if trozos else "")
    if linea != ultima:
        sys.stdout.write("\r" + linea[:150].ljust(150))
        sys.stdout.flush()
        ultima = linea
    if "confusion" in txt.lower() or "results saved" in txt.lower():
        print("\nEntrenamiento terminado.")
        break
    time.sleep(1)
