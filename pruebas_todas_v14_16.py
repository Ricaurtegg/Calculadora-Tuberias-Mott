"""Regresión acumulada: ejecuta la cadena histórica hasta V14.17 y luego V14.16."""
import runpy
from pathlib import Path

BASE = Path(__file__).resolve().parent

# La suite histórica completa puede tardar varios minutos en algunos equipos.
runpy.run_path(str(BASE / "pruebas_todas_v14_17.py"), run_name="__main__")
runpy.run_path(str(BASE / "pruebas_v14_16.py"), run_name="__main__")

print("\n[OK] REGRESIÓN ACUMULADA + AUDITORÍA FÍSICA V14.16 COMPLETADAS.")
