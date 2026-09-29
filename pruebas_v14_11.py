from pathlib import Path
import copy

from clasificar_problema import identificar_clase_automaticamente
from consolidacion_datos import consolidar_resultado
from confianza_datos_v1411 import (
    VERSION_CONFIANZA,
    construir_confianza_datos,
    aplicar_confirmaciones,
    confirmar_todos_pendientes,
)
from transferencia_v147 import construir_previsualizacion_transferencia
from reporte_final_v149 import construir_manifiesto_ejecucion, construir_reporte_final, reporte_markdown, reporte_docx

BASE = Path(__file__).resolve().parent
APP = (BASE / "app.py").read_text(encoding="utf-8")


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)


def entrada(rep, clave, tramo=None):
    for x in rep.get("entradas") or []:
        if x.get("clave") == clave and x.get("tramo") == tramo:
            return x
    raise AssertionError(f"No existe {clave} tramo={tramo}: {rep}")


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
                 "accesorios": [{"nombre": "Entrada — borde cuadrado/agudo", "cantidad": 1}], "componentes_graficos": []},
                {"numero": 2, "L_m": 96.3, "D_m": 0.075, "material": "Plástico",
                 "accesorios": [{"nombre": "Salida hacia depósito grande", "cantidad": 1}], "componentes_graficos": []},
            ],
            "transiciones": [{"entre": 1, "tipo": "Contracción súbita", "angulo_grados": None}],
        },
    }


print("[1/15] Versión V14.11 y texto pegado queda con confianza alta...")
r1 = iic_completo()
rep1 = construir_confianza_datos(r1, "Determine el caudal Q.", {"modo_entrada": "⌨️ Escribir o pegar"})
ok(VERSION_CONFIANZA == "V14.11", VERSION_CONFIANZA)
ok(rep1["listo_para_v147"], rep1)
ok(entrada(rep1, "P1_kpa")["confianza_pct"] == 98.0, entrada(rep1, "P1_kpa"))
print("  OK")

print("[2/15] Archivo con texto directo queda alto sin confirmación extra...")
ctx2 = {"modo_entrada": "📎 Subir archivo", "archivo_info": {"ocr_aplicado": False, "metodo": "DOCX"}, "texto_extraido_original": "abc"}
rep2 = construir_confianza_datos(r1, "abc", ctx2)
ok(entrada(rep2, "P1_kpa")["confianza_pct"] == 97.0, entrada(rep2, "P1_kpa"))
ok(rep2["listo_para_v147"], rep2)
print("  OK")

print("[3/15] OCR sin edición queda en confianza media y exige confirmación...")
texto3 = "Agua a 20 C. P1=135 kPa. P2=0 kPa. z1=31.2 m. z2=8.4 m. Determine el caudal."
ctx3 = {"modo_entrada": "📎 Subir archivo", "archivo_info": {"ocr_aplicado": True, "metodo": "OCR"}, "texto_extraido_original": texto3}
rep3 = construir_confianza_datos(r1, texto3, ctx3)
ok(entrada(rep3, "P1_kpa")["nivel"] == "Media", entrada(rep3, "P1_kpa"))
ok(not rep3["listo_para_v147"] and rep3["pendientes_confirmacion"] > 0, rep3)
print("  OK")

print("[4/15] OCR editado parcialmente sigue requiriendo confirmación..." )
ctx4 = copy.deepcopy(ctx3)
ctx4["texto_extraido_original"] = texto3.replace("135", "l35")
rep4 = construir_confianza_datos(r1, texto3, ctx4)
ok(entrada(rep4, "P1_kpa")["confianza_pct"] == 88.0, entrada(rep4, "P1_kpa"))
ok(not rep4["listo_para_v147"], rep4)
print("  OK")

print("[5/15] Revisión OCR explícita sube a confianza alta...")
ctx5r = copy.deepcopy(ctx3)
ctx5r["ocr_revisado_explicito"] = True
rep5r = construir_confianza_datos(r1, texto3, ctx5r)
ok(entrada(rep5r, "P1_kpa")["confianza_pct"] == 94.0, entrada(rep5r, "P1_kpa"))
ok(rep5r["listo_para_v147"], rep5r)
print("  OK")

print("[6/15] Inferencia segura V14.5 recibe confianza 99 %...")
en5 = "Agua a 20 °C va del depósito A presurizado a P1=100 kPa y z1=10 m hacia el depósito B abierto a la atmósfera a z2=0 m. Determine el caudal. Tubería de 40 m y 80 mm de acero comercial. Desprecie pérdidas menores."
r5 = identificar_clase_automaticamente(en5)
r5 = consolidar_resultado(r5, en5)
rep5 = construir_confianza_datos(r5, en5, {"modo_entrada": "⌨️ Escribir o pegar"})
p2 = entrada(rep5, "P2_kpa")
ok(p2["confianza_pct"] == 99.0 and "V14.5" in p2["fuente"], p2)
print("  OK")

print("[7/15] Respuesta explícita V14.6 recibe 100 %...")
r6 = iic_completo()
r6["respuestas_v146"] = [{"id": "material::2", "clave": "material", "tramo": 2, "respuesta": "Plástico", "fuente": "usuario V14.6"}]
rep6 = construir_confianza_datos(r6, "Determine Q", {"modo_entrada": "⌨️ Escribir o pegar"})
m2 = entrada(rep6, "material", 2)
ok(m2["confianza_pct"] == 100.0 and m2["fuente"] == "usuario V14.6", m2)
print("  OK")

