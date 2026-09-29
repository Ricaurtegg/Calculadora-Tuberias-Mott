"""Pruebas de sensibilidad/recalculo automático V13.

Comprueba que al modificar tres variables representativas por cada una de las
seis clases/métodos, la solución cambia en el sentido físico esperado.
Esto protege la automatización requerida por la asignación.
"""
from copy import deepcopy

from casos_mott_cap11 import CASOS
from calculos.hidraulica import calcular_sistema_para_q, verificar_clase_iii_b
from metodos_mott import resolver_clase_ii_mott_v9, resolver_clase_iii_a_mott_v9


def normalizar_tramos(tramos):
    """Asegura la misma estructura mínima que crea app.py."""
    salida = []
    for t0 in deepcopy(tramos):
        t = dict(t0)
        t.setdefault("numero", len(salida) + 1)
        t.setdefault("material", "Acero comercial o soldado")
        t.setdefault("K", 0.0)
        t.setdefault("K_extra", 0.0)
        t.setdefault("K_extra_posicion_fraccion", 0.85)
        t.setdefault("accesorios_detalle", [])
        t.setdefault("componentes_graficos", [])
        salida.append(t)
    return salida


def q_ii(caso):
    metodo = caso["clase"].replace("Clase ", "")
    sol = resolver_clase_ii_mott_v9(
        metodo=metodo,
        tramos=normalizar_tramos(caso["tramos"]),
        nu=caso["nu"], gamma=caso["gamma"],
        P1=caso["P1"], P2=caso["P2"], z1=caso["z1"], z2=caso["z2"],
        hA=caso["hA"], hR=caso["hR"],
        tipo_v1=caso["tipo_v1"], tipo_v2=caso["tipo_v2"], transiciones=[],
    )
    return float(sol["Q_final"])


def d_iiia(caso):
    r = resolver_clase_iii_a_mott_v9(
        Q=caso["Q"], L=caso["L"], epsilon=caso["epsilon"], nu=caso["nu"],
        hL_permitida=caso["hL_permitida"], catalogo_comercial=None,
    )
    return float(r["D_mott"])


def p2_iiib(caso):
    r = verificar_clase_iii_b(
        D_actual=caso["D"], Q=caso["Q"], L=caso["L"], epsilon=caso["epsilon"],
        nu=caso["nu"], K=caso["K"], gamma=caso["gamma"], P1=caso["P1"],
        P2_deseada=caso["P2_deseada"], z1=caso["z1"], z2=caso["z2"],
        hA=caso["hA"], hR=caso["hR"], tipo_v1=caso["tipo_v1"], tipo_v2=caso["tipo_v2"],
    )
    return float(r["P2_calculada"])


def exigir(cond, mensaje):
    if not cond:
        raise AssertionError(mensaje)


print("=" * 72)
print("PRUEBAS DE RECÁLCULO AUTOMÁTICO — 3 CAMBIOS POR CLASE/MÉTODO")
print("=" * 72)

# 1. Clase I
print("[1/6] Clase I: Q, L y K...")
c = deepcopy(CASOS["I_11_1"])
h0 = calcular_sistema_para_q(c["Q"], normalizar_tramos(c["tramos"]), c["nu"])["hL_total"]
h_q = calcular_sistema_para_q(c["Q"] * 1.05, normalizar_tramos(c["tramos"]), c["nu"])["hL_total"]
t = normalizar_tramos(c["tramos"]); t[1]["L"] *= 1.10
h_l = calcular_sistema_para_q(c["Q"], t, c["nu"])["hL_total"]
t = normalizar_tramos(c["tramos"]); t[1]["K"] *= 1.20
h_k = calcular_sistema_para_q(c["Q"], t, c["nu"])["hL_total"]
exigir(h_q > h0, "Clase I: aumentar Q debe aumentar hL.")
exigir(h_l > h0, "Clase I: aumentar L debe aumentar hL.")
exigir(h_k > h0, "Clase I: aumentar K debe aumentar hL.")
print("  OK: los tres cambios recalculan y aumentan las pérdidas como corresponde.")

