import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
candidatos = [
    'pruebas_todas_v14_3_2.py',
    'pruebas_todas_v14_3.py',
    'pruebas_todas_v14_2_2.py',
]
previo = next((x for x in candidatos if (BASE / x).exists()), None)
pruebas = ([previo] if previo else []) + ['pruebas_v14_3_3.py']

fallo = False
for nombre in pruebas:
    print('\n' + '=' * 78)
    print(f'Ejecutando {nombre}')
    print('=' * 78)
    r = subprocess.run([sys.executable, str(BASE / nombre)])
    if r.returncode != 0:
        print(f'[FALLO] {nombre} (código {r.returncode})')
        fallo = True
        break
    print(f'[OK] PASÓ {nombre}')

print('\n' + '=' * 78)
if fallo:
    print('[FALLO] EL CONJUNTO V14.3.3 DETECTÓ AL MENOS UNA REGRESIÓN.')
    raise SystemExit(1)
print('[OK] TODAS LAS PRUEBAS DISPONIBLES HASTA V14.3.3 PASARON.')
print('     z1 OCR robusto: OK')
print('     entrada 0 % / salida 100 %: OK')
print('     persistencia del enunciado: OK')
print('=' * 78)
