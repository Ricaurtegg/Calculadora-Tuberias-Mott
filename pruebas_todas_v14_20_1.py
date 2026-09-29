import subprocess, sys
suites=[
 'pruebas_v14_20_1.py',
 'pruebas_v14_20.py',
 'pruebas_v14_19.py',
 'pruebas_v14_18.py',
 'pruebas_v14_17.py',
 'pruebas_v14_16.py',
 'pruebas_v14_15.py',
 'pruebas_v14_13.py',
 'pruebas_v14_12.py',
]
for s in suites:
    print(f'\n===== {s} =====')
    subprocess.run([sys.executable,s],check=True)
print('\n[OK] REGRESIÓN RECIENTE + PULIDO PRE-V15 PASÓ COMPLETA.')
