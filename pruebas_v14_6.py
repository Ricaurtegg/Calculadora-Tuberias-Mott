from pathlib import Path

from completado_interactivo import (
    VERSION_COMPLETADO,
    ErrorRespuestaFaltante,
    identificador_pregunta,
    aplicar_respuestas_faltantes,
    opciones_transicion_para_pregunta,
)
from consolidacion_datos import consolidar_resultado, VERSION_EXPEDIENTE
from transiciones_mott import TIPO_EXP_GRAD


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)


def base_resultado(clase="Clase II-C", *, material="Acero comercial o soldado"):
    return {
        "clase": clase,
        "confianza": 96,
        "razones": [],
        "advertencias": [],
        "datos": [],
        "prefill": {
            "fluido_app": "Agua a 20 °C",
            "fluido_detectado": "Agua",
            "temperatura_c": 20.0,
            "Q_m3s": None if clase.startswith("Clase II") else 0.0187,
            "P1_kpa": 81.4,
            "P2_kpa": 0.0,
            "z1_m": 21.8,
            "z2_m": 6.2,
            "hA_m": 0.0,
            "hR_m": 0.0,
            "incognita_clase_i": None,
            "v1_tipo": "deposito",
            "v2_tipo": "deposito",
            "tramos": [{
                "numero": 1, "L_m": 128.6, "D_m": 0.0917,
                "material": material, "accesorios": [], "curvas": [],
                "K_extra": None, "componentes_graficos": [],
            }],
            "transiciones": [],
        },
    }


def pendientes(r):
    e = r["expediente_v145"]
    return {identificador_pregunta(x) for x in e.get("faltantes", [])}


print("[1/13] Material faltante -> respuesta V14.6 -> expediente listo...")
r = consolidar_resultado(base_resultado(material=None), "Determine Q e incluya las pérdidas menores.")
ok("material__tramo_1" in pendientes(r), pendientes(r))
r2 = aplicar_respuestas_faltantes(r, "Determine Q e incluya las pérdidas menores.", {
    "material__tramo_1": "Acero comercial o soldado",
})
ok(r2["prefill"]["tramos"][0]["material"] == "Acero comercial o soldado", r2["prefill"])
ok(r2["expediente_v145"]["listo_para_resolver"], r2["expediente_v145"]["faltantes"])
ok(r2["completado_v146"]["respuestas_acumuladas"] == 1, r2["completado_v146"])
print("  OK")

print("[2/13] Respuesta parcial elimina solo la pregunta contestada...")
r = base_resultado()
r["prefill"]["P1_kpa"] = None
r["prefill"]["z1_m"] = None
r = consolidar_resultado(r, "Determine el caudal e incluya todas las pérdidas.")
ok({"P1_kpa", "z1_m"}.issubset(pendientes(r)), pendientes(r))
r2 = aplicar_respuestas_faltantes(r, "Determine el caudal e incluya todas las pérdidas.", {"P1_kpa": 73.25})
ok("P1_kpa" not in pendientes(r2) and "z1_m" in pendientes(r2), pendientes(r2))
ok(abs(r2["prefill"]["P1_kpa"] - 73.25) < 1e-12, r2["prefill"])
print("  OK")

print("[3/13] Clase I: seleccionar incógnita reconsolida sin pedir esa variable...")
r = base_resultado("Clase I")
r["prefill"]["P2_kpa"] = None
r = consolidar_resultado(r, "Analice el sistema.")
ok("incognita_clase_i" in pendientes(r), pendientes(r))
r2 = aplicar_respuestas_faltantes(r, "Analice el sistema.", {"incognita_clase_i": "Presión P2"})
ok(r2["prefill"]["incognita_clase_i"] == "Presión P2", r2["prefill"])
ok("P2_kpa" not in pendientes(r2), pendientes(r2))
ok(r2["expediente_v145"]["listo_para_resolver"], r2["expediente_v145"]["faltantes"])
print("  OK")

print("[4/13] Sin tramos: V14.6 crea la estructura y luego pregunta solo sus datos...")
r = base_resultado()
r["prefill"]["tramos"] = []
r = consolidar_resultado(r, "Determine el caudal.")
ok("tramos" in pendientes(r), pendientes(r))
r2 = aplicar_respuestas_faltantes(r, "Determine el caudal.", {"tramos": 2})
ok(len(r2["prefill"]["tramos"]) == 2, r2["prefill"]["tramos"])
p = pendientes(r2)
for pid in ("L_m__tramo_1", "D_m__tramo_1", "material__tramo_1", "L_m__tramo_2", "D_m__tramo_2", "material__tramo_2"):
    ok(pid in p, (pid, p))
print("  OK")

print("[5/13] No acepta Q/L/D no positivos...")
r = base_resultado("Clase III-B")
r["prefill"]["Q_m3s"] = None
r = consolidar_resultado(r, "Verifique el diámetro comercial.")
try:
    aplicar_respuestas_faltantes(r, "Verifique el diámetro comercial.", {"Q_m3s": 0.0})
except ErrorRespuestaFaltante:
    pass
else:
    raise AssertionError("Aceptó Q=0")
print("  OK")

print("[6/13] Ignora respuestas para campos que no están pendientes...")
r = consolidar_resultado(base_resultado(material=None), "Determine Q.")
r2 = aplicar_respuestas_faltantes(r, "Determine Q.", {"P1_kpa": 999.0, "material__tramo_1": "Plástico"})
ok(abs(r2["prefill"]["P1_kpa"] - 81.4) < 1e-12, r2["prefill"]["P1_kpa"])
ok(r2["prefill"]["tramos"][0]["material"] == "Plástico", r2["prefill"])
print("  OK")