# 2. II-A
print("[2/6] II-A: ΔP, L y rugosidad...")
c = deepcopy(CASOS["IIA_11_2"]); q0 = q_ii(c)
c1 = deepcopy(c); c1["P1"] += 6000.0
c2 = deepcopy(c); c2["tramos"][0]["L"] *= 1.10
c3 = deepcopy(c); c3["tramos"][0]["epsilon"] *= 1.50
exigir(q_ii(c1) > q0, "II-A: mayor ΔP disponible debe permitir mayor Q.")
exigir(q_ii(c2) < q0, "II-A: mayor L debe reducir Q.")
exigir(q_ii(c3) < q0, "II-A: mayor rugosidad debe reducir Q.")
print("  OK: ΔP↑ => Q↑; L↑ => Q↓; ε↑ => Q↓.")

# 3. II-B
print("[3/6] II-B: K, L y ΔP...")
c = deepcopy(CASOS["IIB_11_3"]); q0 = q_ii(c)
c1 = deepcopy(c); c1["tramos"][0]["K"] *= 1.20
c2 = deepcopy(c); c2["tramos"][0]["L"] *= 1.10
c3 = deepcopy(c); c3["P1"] += 6000.0
exigir(q_ii(c1) < q0, "II-B: mayor K debe reducir Q.")
exigir(q_ii(c2) < q0, "II-B: mayor L debe reducir Q.")
exigir(q_ii(c3) > q0, "II-B: mayor ΔP disponible debe aumentar Q.")
print("  OK: K↑ => Q↓; L↑ => Q↓; ΔP↑ => Q↑.")

# 4. II-C
print("[4/6] II-C: carga disponible, K y L...")
c = deepcopy(CASOS["IIC_11_4"]); q0 = q_ii(c)
c1 = deepcopy(c); c1["z1"] += 5.0 * 0.3048
c2 = deepcopy(c); c2["tramos"][0]["K"] *= 1.20
c3 = deepcopy(c); c3["tramos"][0]["L"] *= 1.10
exigir(q_ii(c1) > q0, "II-C: mayor carga disponible debe aumentar Q.")
exigir(q_ii(c2) < q0, "II-C: mayor K debe reducir Q.")
exigir(q_ii(c3) < q0, "II-C: mayor L debe reducir Q.")
print("  OK: Hdisp↑ => Q↑; K↑ => Q↓; L↑ => Q↓.")

# 5. III-A
print("[5/6] III-A: Q, L y hL permitido...")
c = deepcopy(CASOS["IIIA_11_5"]); d0 = d_iiia(c)
c1 = deepcopy(c); c1["Q"] *= 1.10
c2 = deepcopy(c); c2["L"] *= 1.10
c3 = deepcopy(c); c3["hL_permitida"] *= 1.10
exigir(d_iiia(c1) > d0, "III-A: mayor Q debe exigir mayor D.")
exigir(d_iiia(c2) > d0, "III-A: mayor L debe exigir mayor D.")
exigir(d_iiia(c3) < d0, "III-A: permitir mayor hL debe reducir D mínimo.")
print("  OK: Q↑ => Dmin↑; L↑ => Dmin↑; hL permitido↑ => Dmin↓.")

# 6. III-B
print("[6/6] III-B: Q, K y D...")
c = deepcopy(CASOS["IIIB_11_6"]); p0 = p2_iiib(c)
c1 = deepcopy(c); c1["Q"] *= 1.10
c2 = deepcopy(c); c2["K"] *= 1.20
c3 = deepcopy(c); c3["D"] *= 1.05
exigir(p2_iiib(c1) < p0, "III-B: mayor Q debe reducir P2.")
exigir(p2_iiib(c2) < p0, "III-B: mayor K debe reducir P2.")
exigir(p2_iiib(c3) > p0, "III-B: mayor D debe aumentar P2 disponible.")
print("  OK: Q↑ => P2↓; K↑ => P2↓; D↑ => P2↑.")

print("\n✅ LAS 18 PRUEBAS DE RECÁLCULO AUTOMÁTICO PASARON.")
