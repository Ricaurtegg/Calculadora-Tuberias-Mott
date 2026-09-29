import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
pruebas = ["pruebas_todas_v14_4.py", "pruebas_v14_5.py"]

fallo = False
for nombre in pruebas:
    print("\n" + "=" * 78)
    print(f"Ejecutando {nombre}")
    print("=" * 78)
    r = subprocess.run([sys.executable, str(BASE / nombre)])
    if r.returncode != 0:
        print(f"[FALLO] {nombre} (código {r.returncode})")
        fallo = True
        break
    print(f"[OK] PASO {nombre}")

print("\n" + "=" * 78)
if fallo:
    print("[FALLO] EL CONJUNTO V14.5 DETECTÓ AL MENOS UNA REGRESIÓN.")
    raise SystemExit(1)
else:
    print("[OK] TODAS LAS PRUEBAS DISPONIBLES HASTA V14.5 PASARON.")
    print("     Motor hidráulico / Mott anterior: OK")
    print("     OCR + interpretación espacial V14.3: OK")
    print("     Visión geométrica OpenCV V14.4: OK")
    print("     Expediente consolidado y faltantes V14.5: OK")
print("=" * 78)
