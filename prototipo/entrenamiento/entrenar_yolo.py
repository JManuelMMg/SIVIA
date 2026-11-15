"""Entrena el detector YOLO en local (GPU).

Uso v3 (desde COCO):   .venv_yolo/Scripts/python entrenar_yolo.py
Uso v4 (afinar v3):    .venv_yolo/Scripts/python entrenar_yolo.py --datos dataset_yolo_v4 --nombre v4_sin_filtro
                         --pesos modelo/yolo/v3_yolo11s/weights/best.pt --epocas 35 --lr0 0.0005
"""
import argparse
import os

from ultralytics import YOLO

BASE = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", default="dataset_yolo")
    ap.add_argument("--nombre", default="v3_yolo11s")
    ap.add_argument("--pesos", default="yolo11s.pt")
    ap.add_argument("--epocas", type=int, default=80)
    ap.add_argument("--lote", type=int, default=8)
    ap.add_argument("--img", type=int, default=640)
    ap.add_argument("--paciencia", type=int, default=20)
    ap.add_argument("--lr0", type=float, default=None, help="tasa inicial; al afinar conviene una baja (0.0005)")
    ap.add_argument("--workers", type=int, default=0, help="procesos de carga (0 en Windows; 2 a 8 en Colab)")
    ap.add_argument("--calentamiento", type=float, default=3.0, help="épocas de calentamiento")
    a = ap.parse_args()
    extra = {"optimizer": "AdamW", "lr0": a.lr0} if a.lr0 else {}
    YOLO(os.path.join(BASE, a.pesos) if os.path.exists(os.path.join(BASE, a.pesos)) else a.pesos).train(
        data=os.path.join(BASE, a.datos, "datos.yaml"), epochs=a.epocas, imgsz=a.img, batch=a.lote, amp=True, workers=a.workers,
        patience=a.paciencia, project=os.path.join(BASE, "modelo", "yolo"), name=a.nombre, exist_ok=True,
        degrees=10, fliplr=0.5, mosaic=1.0, close_mosaic=5, cos_lr=True, plots=True, warmup_epochs=a.calentamiento, **extra)
