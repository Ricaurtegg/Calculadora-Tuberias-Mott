"""Regresión acumulada del checkpoint V14.17.2 + módulo V14.15.

Ejecuta toda la cadena de V14.17.2 (incluyendo banco V14.17, auditoría física
V14.16 y visión V14.14) y después la batería específica de diagramas V14.15.
"""
import runpy
from pathlib import Path

BASE = Path(__file__).resolve().parent
runpy.run_path(str(BASE / 'pruebas_todas_v14_14.py'), run_name='__main__')
runpy.run_path(str(BASE / 'pruebas_v14_15.py'), run_name='__main__')

print('\n[OK] REGRESIÓN ACUMULADA + DIAGRAMAS HIDRÁULICOS V14.15 COMPLETADAS.')
print('     Checkpoint de distribución: V14.17.3 ESTABLE')