print("[8/15] Dato completado solo desde figura conserva confianza visual conservadora...")
r7 = iic_completo(); r7["prefill"]["P1_kpa"] = 135.0
fig7 = {"hallazgos": [{"tipo": "P1", "texto": "P1 = 135 kPa", "confianza": 72.0, "estado": "Confirmar"}]}
rep7 = construir_confianza_datos(r7, "Determine el caudal Q del sistema.", {"modo_entrada": "⌨️ Escribir o pegar"}, figura=fig7)
p17 = entrada(rep7, "P1_kpa")
ok(p17["confianza_pct"] == 75.0 and p17["requiere_confirmacion"], p17)
print("  OK")

print("[9/15] Confirmar datos medios/bajos desbloquea V14.11 sin alterar valores...")
rep8 = confirmar_todos_pendientes(rep3)
ok(rep8["listo_para_v147"] and rep8["pendientes_confirmacion"] == 0, rep8)
ok(entrada(rep8, "P1_kpa")["valor"] == entrada(rep3, "P1_kpa")["valor"], "V14.11 alteró el valor")
print("  OK")

print("[10/15] Firma V14.11 cambia si cambia un dato y evita reutilizar confirmación antigua...")
r9 = iic_completo()
a9 = construir_confianza_datos(r9, texto3, ctx3)
r9b = iic_completo(); r9b["prefill"]["P1_kpa"] = 136.0
b9 = construir_confianza_datos(r9b, texto3, ctx3)
ok(a9["firma"] != b9["firma"], (a9["firma"], b9["firma"]))
print("  OK")

print("[11/15] V14.7 bloquea un reporte V14.11 pendiente y acepta el confirmado...")
r10 = iic_completo(); r10["confianza_datos_v1411"] = rep3
p10 = construir_previsualizacion_transferencia(r10, texto3)
ok(not p10["listo_para_transferir"], p10)
r10c = iic_completo(); r10c["confianza_datos_v1411"] = rep8
p10c = construir_previsualizacion_transferencia(r10c, texto3)
ok(p10c["listo_para_transferir"], p10c["bloqueos"])
ok(p10c["snapshot"].get("firma_confianza_v1411") == rep8["firma"], p10c["snapshot"])
print("  OK")

print("[12/15] Tramos, accesorios y transiciones reciben confianza individual...")
rep11 = construir_confianza_datos(r1, "Determine Q", {"modo_entrada": "⌨️ Escribir o pegar"})
ok(any(x["clave"] == "L_m" and x.get("tramo") == 1 for x in rep11["entradas"]), "Falta L1")
ok(any(x["clave"] == "accesorio" for x in rep11["entradas"]), "Faltan accesorios")
ok(any(x["categoria"] == "transicion" for x in rep11["entradas"]), "Falta transición")
print("  OK")

print("[13/15] Manifiesto/reporte V14.9 conserva V14.11 y lo exporta a Markdown/Word...")
r12 = iic_completo(); r12["confianza_datos_v1411"] = rep1
p12 = construir_previsualizacion_transferencia(r12, "Determine Q")
ok(p12["listo_para_transferir"], p12["bloqueos"])
m12 = construir_manifiesto_ejecucion(r12, "Determine Q", p12)
ok(m12["confianza_datos_v1411"]["version"] == "V14.11", m12)
sol_dummy = {"Q_final": 0.02, "iteraciones": 1, "residual": 0.0, "convergencia": True,
             "sistema": {"total_hf": 1.0, "total_hm": 0.2, "hL_total": 1.2, "resultados": []}}
aud_dummy = {"estado": "OK", "checks": [], "comprobaciones": 0, "errores": 0, "advertencias": 0}
rf12 = construir_reporte_final(m12, sol_dummy, aud_dummy)
ok(rf12["confianza_datos_v1411"]["firma"] == rep1["firma"], rf12)
ok("Confianza individual V14.11" in reporte_markdown(rf12), "Markdown no incluye V14.11")
ok(len(reporte_docx(rf12)) > 1000, "Word V14.11 inválido")
print("  OK")

print("[14/15] La confianza es por dato y no reutiliza la confianza global de clase...")
r13 = iic_completo(); r13["confianza"] = 55
rep13 = construir_confianza_datos(r13, "Determine Q", {"modo_entrada": "⌨️ Escribir o pegar"})
ok(entrada(rep13, "P1_kpa")["confianza_pct"] == 98.0, entrada(rep13, "P1_kpa"))
print("  OK")

print("[15/15] Integración V14.11 en app.py conserva V14.10 y V14.7...")
for token in (
    "confianza_datos_v1411", "V14.11 — Confianza individual por dato",
    "mostrar_confianza_v1411", "bloqueo_confianza_v1411", "mostrar_previsualizacion_v147",
    "V14.10 — Después de confirmar",
):
    ok(token in APP, f"Falta integración en app.py: {token}")
print("  OK")

print("\nTODAS LAS PRUEBAS V14.11 DE CONFIANZA INDIVIDUAL PASARON.")
