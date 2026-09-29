"""Regresión acumulada de la base V14.17.1 + módulo V14.14.

En equipos rápidos ejecuta toda la cadena histórica mediante pruebas_todas_v14_16.py
y después la batería específica V14.14. Puede tardar varios minutos porque incluye
OCR, Mott, flujo automático, banco maestro y auditoría física.
"""
import runpy
from pathlib import Path

BASE = Path(__file__).resolve().parent

runpy.run_path(str(BASE / "pruebas_todas_v14_16.py"), run_name="__main__")
runpy.run_path(str(BASE / "pruebas_v14_14.py"), run_name="__main__")

print("\n[OK] REGRESIÓN ACUMULADA + VISIÓN GEOMÉTRICA V14.14 COMPLETADAS.")
print("     Checkpoint de distribución: V14.17.2 ESTABLE")
