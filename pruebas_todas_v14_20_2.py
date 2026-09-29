"""Regresión del hotfix V14.20.2 sobre la base pre-V15."""
import subprocess
import sys

scripts = [
    "pruebas_v14_20_1.py",
    "pruebas_v14_20_2.py",
    "pruebas_v14_7.py",
    "pruebas_v14_9.py",
    "pruebas_v14_10.py",
    "pruebas_v14_11.py",
    "pruebas_v14_17.py",
    "pruebas_v14_19.py",
]

for script in scripts:
    print(f"\n=== {script} ===")
    rc = subprocess.run([sys.executable, script]).returncode
    if rc != 0:
        raise SystemExit(rc)

print("\n[OK] REGRESIÓN V14.20.2 / V14.17.7.1 COMPLETADA.")
