from pathlib import Path
import copy
import io
import zipfile

from auditoria_fisica_v1416 import (
    VERSION_AUDITORIA_FISICA,
    auditar_fisica,
    presion_vapor_agua_kpa,
)
from clasificar_problema import identificar_clase_automaticamente
from transferencia_v147 import construir_previsualizacion_transferencia
from reporte_final_v149 import construir_manifiesto_ejecucion, reporte_markdown, reporte_docx
from flujo_automatico_v1410 import resolver_flujo_confirmado
from banco_regresion_v1417 import ejecutar_banco_maestro

BASE = Path(__file__).resolve().parent
APP = (BASE / "app.py").read_text(encoding="utf-8")
FLOW = (BASE / "flujo_automatico_v1410.py").read_text(encoding="utf-8")
REPORT = (BASE / "reporte_final_v149.py").read_text(encoding="utf-8")


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)


def contexto_base(clase="Clase II-C", fluido="Agua a 20 °C"):
    return {
        "clase": clase,
        "prefill": {
            "fluido_app": fluido,
            "P1_kpa": 135.0, "P2_kpa": 0.0,
            "z1_m": 31.2, "z2_m": 8.4, "hA_m": 0.0, "hR_m": 0.0,
            "tramos": [
                {"numero": 1, "L_m": 68.5, "D_m": 0.100, "material": "Acero comercial o soldado"},
                {"numero": 2, "L_m": 96.3, "D_m": 0.075, "material": "Plástico"},
            ],
            "transiciones": [{"entre": 1, "tipo": "Contracción súbita"}],
        },
    }


def resultado_sistema(v1=3.0, v2=5.5, re1=3e5, re2=4e5):
    return {
        "sistema": {
            "resultados": [
                {"L (m)": 68.5, "D (m)": 0.1, "V (m/s)": v1, "Re": re1, "f Darcy": 0.018, "hf (m)": 6.0, "hm (m)": 0.7, "ε/D": 0.00046},
                {"L (m)": 96.3, "D (m)": 0.075, "V (m/s)": v2, "Re": re2, "f Darcy": 0.014, "hf (m)": 27.0, "hm (m)": 1.6, "ε/D": 0.000004},
            ],
            "total_hf": 33.0, "total_hm_accesorios": 2.3, "total_hm_transiciones": 0.2, "hL_total": 35.5,
        }
    }


def iic_completo():
    return {
        "clase": "Clase II-C", "confianza": 96,
        "prefill": {
            "fluido_app": "Agua a 20 °C", "fluido_detectado": "Agua a 20 °C",
            "P1_kpa": 135.0, "P2_kpa": 0.0,
            "z1_m": 31.2, "z2_m": 8.4, "hA_m": 0.0, "hR_m": 0.0,
            "v1_tipo": "deposito", "v2_tipo": "deposito",
            "tramos": [
                {"numero": 1, "L_m": 68.5, "D_m": 0.100, "material": "Acero comercial o soldado",
                 "accesorios": [{"nombre": "Entrada — borde cuadrado/agudo", "cantidad": 1}, {"nombre": "Codo 90° estándar", "cantidad": 2}], "componentes_graficos": []},
                {"numero": 2, "L_m": 96.3, "D_m": 0.075, "material": "Plástico",
                 "accesorios": [{"nombre": "Salida hacia depósito grande", "cantidad": 1}, {"nombre": "Válvula de compuerta — totalmente abierta", "cantidad": 1}], "componentes_graficos": []},
            ],
            "transiciones": [{"entre": 1, "tipo": "Contracción súbita", "angulo_grados": None}],
        },
    }


print("[1/15] V14.16 activo...")
ok(VERSION_AUDITORIA_FISICA == "V14.16", VERSION_AUDITORIA_FISICA)
print("  OK")

print("[2/15] Caso plausible no genera falsos errores/advertencias...")
a2 = auditar_fisica(contexto_base(), resultado_sistema(), {"nombre": "Agua a 20 °C"})
ok(a2["estado"] == "OK", a2)
ok(a2["errores"] == 0 and a2["advertencias"] == 0, a2)
print("  OK")

