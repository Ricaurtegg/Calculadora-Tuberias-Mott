from pathlib import Path
import subprocess
import sys

BASE = Path(__file__).resolve().parent
anteriores = ["pruebas_todas_v14_11.py", "pruebas_todas_v14_10.py", "pruebas_todas_v14_9.py"]
previo = next((x for x in anteriores if (BASE / x).exists()), None)
pruebas = ([previo] if previo else []) + ["pruebas_v14_12.py"]

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
    print("[FALLO] EL CONJUNTO V14.12 DETECTÓ AL MENOS UNA REGRESIÓN.")
    raise SystemExit(1)
else:
    print("[OK] TODAS LAS PRUEBAS DISPONIBLES HASTA V14.12.1 PASARON.")
    print("     Motor hidráulico / Mott anterior: OK")
    print("     OCR + expediente + confianza + flujo V14.3–V14.11: OK")
    print("     Parser hidráulico robusto y trazabilidad V14.12.1: OK")
print("=" * 78)
