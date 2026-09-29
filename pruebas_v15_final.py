from pathlib import Path

from clasificar_problema import identificar_clase_automaticamente
from consolidacion_datos import consolidar_resultado
from transferencia_v147 import construir_previsualizacion_transferencia
from reporte_final_v149 import construir_manifiesto_ejecucion
from flujo_automatico_v1410 import resolver_flujo_confirmado

BASE = Path(__file__).resolve().parent
EJ = BASE / "EJEMPLOS_MOTT_V15"

CASOS = [
    ("01_Mott_11_1_Clase_I.txt", "Clase I", "valor", 217.4, 0.03),
    ("02_Mott_11_2_Clase_II_A.txt", "Clase II-A", "Q_final", 0.0570, 0.015),
    ("03_Mott_11_3_Clase_II_B.txt", "Clase II-B", "Q_final", 0.0538, 0.02),
    ("04_Mott_11_4_Clase_II_C.txt", "Clase II-C", "Q_final", 0.955 * 0.028316846592, 0.02),
    ("05_Mott_11_5_Clase_III_A.txt", "Clase III-A", "D_mott", 0.309 * 0.3048, 0.012),
    ("06_Mott_11_6_Clase_III_B.txt", "Clase III-B", "P2_calculada", 100.48 * 6894.757293168, 0.015),
]

def rel(a, b):
    return abs(float(a)-float(b))/max(abs(float(b)), 1e-30)

print("="*76)
print("V15.0 FINAL — VALIDACION DE LOS 6 CASOS PATRON DE MOTT")
print("="*76)

for i, (archivo, clase, campo, ref, tol) in enumerate(CASOS, 1):
    txt = (EJ / archivo).read_text(encoding="utf-8")
    r0 = identificar_clase_automaticamente(txt)
    if r0.get("clase") != clase:
        raise AssertionError(f"{archivo}: clase {r0.get('clase')} != {clase}")
    r = consolidar_resultado(r0, txt)
    falt = r.get("expediente_v145", {}).get("faltantes", [])
    if falt:
        raise AssertionError(f"{archivo}: no debe pedir datos adicionales: {falt}")
    p = construir_previsualizacion_transferencia(r, txt)
    if not p.get("listo_para_transferir"):
        raise AssertionError(f"{archivo}: V14.7 bloqueado: {p.get('bloqueos')}")
    m = construir_manifiesto_ejecucion(r, txt, p)
    f = resolver_flujo_confirmado(r, txt, p, p["firma"], m)
    sol = f["resultado_solver"]
    obt = float(sol[campo])
    e = rel(obt, ref)
    if e > tol:
        raise AssertionError(f"{archivo}: {campo}={obt:.12g}, ref={ref:.12g}, error={100*e:.3f}%")
    if f["auditoria"].get("estado") == "ERROR":
        raise AssertionError(f"{archivo}: auditoría matemática ERROR")
    print(f"[{i}/6] {clase:<11} OK | {campo}={obt:.9g} | error ref={100*e:.3f}%")

print("\n✅ V15.0 FINAL: LOS 6 EJEMPLOS TXT SE CLASIFICAN, NO PIDEN DATOS Y RESUELVEN.")
