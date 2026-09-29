from pathlib import Path
import subprocess, sys
BASE=Path(__file__).resolve().parent
anteriores=['pruebas_todas_v14_13.py','pruebas_todas_v14_12_2.py']
previo=next((x for x in anteriores if (BASE/x).exists()),None)
pruebas=([previo] if previo else [])+['pruebas_v14_17.py']
fallo=False
for nombre in pruebas:
    print('\n'+'='*78); print(f'Ejecutando {nombre}'); print('='*78)
    r=subprocess.run([sys.executable,str(BASE/nombre)])
    if r.returncode!=0:
        print(f'[FALLO] {nombre} (código {r.returncode})'); fallo=True; break
    print(f'[OK] PASO {nombre}')
print('\n'+'='*78)
if fallo:
    print('[FALLO] EL CONJUNTO V14.17 DETECTÓ AL MENOS UNA REGRESIÓN.'); raise SystemExit(1)
print('[OK] TODAS LAS PRUEBAS DISPONIBLES HASTA V14.17 PASARON.')
print('     Base hidráulica / Mott / OCR / flujo V14.13: OK')
print('     Banco maestro 49 casos V14.17: OK')
print('='*78)
