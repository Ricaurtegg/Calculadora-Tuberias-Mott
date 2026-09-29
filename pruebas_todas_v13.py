"""Ejecutor maestro de regresión hasta V13 — corrección Windows/PowerShell.

Motivo de esta revisión:
Los tests individuales pueden imprimir Unicode correctamente cuando escriben
直接amente en la consola de Windows. Sin embargo, si subprocess captura stdout
mediante una tubería, Python puede usar cp1252 y fallar con símbolos como
→, ↔ o ✅. Por eso este ejecutor NO captura la salida de los procesos hijos:
la deja ir directamente a la misma consola, igual que al ejecutar cada test
por separado. Además fuerza UTF-8 como protección adicional.
"""

import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent

ANTERIORES = [
    "pruebas_v9.py",
    "pruebas_v10.py",
    "pruebas_regresion_clases.py",
    "pruebas_v11.py",
    "pruebas_v12.py",
]

V13_OBLIGATORIAS = [
    "pruebas_mott_cap11.py",
    "pruebas_recalculo_v13.py",
    "pruebas_integridad_v13.py",
]

lineas_reporte = [
    "REPORTE MAESTRO DE PRUEBAS V13",
    f"Fecha: {datetime.now().isoformat(timespec='seconds')}",
    "",
]


def ejecutar(nombre, obligatorio=False):
    ruta = BASE / nombre

    if not ruta.exists():
        if obligatorio:
            print(f"[ERROR] FALTA PRUEBA OBLIGATORIA: {nombre}", flush=True)
            lineas_reporte.append(f"FALTA: {nombre}")
            return False

        print(
            f"[AVISO] {nombre} no está presente; se omite por ser prueba histórica opcional.",
            flush=True,
        )
        lineas_reporte.append(f"OMITIDA: {nombre}")
        return True

    print("\n" + "=" * 78, flush=True)
    print(f"Ejecutando {nombre}", flush=True)
    print("=" * 78, flush=True)

    # Protección para Windows/PowerShell:
    # 1) el hijo hereda la consola directamente (sin capture_output),
    # 2) se fuerza UTF-8 en el intérprete hijo.
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    proc = subprocess.run(
        [sys.executable, "-X", "utf8", str(ruta)],
        cwd=str(BASE),
        env=env,
    )

    if proc.returncode != 0:
        print(f"[FALLO] {nombre} (código {proc.returncode})", flush=True)
        lineas_reporte.append(f"FALLÓ: {nombre}")
        return False

    print(f"[OK] PASÓ {nombre}", flush=True)
    lineas_reporte.append(f"OK: {nombre}")
    return True


ok = True

for nombre in ANTERIORES:
    ok = ejecutar(nombre, obligatorio=False) and ok

for nombre in V13_OBLIGATORIAS:
    resultado = ejecutar(nombre, obligatorio=True)
    ok = resultado and ok
    if not resultado:
        break

lineas_reporte.extend([
    "",
    "RESULTADO FINAL: " + ("APROBADO" if ok else "FALLÓ"),
])

(BASE / "reporte_pruebas_v13.txt").write_text(
    "\n".join(lineas_reporte),
    encoding="utf-8",
)

print("\n" + "=" * 78, flush=True)
if ok:
    print("[OK] TODAS LAS PRUEBAS DISPONIBLES HASTA V13 PASARON.", flush=True)
    print("     Banco Mott 11.1-11.6: OK", flush=True)
    print("     18 pruebas de recálculo: OK", flush=True)
    print("     Integridad de catálogos/unidades: OK", flush=True)
    print("     Reporte: reporte_pruebas_v13.txt", flush=True)
else:
    print("[FALLO] EL CONJUNTO V13 DETECTÓ AL MENOS UNA REGRESIÓN.", flush=True)
    print("        Revise arriba el primer archivo que falló.", flush=True)
print("=" * 78, flush=True)

raise SystemExit(0 if ok else 1)
