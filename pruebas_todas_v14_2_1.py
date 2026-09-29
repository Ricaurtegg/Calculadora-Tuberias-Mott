import subprocess
import sys

ARCHIVOS = [
    'pruebas_todas_v14_2.py',
    'pruebas_v14_2_1.py',
]

fallo = False
for archivo in ARCHIVOS:
    print('\n' + '=' * 78)
    print(f'Ejecutando {archivo}')
    print('=' * 78)
    r = subprocess.run([sys.executable, '-X', 'utf8', archivo])
    if r.returncode != 0:
        print(f'[FALLO] {archivo}')
        fallo = True
        break
    print(f'[OK] PASO {archivo}')

print('\n' + '=' * 78)
if fallo:
    print('[FALLO] AL MENOS UNA PRUEBA HASTA V14.2.1 FALLO.')
    raise SystemExit(1)
else:
    print('[OK] TODAS LAS PRUEBAS HASTA V14.2.1 PASARON.')
    print('     V14.2 OCR: OK')
    print('     Coherencia deposito 1 / deposito 2: OK')
print('=' * 78)