print("[3/15] Reynolds de transición produce REVISAR, sin modificar el solver...")
r3 = resultado_sistema(re1=3000)
a3 = auditar_fisica(contexto_base(), r3, {"nombre": "Agua a 20 °C"})
ok(a3["estado"] == "REVISAR", a3)
ok(any(x["codigo"] == "REYNOLDS_1" and x["nivel"] == "warning" for x in a3["checks"]), a3)
ok(r3["sistema"]["resultados"][0]["Re"] == 3000, "V14.16 modificó el resultado")
print("  OK")

print("[4/15] Velocidad extrema se marca como advertencia física...")
a4 = auditar_fisica(contexto_base(), resultado_sistema(v2=12.0), {"nombre": "Agua a 20 °C"})
ok(a4["estado"] == "REVISAR", a4)
ok(any(x["codigo"] == "VELOCIDAD_2" and x["nivel"] == "warning" for x in a4["checks"]), a4)
print("  OK")

print("[5/15] Presión absoluta imposible produce ERROR físico...")
c5 = contexto_base(); c5["prefill"]["P1_kpa"] = -110.0
A5 = auditar_fisica(c5, resultado_sistema(), {"nombre": "Agua a 20 °C"})
ok(A5["estado"] == "ERROR", A5)
ok(any(x["codigo"] == "PABS_1" and x["nivel"] == "error" for x in A5["checks"]), A5)
print("  OK")

print("[6/15] Agua cerca de presión de vapor se detecta...")
pvap20 = presion_vapor_agua_kpa(20.0)
ok(2.0 < pvap20 < 3.0, pvap20)
c6 = contexto_base(); c6["prefill"]["P1_kpa"] = -96.0  # Pabs≈5.325 kPa; margen≈3 kPa
A6 = auditar_fisica(c6, resultado_sistema(), {"nombre": "Agua a 20 °C"})
ok(any(x["codigo"] == "VAPOR_AGUA_1" and x["nivel"] == "warning" for x in A6["checks"]), A6)
print("  OK")

print("[7/15] Carga negativa de bomba queda como ERROR de convención...")
c7 = contexto_base(); c7["prefill"]["hA_m"] = -3.0
A7 = auditar_fisica(c7, resultado_sistema(), {"nombre": "Agua a 20 °C"})
ok(any(x["codigo"] == "HA_SIGNO" and x["nivel"] == "error" for x in A7["checks"]), A7)
print("  OK")

print("[8/15] Bomba positiva informa el alcance NPSH sin inventarlo...")
c8 = contexto_base(); c8["prefill"]["hA_m"] = 25.0
A8 = auditar_fisica(c8, resultado_sistema(), {"nombre": "Agua a 20 °C"})
ok(any(x["codigo"] == "NPSH_ALCANCE" and x["nivel"] == "info" and not x["evaluable"] for x in A8["checks"]), A8)
print("  OK")

print("[9/15] Diámetro dimensionalmente sospechoso se marca para revisión...")
c9 = contexto_base(); c9["prefill"]["tramos"][0]["D_m"] = 0.001
r9 = resultado_sistema(); r9["sistema"]["resultados"][0]["D (m)"] = 0.001
A9 = auditar_fisica(c9, r9, {"nombre": "Agua a 20 °C"})
ok(any(x["codigo"] == "DIAMETRO_1" and x["nivel"] == "warning" for x in A9["checks"]), A9)
print("  OK")

print("[10/15] Fluido potencialmente no newtoniano genera advertencia de modelo...")
c10 = contexto_base(fluido="Miel — 21 °C [aprox.]")
A10 = auditar_fisica(c10, resultado_sistema(), {"nombre": "Miel — 21 °C [aprox.]"})
ok(any(x["codigo"] == "FLUIDO_MODELO_NEWTONIANO" and x["nivel"] == "warning" for x in A10["checks"]), A10)
print("  OK")

