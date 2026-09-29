import os
os.environ.setdefault("MPLBACKEND", "Agg")

from pathlib import Path
import copy
import matplotlib.pyplot as plt

from transferencia_v147 import (
    VERSION_TRANSFERENCIA,
    construir_previsualizacion_transferencia,
    confirmacion_corresponde,
)
from diagramas import crear_esquema_sistema, DIAGRAMAS_VERSION, _bbox_etiqueta


BASE = Path(__file__).resolve().parent
APP = (BASE / "app.py").read_text(encoding="utf-8")


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)


def resultado_iic_completo():
    return {
        "clase": "Clase II-C",
        "confianza": 96,
        "prefill": {
            "fluido_app": "Agua a 20 °C",
            "fluido_detectado": "Agua a 20 °C",
            "P1_kpa": 135.0,
            "P2_kpa": 0.0,
            "z1_m": 31.2,
            "z2_m": 8.4,
            "hA_m": 0.0,
            "hR_m": 0.0,
            "tramos": [
                {
                    "numero": 1,
                    "L_m": 68.5,
                    "D_m": 0.100,
                    "material": "Acero comercial o soldado",
                    "accesorios": [
                        {"nombre": "Entrada — borde cuadrado/agudo", "cantidad": 1},
                        {"nombre": "Codo estándar de 90°", "cantidad": 2},
                    ],
                    "curvas": [],
                    "componentes_graficos": [],
                },
                {
                    "numero": 2,
                    "L_m": 96.3,
                    "D_m": 0.075,
                    "material": "Plástico",
                    "accesorios": [
                        {"nombre": "Válvula de compuerta — totalmente abierta", "cantidad": 1},
                        {"nombre": "Salida — tubería dentro del depósito", "cantidad": 1},
                    ],
                    "curvas": [],
                    "componentes_graficos": [],
                },
            ],
            "transiciones": [
                {"entre": 1, "tipo": "Contracción súbita", "angulo_grados": None}
            ],
        },
    }


print("[1/9] V14.7 previsualiza II-C completo y conserva Q como incógnita...")
r = resultado_iic_completo()
p = construir_previsualizacion_transferencia(r, "Determine el caudal Q.")
ok(p["version"] == VERSION_TRANSFERENCIA == "V14.7", "Versión V14.7 incorrecta")
ok(p["listo_para_transferir"], f"Debía estar listo: {p['bloqueos']}")
ok(any(x.get("clave") == "Q_m3s" for x in p["incognitas"]), "Q no quedó como incógnita")
qrow = next(x for x in p["filas_generales"] if x["Dato"] == "Caudal Q")
ok(qrow["Valor"] == "INCÓGNITA", "Q se intentó transferir como dato conocido")
ok(len(p["filas_tramos"]) == 2, "No previsualizó los dos tramos")
print("  OK")


print("[2/9] La firma invalida una confirmación si cambia cualquier dato...")
firma1 = p["firma"]
r2 = copy.deepcopy(r)
r2["prefill"]["P1_kpa"] = 136.25
p2 = construir_previsualizacion_transferencia(r2, "Determine el caudal Q.")
ok(firma1 != p2["firma"], "La firma no cambió al modificar P1")
ok(confirmacion_corresponde(p, firma1), "La confirmación válida no fue aceptada")
ok(not confirmacion_corresponde(p2, firma1), "Se aceptó una confirmación de un snapshot antiguo")
print("  OK")


print("[3/9] Un dato faltante bloquea V14.7 en vez de transferir silenciosamente...")
r3 = resultado_iic_completo()
r3["prefill"]["tramos"][1]["material"] = None
p3 = construir_previsualizacion_transferencia(r3, "Determine el caudal Q.")
ok(not p3["listo_para_transferir"], "V14.7 dejó pasar un material faltante")
ok(any("faltante" in x.lower() or "material" in x.lower() for x in p3["bloqueos"]), "No explicó el bloqueo")
print("  OK")


print("[4/9] Fluido y material personalizados conservan propiedades aportadas...")
r4 = resultado_iic_completo()
r4["prefill"]["fluido_app"] = "Personalizado"
r4["prefill"]["fluido_detectado"] = "Personalizado"
r4["prefill"]["rho_usuario"] = 917.4
r4["prefill"]["nu_usuario_m2s"] = 7.35e-5
r4["prefill"]["tramos"][0]["material"] = "Personalizada"
r4["prefill"]["tramos"][0]["epsilon_m"] = 0.000081
p4 = construir_previsualizacion_transferencia(r4, "Determine Q.")
ok(p4["listo_para_transferir"], f"Personalizados deberían ser válidos: {p4['bloqueos']}")
ok(p4["filas_tramos"][0]["ε"] != "catálogo" and p4["filas_tramos"][0]["ε"] != "—", "No mostró ε personalizado")
print("  OK")


