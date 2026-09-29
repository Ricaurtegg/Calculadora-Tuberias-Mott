"""Regresión acumulada del checkpoint V14.17.4 + módulo V14.19."""
import runpy
from pathlib import Path
BASE = Path(__file__).resolve().parent
runpy.run_path(str(BASE / 'pruebas_todas_v14_18.py'), run_name='__main__')
runpy.run_path(str(BASE / 'pruebas_v14_19.py'), run_name='__main__')
print('\n[OK] REGRESIÓN ACUMULADA + PROCEDIMIENTO MOTT V14.19 COMPLETADAS.')
print('     Checkpoint de distribución: V14.17.5 ESTABLE')
