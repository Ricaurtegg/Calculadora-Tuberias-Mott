"""Maestro de regresión hasta V14.2.

No ejecuta pruebas_v14_1.py antigua porque V14.2 cambia deliberadamente la
conducta del PDF escaneado: ahora usa OCR en lugar de devolver texto vacío.
"""
import os
from pathlib import Path
import subprocess
import sys

BASE = Path(__file__).resolve().parent
PRUEBAS = [
    ("pruebas_todas_v13.py", True),
    ("pruebas_v14_1_1.py", False),
    ("pruebas_v14_2.py", True),
]

env = os.environ.copy()
env["PYTHONUTF8"] = "1"
env["PYTHONIOENCODING"] = "utf-8"

for nombre, obligatorio in PRUEBAS:
    ruta = BASE / nombre
    print("\n" + "=" * 78)
    print(f"Ejecutando {nombre}")
    print("=" * 78)

    if not ruta.exists():
        if obligatorio:
            print(f"[FALLO] Falta el archivo obligatorio {nombre}.")
            raise SystemExit(1)
        print(f"[AVISO] {nombre} no está presente; se omite.")
        continue

    r = subprocess.run([sys.executable, "-X", "utf8", str(ruta)], cwd=BASE, env=env)
    if r.returncode != 0:
        print(f"[FALLO] {nombre} (código {r.returncode})")
        raise SystemExit(r.returncode)
    print(f"[OK] PASO {nombre}")

print("\n" + "=" * 78)
print("[OK] TODAS LAS PRUEBAS HASTA V14.2 PASARON.")
print("     V13 hidráulico / Mott: OK")
print("     V14.1.1 parser de accesorios: OK si estaba presente")
print("     TXT / DOCX / PDF seleccionable: OK")
print("     PNG / JPG / JPEG por OCR: OK")
print("     PDF escaneado por OCR: OK")
print("=" * 78)
