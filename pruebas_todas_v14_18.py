"""Regresión acumulada del checkpoint V14.17.3.1 + módulo V14.18."""
import runpy
from pathlib import Path
BASE = Path(__file__).resolve().parent
runpy.run_path(str(BASE / 'pruebas_todas_v14_15.py'), run_name='__main__')
runpy.run_path(str(BASE / 'pruebas_v14_18.py'), run_name='__main__')
print('\n[OK] REGRESIÓN ACUMULADA + REPORTE TÉCNICO V2 V14.18 COMPLETADAS.')
print('     Checkpoint de distribución: V14.17.4 ESTABLE')
