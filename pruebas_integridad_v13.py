"""Pruebas de integridad de catálogos y conversiones — V13."""

from catalogos_mott import MATERIALES, FLUIDOS, ACCESORIOS, calcular_k_accesorio, calcular_ft_mott
from catalogo_tuberias_mott import seleccionar_tamano_comercial
from unidades import (
    SISTEMA_US, CAUDAL_US_GPM, CAUDAL_US_FT3S,
    desde_interno, a_interno,
)


def exigir(cond, msg):
    if not cond:
        raise AssertionError(msg)


def cerca(a, b, tol=1e-10):
    return abs(float(a)-float(b)) <= tol * max(1.0, abs(float(b)))


print("="*72)
print("PRUEBAS DE INTEGRIDAD — CATÁLOGOS MOTT + UNIDADES")
print("="*72)

print("[1/5] Materiales de rugosidad Mott...")
exigir(len(MATERIALES) >= 10, "Se esperaban las 9 categorías Mott + Personalizada.")
exigir(cerca(MATERIALES["Plástico"], 3.0e-7), "Rugosidad de plástico alterada.")
exigir(cerca(MATERIALES["Acero comercial o soldado"], 4.6e-5), "Rugosidad de acero comercial alterada.")
exigir(cerca(MATERIALES["Hierro galvanizado"], 1.5e-4), "Rugosidad de hierro galvanizado alterada.")
print("  OK")

print("[2/5] Fluidos incomprensibles cargados...")
exigir(len(FLUIDOS) >= 60, "El catálogo de fluidos perdió entradas importantes.")
agua20 = FLUIDOS["Agua a 20 °C"]
exigir(cerca(agua20["rho"], 998.0), "ρ de agua a 20 °C cambió.")
exigir(cerca(agua20["nu"], 1.02e-6), "ν de agua a 20 °C cambió.")
exigir("Mott" in agua20["fuente"], "La trazabilidad del agua a Mott se perdió.")
print(f"  OK: {len(FLUIDOS)} opciones de fluido disponibles.")

print("[3/5] Accesorios Mott y fT...")
exigir(len(ACCESORIOS) >= 25, "El catálogo de accesorios parece incompleto.")
ft = calcular_ft_mott(0.1023, "Acero comercial o soldado")
exigir(cerca(ft["ft"], 0.016), "fT DN100 esperado = 0.016.")
k_codo = calcular_k_accesorio("Codo 90° estándar", 0.1023, "Acero comercial o soldado")["k"]
k_globo = calcular_k_accesorio("Válvula de globo — totalmente abierta", 0.1023, "Acero comercial o soldado")["k"]
k_mariposa = calcular_k_accesorio("Válvula mariposa — totalmente abierta", 0.1023, "Acero comercial o soldado")["k"]
exigir(cerca(k_codo, 0.48), "K del codo estándar DN100 cambió.")
exigir(cerca(k_globo, 5.44), "K de globo DN100 cambió.")
exigir(cerca(k_mariposa, 0.72), "K de mariposa DN100 cambió.")
print("  OK")

print("[4/5] Selección de diámetro comercial...")
sel = seleccionar_tamano_comercial(0.0983, "Acero Schedule 40 — Mott Apéndice F")
exigir(sel["nps"] == "4", "98.3 mm debe seleccionar NPS 4 Sch 40.")
exigir(cerca(sel["id_m"], 0.1023), "ID de NPS 4 Sch 40 debe ser 102.3 mm.")
exigir(sel["tamano_anterior"]["id_m"] < 0.0983 <= sel["id_m"], "Regla de primer tamaño que cumple fue alterada.")
print("  OK")

print("[5/5] Round-trip SI ↔ US Customary...")
casos = [
    (50.0, "longitud", CAUDAL_US_GPM),
    (0.1023, "diametro", CAUDAL_US_GPM),
    (150.0, "presion", CAUDAL_US_GPM),
    (0.015, "caudal", CAUDAL_US_GPM),
    (0.015, "caudal", CAUDAL_US_FT3S),
    (3.2, "velocidad", CAUDAL_US_GPM),
    (25.0, "temperatura", CAUDAL_US_GPM),
    (998.0, "densidad", CAUDAL_US_GPM),
    (1.02e-6, "nu", CAUDAL_US_GPM),
    (9.8, "potencia", CAUDAL_US_GPM),
]
for valor, kind, q_unit in casos:
    ui = desde_interno(valor, kind, SISTEMA_US, q_unit)
    back = a_interno(ui, kind, SISTEMA_US, q_unit)
    exigir(abs(back-valor) <= 1e-10*max(1.0, abs(valor)), f"Round-trip falló para {kind}: {valor} -> {ui} -> {back}")
print("  OK")

print("\n✅ TODAS LAS PRUEBAS DE INTEGRIDAD V13 PASARON.")
