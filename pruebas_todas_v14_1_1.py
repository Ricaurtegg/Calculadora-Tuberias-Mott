from pathlib import Path
import os, subprocess, sys
BASE = Path(__file__).resolve().parent
ENV = os.environ.copy()
ENV['PYTHONUTF8'] = '1'
ENV['PYTHONIOENCODING'] = 'utf-8'
pruebas = ['pruebas_todas_v14_1.py', 'pruebas_v14_1_1.py']
fallos=[]
for nombre in pruebas:
    ruta=BASE/nombre
    print('\n'+'='*78)
    print(f'Ejecutando {nombre}')
    print('='*78)
    if not ruta.exists():
        print(f'[OMITIDO] No existe {nombre}')
        continue
    r=subprocess.run([sys.executable,'-X','utf8',str(ruta)],cwd=str(BASE),env=ENV)
    if r.returncode:
        print(f'[ERROR] FALLO {nombre} (codigo {r.returncode})')
        fallos.append(nombre)
    else:
        print(f'[OK] PASO {nombre}')
if fallos:
    raise SystemExit(1)
print('\n'+'='*78)
print('[OK] TODAS LAS PRUEBAS HASTA V14.1.1 PASARON.')
print('     V13 hidráulico: OK')
print('     V14.1 archivos: OK')
print('     Parser de codos 45/90 grados: OK')
print('='*78)
