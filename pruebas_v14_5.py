from pathlib import Path

from clasificar_problema import identificar_clase_automaticamente
from consolidacion_datos import consolidar_resultado, VERSION_EXPEDIENTE


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)


def base_resultado(clase, *, D=0.08, material="Acero comercial o soldado"):
    return {
        "clase": clase,
        "confianza": 95,
        "razones": [],
        "advertencias": [],
        "datos": [],
        "prefill": {
            "fluido_app": "Agua a 20 °C",
            "fluido_detectado": "Agua",
            "temperatura_c": 20.0,
            "Q_m3s": 0.0173,
            "P1_kpa": 65.0,
            "P2_kpa": 0.0,
            "z1_m": 22.4,
            "z2_m": 7.1,
            "hA_m": 0.0,
            "hR_m": 0.0,
            "incognita_clase_i": None,
            "v1_tipo": "deposito",
            "v2_tipo": "deposito",
            "tramos": [{
                "numero": 1,
                "L_m": 137.6,
                "D_m": D,
                "material": material,
                "accesorios": [],
                "curvas": [],
                "K_extra": None,
                "componentes_graficos": [],
            }],
            "transiciones": [],
        },
    }


def faltantes(exp):
    return {(x.get("clave"), x.get("tramo")) for x in exp.get("faltantes", [])}


print("[1/9] II-C: expediente completo, Q es incógnita y atmósfera A/B infiere P2=0...")
texto = """Agua a 20 °C fluye desde un deposito cerrado A hacia un deposito abierto B por una tuberia de acero comercial de D = 102.3 mm y L = 121.7 m. La superficie del deposito A esta a z1 = 18.4 m y la del deposito B a z2 = 5.3 m. P1 = 84.6 kPa manometricos. Una valvula de compuerta totalmente abierta produce perdida menor. Determine el caudal Q e incluya todas las perdidas menores."""
r = consolidar_resultado(identificar_clase_automaticamente(texto), texto)
e = r["expediente_v145"]
ok(r["clase"] == "Clase II-C", r["clase"])
ok(abs(r["prefill"]["P2_kpa"] - 0.0) < 1e-12, r["prefill"].get("P2_kpa"))
ok(any(x.get("clave") == "Q_m3s" for x in e["incognitas"]), e["incognitas"])
ok(("Q_m3s", None) not in faltantes(e), e["faltantes"])
ok(e["listo_para_resolver"], e["faltantes"])
print("  OK")

print("[2/9] II-C: si solo falta material, pregunta únicamente material...")
r = base_resultado("Clase II-C", material=None)
r["prefill"]["Q_m3s"] = None  # Q es incógnita de la clase
c = consolidar_resultado(r, "Determine el caudal Q. Incluya todas las perdidas menores.")
e = c["expediente_v145"]
ok(faltantes(e) == {("material", 1)}, e["faltantes"])
print("  OK")

print("[3/9] III-A: D no se considera faltante porque es la incógnita...")
r = base_resultado("Clase III-A", D=None)
c = consolidar_resultado(r, "Determine el diametro minimo requerido de la tuberia.")
e = c["expediente_v145"]
ok(any(x.get("clave") == "D_m" for x in e["incognitas"]), e["incognitas"])
ok(("D_m", 1) not in faltantes(e), e["faltantes"])
ok(e["listo_para_resolver"], e["faltantes"])
print("  OK")

print("[4/9] III-B: D sí es dato requerido y se pregunta si falta...")
r = base_resultado("Clase III-B", D=None)
c = consolidar_resultado(r, "Verifique la presion con la tuberia comercial seleccionada.")
e = c["expediente_v145"]
ok(("D_m", 1) in faltantes(e), e["faltantes"])
ok(not e["listo_para_resolver"], "III-B no debería estar lista sin D")
print("  OK")

print("[5/9] Clase I: P2 incógnita no se solicita como entrada...")
r = base_resultado("Clase I")
r["prefill"]["incognita_clase_i"] = "Presión P2"
r["prefill"]["P2_kpa"] = None
c = consolidar_resultado(r, "Determine la presion en el punto 2. No hay bomba ni turbina.")
e = c["expediente_v145"]
ok(any(x.get("clave") == "P2_kpa" for x in e["incognitas"]), e["incognitas"])
ok(("P2_kpa", None) not in faltantes(e), e["faltantes"])
ok(e["listo_para_resolver"], e["faltantes"])
print("  OK")

print("[6/9] Clase I: si no se sabe qué calcular, solicita solo definir la incógnita...")
r = base_resultado("Clase I")
c = consolidar_resultado(r, "Analice el sistema de tuberias con los datos indicados.")
e = c["expediente_v145"]
ok(("incognita_clase_i", None) in faltantes(e), e["faltantes"])
print("  OK")

print("[7/9] Componente gráfico sin tipo/K se pregunta en II-C, pero no en II-A...")
for clase, debe_preguntar in (("Clase II-C", True), ("Clase II-A", False)):
    r = base_resultado(clase)
    r["prefill"]["Q_m3s"] = None
    r["prefill"]["tramos"][0]["componentes_graficos"] = [{"nombre": "Válvula inferida por geometría"}]
    e = consolidar_resultado(r, "Determine el caudal.")["expediente_v145"]
    tiene = any(str(x.get("clave", "")).startswith("componente_grafico_") for x in e["faltantes"])
    ok(tiene == debe_preguntar, (clase, e["faltantes"]))
print("  OK")

print("[8/9] Contradicción atmosférica explícita bloquea el expediente...")
r = base_resultado("Clase II-C")
r["prefill"]["Q_m3s"] = None
r["prefill"]["P2_kpa"] = 34.7
texto_conf = "El deposito 2 esta abierto a la atmosfera y P2 = 34.7 kPa manometricos. Determine el caudal e incluya todas las perdidas menores."
e = consolidar_resultado(r, texto_conf)["expediente_v145"]
ok(e["cantidad_conflictos"] >= 1, e["conflictos"])
ok(not e["listo_para_autollenado"] and not e["listo_para_resolver"], e)
print("  OK")

print("[9/9] Integración V14.5 en app.py y versión del expediente...")
app = Path(__file__).with_name("app.py").read_text(encoding="utf-8")
for token in (
    "from consolidacion_datos import",
    "resultado_nuevo = consolidar_resultado(resultado_nuevo, enunciado)",
    "V14.5 — Expediente consolidado del problema",
    "mostrar_expediente_v145(resultado)",
):
    ok(token in app, f"Falta integración V14.5 en app.py: {token}")
ok(VERSION_EXPEDIENTE == "V14.5", VERSION_EXPEDIENTE)
print("  OK")

print("\nTODAS LAS PRUEBAS V14.5 DE CONSOLIDACIÓN PASARON.")
