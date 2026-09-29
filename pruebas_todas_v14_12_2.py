import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
pruebas = ["pruebas_todas_v14_12.py", "pruebas_v14_12_2.py"]
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
    print(f"[OK] PASÓ {nombre}")

print("\n" + "=" * 78)
if fallo:
    print("[FALLO] EL CONJUNTO V14.12.2 DETECTÓ AL MENOS UNA REGRESIÓN.")
    raise SystemExit(1)
print("[OK] TODAS LAS PRUEBAS DISPONIBLES HASTA V14.12.2 PASARON.")
print("     Motor hidráulico / Mott anterior: OK")
print("     Parser robusto y trazabilidad V14.12.1: OK")
print("     Auditoría específica II-A Mott Ec. (11-3) V14.8.3: OK")
print("=" * 78)