print("[7/13] Transición detectada: filtra por sentido y guarda tipo/ángulo...")
r = base_resultado()
r["prefill"]["tramos"] = [
    {"numero": 1, "L_m": 60.4, "D_m": 0.0762, "material": "Acero comercial o soldado", "accesorios": [], "curvas": [], "componentes_graficos": []},
    {"numero": 2, "L_m": 81.7, "D_m": 0.1123, "material": "Acero comercial o soldado", "accesorios": [], "curvas": [], "componentes_graficos": []},
]
r["prefill"]["transiciones"] = [{"entre": 1, "tipo": None, "angulo_grados": None}]
r = consolidar_resultado(r, "Determine Q incluyendo el cambio gradual de sección.")
item = next(x for x in r["expediente_v145"]["faltantes"] if x["clave"].startswith("transicion_"))
ops = opciones_transicion_para_pregunta(item, r["prefill"])
ok(TIPO_EXP_GRAD in ops and all("Contracción" not in x for x in ops), ops)
pid = identificador_pregunta(item)
r2 = aplicar_respuestas_faltantes(r, "Determine Q incluyendo el cambio gradual de sección.", {
    pid: {"tipo": TIPO_EXP_GRAD, "angulo_grados": 22.5}
})
ok(r2["prefill"]["transiciones"][0]["tipo"] == TIPO_EXP_GRAD, r2["prefill"]["transiciones"])
ok(abs(r2["prefill"]["transiciones"][0]["angulo_grados"] - 22.5) < 1e-12, r2["prefill"]["transiciones"])
print("  OK")

print("[8/13] Componente gráfico -> accesorio Mott, conserva posición y deja de estar pendiente...")
r = base_resultado()
r["prefill"]["tramos"][0]["componentes_graficos"] = [{"nombre": "válvula?", "posicion_fraccion": 0.637}]
r = consolidar_resultado(r, "Determine Q e incluya pérdidas menores.")
pid = next(x for x in pendientes(r) if x.startswith("componente_grafico_"))
r2 = aplicar_respuestas_faltantes(r, "Determine Q e incluya pérdidas menores.", {
    pid: {"modo": "accesorio", "nombre": "Válvula de compuerta — totalmente abierta"}
})
t = r2["prefill"]["tramos"][0]
ok(not t["componentes_graficos"], t)
ok(t["accesorios"][0]["nombre"] == "Válvula de compuerta — totalmente abierta", t)
ok(abs(t["accesorios"][0]["posicion_fraccion"] - 0.637) < 1e-12, t)
ok(not any(x.startswith("componente_grafico_") for x in pendientes(r2)), pendientes(r2))
print("  OK")

print("[9/13] Componente gráfico -> K manual y conserva posición...")
r = base_resultado()
r["prefill"]["tramos"][0]["componentes_graficos"] = [{"nombre": "elemento?", "posicion_fraccion": 0.412}]
r = consolidar_resultado(r, "Determine Q con pérdidas menores.")
pid = next(x for x in pendientes(r) if x.startswith("componente_grafico_"))
r2 = aplicar_respuestas_faltantes(r, "Determine Q con pérdidas menores.", {pid: {"modo": "k_manual", "K": 0.347}})
t = r2["prefill"]["tramos"][0]
ok(abs(t["K_extra"] - 0.347) < 1e-12, t)
ok(abs(t["K_extra_posicion_fraccion"] - 0.412) < 1e-12, t)
print("  OK")


print("[10/13] Material personalizado exige y conserva ε aportada por el usuario...")
r = consolidar_resultado(base_resultado(material=None), "Determine Q.")
r2 = aplicar_respuestas_faltantes(r, "Determine Q.", {
    "material__tramo_1": {"nombre": "Personalizada", "epsilon_m": 7.3e-5}
})
t = r2["prefill"]["tramos"][0]
ok(t["material"] == "Personalizada" and abs(t["epsilon_m"] - 7.3e-5) < 1e-15, t)
print("  OK")

print("[11/13] Fluido personalizado conserva ρ y ν para el autollenado...")
r = base_resultado()
r["prefill"]["fluido_app"] = None
r["prefill"]["fluido_detectado"] = None
r = consolidar_resultado(r, "Determine Q.")
ok("fluido_app" in pendientes(r), pendientes(r))
r2 = aplicar_respuestas_faltantes(r, "Determine Q.", {
    "fluido_app": {"nombre": "Personalizado", "rho": 912.4, "nu": 4.87e-6}
})
ok(r2["prefill"]["fluido_app"] == "Personalizado", r2["prefill"])
ok(abs(r2["prefill"]["rho_usuario"] - 912.4) < 1e-12, r2["prefill"])
ok(abs(r2["prefill"]["nu_usuario_m2s"] - 4.87e-6) < 1e-15, r2["prefill"])
print("  OK")

print("[12/13] Versiones: V14.5 se conserva y V14.6 se añade sin romper compatibilidad...")
ok(VERSION_EXPEDIENTE == "V14.5", VERSION_EXPEDIENTE)
ok(VERSION_COMPLETADO == "V14.6", VERSION_COMPLETADO)
print("  OK")

print("[13/13] Integración V14.6 en app.py...")
app = Path(__file__).with_name("app.py").read_text(encoding="utf-8")
for token in (
    "from completado_interactivo import",
    "V14.6 — Complete únicamente los datos faltantes",
    "aplicar_respuestas_faltantes(",
    "resultado = mostrar_completado_v146(resultado, enunciado)",
    "(usar_prefill and faltan_v146)",
):
    ok(token in app, f"Falta integración V14.6: {token}")
print("  OK")

print("\nTODAS LAS PRUEBAS V14.6 DE COMPLETADO INTERACTIVO PASARON.")
