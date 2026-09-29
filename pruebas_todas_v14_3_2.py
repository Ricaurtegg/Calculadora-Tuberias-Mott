import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent

candidatos_previos = [
    "pruebas_todas_v14_3.py",
    "pruebas_todas_v14_2_2.py",
    "pruebas_todas_v14_2_1.py",
    "pruebas_todas_v14_2.py",
    "pruebas_todas_v13.py",
]
previo = next((x for x in candidatos_previos if (BASE / x).exists()), None)
pruebas = ([previo] if previo else []) + ["pruebas_v14_3_2.py"]

fallo = False
for archivo in pruebas:
    print("\n" + "=" * 78)
    print(f"Ejecutando {archivo}")
    print("=" * 78)
    r = subprocess.run([sys.executable, str(BASE / archivo)])
    if r.returncode != 0:
        print(f"[FALLO] {archivo} (código {r.returncode})")
        fallo = True
        break
    print(f"[OK] PASÓ {archivo}")

print("\n" + "=" * 78)
if fallo:
    print("[FALLO] EL CONJUNTO V14.3.2 DETECTÓ AL MENOS UNA REGRESIÓN.")
    raise SystemExit(1)
print("[OK] TODAS LAS PRUEBAS HASTA V14.3.2 PASARON.")
print("     Fusión estructurada figura -> datos: OK")
print("     P1/z1/hA desde figura confirmada: OK")
print("     Entrada/salida y posiciones gráficas: OK")
print("     No duplica tramos: OK")
print("=" * 78)
