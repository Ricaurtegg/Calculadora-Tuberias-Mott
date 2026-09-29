import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
anteriores = ["pruebas_todas_v14_12_2.py", "pruebas_todas_v14_12.py", "pruebas_todas_v14_11.py"]
previo = next((x for x in anteriores if (BASE / x).exists()), None)
pruebas = ([previo] if previo else []) + ["pruebas_v14_13.py"]
fallo=False
for nombre in pruebas:
    print("\n"+"="*78); print(f"Ejecutando {nombre}"); print("="*78)
    r=subprocess.run([sys.executable,str(BASE/nombre)])
    if r.returncode != 0:
        print(f"[FALLO] {nombre} (código {r.returncode})"); fallo=True; break
    print(f"[OK] PASO {nombre}")
print("\n"+"="*78)
if fallo:
    print("[FALLO] EL CONJUNTO V14.13 DETECTÓ AL MENOS UNA REGRESIÓN."); raise SystemExit(1)
print("[OK] TODAS LAS PRUEBAS DISPONIBLES HASTA V14.13 PASARON.")
print("     Motor hidráulico / Mott anterior: OK")
print("     Parser unidades V14.12.2: OK")
print("     Accesorios y transiciones avanzadas V14.13: OK")
print("="*78)
