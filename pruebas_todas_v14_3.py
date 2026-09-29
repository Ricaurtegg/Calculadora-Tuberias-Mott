"""Ejecutor maestro V14.3.

Ejecuta primero la prueba maestra anterior disponible y después obliga a pasar
la interpretación de figuras V14.3. Se fuerza UTF-8 para evitar errores de
consola de Windows con símbolos Unicode.
"""
from pathlib import Path
import os
import subprocess
import sys

BASE = Path(__file__).resolve().parent

anteriores = [
    "pruebas_todas_v14_2_2.py",
    "pruebas_todas_v14_2_1.py",
    "pruebas_todas_v14_2.py",
]

previa = next((x for x in anteriores if (BASE / x).exists()), None)
obligatorias = ["pruebas_v14_3.py"]
archivos = ([previa] if previa else []) + obligatorias

env = os.environ.copy()
env["PYTHONUTF8"] = "1"
env["PYTHONIOENCODING"] = "utf-8"

fallo = False
for nombre in archivos:
    print("\n" + "=" * 78)
    print(f"Ejecutando {nombre}")
    print("=" * 78)
    r = subprocess.run([sys.executable, "-X", "utf8", str(BASE / nombre)], env=env)
    if r.returncode != 0:
        print(f"[FALLO] {nombre} (código {r.returncode})")
        fallo = True
        break
    print(f"[OK] PASÓ {nombre}")

print("\n" + "=" * 78)
if fallo:
    print("[FALLO] EL CONJUNTO V14.3 DETECTÓ AL MENOS UNA REGRESIÓN.")
    raise SystemExit(1)

print("[OK] TODAS LAS PRUEBAS DISPONIBLES HASTA V14.3 PASARON.")
if previa:
    print(f"     Base anterior: {previa} — OK")
else:
    print("     Aviso: no se encontró una prueba maestra V14.2.x; se validó V14.3 de forma independiente.")
print("     Interpretación espacial de figuras: OK")
print("     PNG + PDF escaneado de esquema: OK")
print("=" * 78)