print("[11/15] Flujo V14.10 incorpora V14.16 en un II-C normal...")
r11 = iic_completo(); en11 = "Determine el caudal Q del sistema."
p11 = construir_previsualizacion_transferencia(r11, en11)
ok(p11["listo_para_transferir"], p11.get("bloqueos"))
m11 = construir_manifiesto_ejecucion(r11, en11, p11)
f11 = resolver_flujo_confirmado(r11, en11, p11, p11["firma"], m11)
ok(f11["estado"] == "OK", f11)
ok(f11["estado_integral"] == "OK", f11)
ok(f11["auditoria_fisica_v1416"]["estado"] == "OK", f11["auditoria_fisica_v1416"])
ok(any(x["id"] == "auditoria_fisica" for x in f11["pasos"]), f11["pasos"])
print("  OK")

print("[12/15] Una advertencia V14.16 no cambia el significado histórico de estado V14.10...")
EN12 = (
    'Agua a 68 °F fluye entre dos depósitos. P1 = 35 psig y P2 = 0 kPa. '
    'Las elevaciones son z1 = 120 ft y z2 = 8.4 m. El tramo 1 tiene una longitud '
    'de 250 ft y es una tubería de acero comercial NPS 4 Schedule 40. '
    'Desprecie las pérdidas menores y determine el caudal Q.'
)
r12 = identificar_clase_automaticamente(EN12)
p12 = construir_previsualizacion_transferencia(r12, EN12)
m12 = construir_manifiesto_ejecucion(r12, EN12, p12)
f12 = resolver_flujo_confirmado(r12, EN12, p12, p12["firma"], m12)
ok(f12["auditoria"]["estado"] == "OK" and f12["estado"] == "OK", f12)
ok(f12["auditoria_fisica_v1416"]["estado"] == "REVISAR", f12["auditoria_fisica_v1416"])
ok(f12["estado_integral"] == "REVISAR", f12)
print("  OK")

print("[13/15] III-A también puede auditarse físicamente con D calculado...")
c13 = {"clase": "Clase III-A", "prefill": {"fluido_app": "Agua a 20 °C", "P1_kpa": 100.0, "P2_kpa": 0.0, "z1_m": 10.0, "z2_m": 0.0, "hA_m": 0.0, "hR_m": 0.0, "tramos": [{"L_m": 50.0, "D_m": None, "material": "Acero comercial o soldado"}]}}
r13 = {"D_mott": 0.08, "V": 2.0, "Re": 160000.0, "f": 0.02, "hf": 2.55, "residual": 0.0}
A13 = auditar_fisica(c13, r13, {"nombre": "Agua a 20 °C"})
ok(A13["errores"] == 0, A13)
ok(any(x["codigo"] == "DIAMETRO_1" for x in A13["checks"]), A13)
print("  OK")

print("[14/15] V14.16 llega a Markdown y Word V14.9...")
rep14 = f11["reporte_v149"]
md14 = reporte_markdown(rep14)
ok("Auditoría física ampliada V14.16" in md14, md14[-3000:])
docx14 = reporte_docx(rep14)
with zipfile.ZipFile(io.BytesIO(docx14)) as z:
    xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
ok("Auditoría física ampliada V14.16" in xml, "Word no contiene V14.16")
print("  OK")

print("[15/15] Integración app/flujo/reporte y banco V14.17 siguen intactos...")
for txt, tokens in (
    (APP, ("auditoria_fisica_v1416", "V14.16 —", "mostrar_auditoria_fisica_v1416")),
    (FLOW, ("auditar_fisica", "auditoria_fisica_v1416", "estado_integral")),
    (REPORT, ("auditoria_fisica_v1416", "Auditoría física ampliada V14.16")),
):
    for tok in tokens:
        ok(tok in txt, f"Falta integración {tok}")
b = ejecutar_banco_maestro(verbose=False)
ok(b["ok"] == 50 and b["total"] == 50, b)
print("  OK: banco V14.17 = 50/50")

print("\nTODAS LAS PRUEBAS V14.16 DE AUDITORÍA FÍSICA AMPLIADA PASARON.")
