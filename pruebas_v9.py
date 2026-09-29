"""Pruebas de regresión para la V9.
Ejecutar desde la carpeta del proyecto:
    python pruebas_v9.py
"""

from catalogo_tuberias_mott import seleccionar_tamano_comercial
from metodos_mott import resolver_clase_ii_mott_v9, resolver_clase_iii_a_mott_v9


def assert_cerca(a, b, tol, nombre):
    if abs(a - b) > tol:
        raise AssertionError(f"{nombre}: {a} no está dentro de ±{tol} de {b}")


print("[1/4] Catálogo comercial Schedule 40...")
sel = seleccionar_tamano_comercial(
    0.0983,
    "Acero Schedule 40 — Mott Apéndice F",
)
assert sel["nps"] == "4"
assert_cerca(sel["id_m"], 0.1023, 1e-9, "ID NPS 4 Sch 40")
assert sel["tamano_anterior"]["nps"] == "3 1/2"
print("  OK: 98.3 mm → NPS 4, ID 102.3 mm")


print("[2/4] Clase II-B con intervalo automático e historial...")
# Caso simple, una sola tubería con pérdidas menores moderadas.
tramos = [{
    "numero": 1,
    "L": 100.0,
    "D": 0.1541,
    "epsilon": 4.6e-5,
    "K": 0.80,
    "K_extra": 0.0,
    "accesorios_detalle": [],
}]
sol = resolver_clase_ii_mott_v9(
    metodo="II-B",
    tramos=tramos,
    nu=1.08e-5,
    gamma=8630.0,
    P1=120000.0,
    P2=60000.0,
    z1=0.0,
    z2=0.0,
    hA=0.0,
    hR=0.0,
    tipo_v1="tuberia",
    tipo_v2="tuberia",
)
assert sol["Q_final"] > 0
assert abs(sol["residual"]) < 1e-7
assert sol["Q_final"] < sol["Q_IIA"]
assert len(sol["historial_iteracion"]) >= 2
assert sol["historial_iteracion"][0]["Iteración"] == 0
print(
    f"  OK: QII-A={sol['Q_IIA']:.6g}, Qfinal={sol['Q_final']:.6g}, "
    f"residual={sol['residual']:.3e}"
)


print("[3/4] Clase III-A con verificación automática...")
r3 = resolver_clase_iii_a_mott_v9(
    Q=0.010,
    L=50.0,
    epsilon=4.6e-5,
    nu=1.02e-6,
    hL_permitida=10.0,
    catalogo_comercial="Acero Schedule 40 — Mott Apéndice F",
)
assert r3["D_mott"] > 0
assert r3["D_numerico_verificacion"] > 0
assert r3["iteraciones_verificacion"] > 0
assert len(r3["historial_iteracion"]) > 0
assert r3["tamano_comercial"] is not None
assert r3["tamano_comercial"]["id_m"] >= r3["D_mott"]
print(
    f"  OK: Dmott={r3['D_mott']*1000:.3f} mm; "
    f"comercial=NPS {r3['tamano_comercial']['nps']} "
    f"({r3['tamano_comercial']['id_m']*1000:.1f} mm ID)"
)


print("[4/4] Regla de selección comercial...")
ant = r3["tamano_comercial"].get("tamano_anterior")
if ant is not None:
    assert ant["id_m"] < r3["D_mott"] <= r3["tamano_comercial"]["id_m"]
print("  OK: el tamaño recomendado es el primero que satisface Dreal >= Dmín")

print("\nTodas las pruebas V9 pasaron correctamente.")
