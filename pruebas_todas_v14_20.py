"""Regresión acumulada del checkpoint V14.17.5 + módulo V14.20."""
import runpy
from pathlib import Path
BASE = Path(__file__).resolve().parent
runpy.run_path(str(BASE / 'pruebas_todas_v14_19.py'), run_name='__main__')
runpy.run_path(str(BASE / 'pruebas_v14_20.py'), run_name='__main__')
print('\n[OK] REGRESIÓN ACUMULADA + COMPARADOR DE ESCENARIOS V14.20 COMPLETADAS.')
print('     Checkpoint de distribución: V14.17.6 ESTABLE')