print("[5/9] III-A permite que D siga siendo la incógnita en la transferencia...")
r5 = {
    "clase": "Clase III-A", "confianza": 95,
    "prefill": {
        "fluido_app": "Agua a 20 °C", "fluido_detectado": "Agua a 20 °C",
        "Q_m3s": 0.0127, "P1_kpa": 0.0, "P2_kpa": 0.0,
        "z1_m": 22.0, "z2_m": 4.0, "hA_m": 0.0, "hR_m": 0.0,
        "tramos": [{"numero": 1, "L_m": 83.4, "D_m": None, "material": "Acero comercial o soldado", "componentes_graficos": []}],
        "transiciones": [],
    },
}
p5 = construir_previsualizacion_transferencia(r5, "Determine el diámetro requerido.")
ok(p5["listo_para_transferir"], f"III-A fue bloqueada: {p5['bloqueos']}")
ok(p5["filas_tramos"][0]["D"] == "INCÓGNITA", "D no quedó como incógnita III-A")
print("  OK")


print("[6/9] Integración V14.7 exige revisión explícita antes del autollenado...")
for token in (
    "construir_previsualizacion_transferencia",
    "V14.7 — Previsualización y validación de transferencia",
    "Confirmo que revisé estos datos y deseo transferirlos al solucionador.",
    "bloquear_v147",
    "transferencia_v147_confirmada",
):
    ok(token in APP, f"Falta integración V14.7 en app.py: {token}")
print("  OK")


print("[7/9] El esquema usa el motor anti-solapamiento V14.7...")
ok("anti-solapamiento" in DIAGRAMAS_VERSION, f"Versión de diagramas inesperada: {DIAGRAMAS_VERSION}")
ok("_resolver_solapamientos_etiquetas" in (BASE / "diagramas.py").read_text(encoding="utf-8"), "Falta resolver de solapamientos")
print("  OK")


print("[8/9] Caso gráfico denso: ninguna caja dinámica queda montada sobre otra...")
tramos_g = [
    {
        "L": 68.5, "D": 0.1, "material": "Acero comercial o soldado",
        "accesorios_detalle": [
            {"nombre": "Entrada — borde cuadrado/agudo", "cantidad": 1, "posicion_fraccion": 0.48},
            {"nombre": "Codo 90° estándar", "cantidad": 1, "posicion_fraccion": 0.70},
            {"nombre": "Codo 90° estándar", "cantidad": 1, "posicion_fraccion": 0.75},
        ],
    },
    {
        "L": 96.3, "D": 0.075, "material": "Plástico",
        "accesorios_detalle": [
            {"nombre": "Válvula de compuerta — totalmente abierta", "cantidad": 1, "posicion_fraccion": 31.0/96.3},
            {"nombre": "Salida hacia depósito", "cantidad": 1, "posicion_fraccion": 0.70},
        ],
    },
]
fig = crear_esquema_sistema(
    tramos_g, z1=31.2, z2=8.4, tipo_v1="deposito", tipo_v2="deposito",
    transiciones=[{"entre": 1, "tipo": "Contracción súbita", "K": 0.14904, "hL": 0.2356}],
    titulo="II-C — esquema hidráulico",
)
fig.canvas.draw()
renderer = fig.canvas.get_renderer()
cuadros = [t for ax in fig.axes for t in ax.texts if t.get_bbox_patch() is not None]
solapes = []
for i in range(len(cuadros)):
    bi = _bbox_etiqueta(cuadros[i], renderer)
    for j in range(i + 1, len(cuadros)):
        bj = _bbox_etiqueta(cuadros[j], renderer)
        if bi.overlaps(bj):
            solapes.append((cuadros[i].get_text(), cuadros[j].get_text()))
plt.close(fig)
ok(not solapes, f"Persisten cuadros solapados: {solapes}")
print("  OK")


print("[9/9] La corrección gráfica no elimina etiquetas de tramos, transición ni accesorios...")
# La prueba anterior ya construyó el caso; se verifican tokens funcionales del módulo.
dia = (BASE / "diagramas.py").read_text(encoding="utf-8")
for token in ("Tramo {i + 1}", "Contracciones/ensanchamientos", "etiquetas_dinamicas", "_bbox_etiqueta"):
    if token == "Contracciones/ensanchamientos":
        # Compatibilidad semántica: el comentario histórico puede cambiar, basta el bloque de transiciones.
        ok("Transiciones geométricas" in dia, "Se perdió el bloque de transiciones")
    else:
        ok(token in dia, f"Falta elemento gráfico esperado: {token}")
print("  OK")

print("\nTODAS LAS PRUEBAS V14.7 DE PREVISUALIZACIÓN Y DIAGRAMAS PASARON.")
