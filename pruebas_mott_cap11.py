"""Banco permanente de regresión contra Mott 7.ª ed., Capítulo 11.

Cubre los seis casos centrales de la entrega:
  11.1 Clase I
  11.2 Clase II-A
  11.3 Clase II-B
  11.4 Clase II-C
  11.5 Clase III-A
  11.6 Clase III-B

Ejecutar:
    python pruebas_mott_cap11.py
"""

import json
from pathlib import Path

from casos_mott_cap11 import CASOS, PSI_TO_PA, FT_TO_M
from calculos.hidraulica import (
    calcular_sistema_para_q,
    resolver_clase_i,
    residuo_energia,
    potencia_entrada_bomba,
    verificar_clase_iii_b,
)
from metodos_mott import resolver_clase_ii_mott_v9, resolver_clase_iii_a_mott_v9

BASE = Path(__file__).resolve().parent


def error_rel(valor, ref):
    return abs(float(valor) - float(ref)) / max(abs(float(ref)), 1e-30)


def exigir_rel(valor, ref, tol, nombre):
    err = error_rel(valor, ref)
    if err > tol:
        raise AssertionError(
            f"{nombre}: obtenido={valor:.12g}, Mott={ref:.12g}, "
            f"error={100*err:.3f}% > {100*tol:.3f}%"
        )
    return err


def exigir_abs(valor, ref, tol, nombre):
    err = abs(float(valor) - float(ref))
    if err > tol:
        raise AssertionError(
            f"{nombre}: obtenido={valor:.12g}, Mott={ref:.12g}, "
            f"error_abs={err:.6g} > {tol:.6g}"
        )
    return err


def base_tramo(t):
    """Copia un tramo preservando la estructura que usa app.py."""
    return {
        "numero": t.get("numero", 1),
        "L": float(t["L"]),
        "D": float(t["D"]),
        # El motor real de la aplicación conserva el material en cada tramo.
        # Se usa el material Mott correspondiente al epsilon de estos ejemplos.
        "material": t.get("material", "Acero comercial o soldado"),
        "epsilon": float(t.get("epsilon", 0.0)),
        "K": float(t.get("K", 0.0)),
        "K_extra": float(t.get("K_extra", 0.0)),
        "K_extra_posicion_fraccion": float(t.get("K_extra_posicion_fraccion", 0.85)),
        "accesorios_detalle": list(t.get("accesorios_detalle", [])),
        "componentes_graficos": list(t.get("componentes_graficos", [])),
    }


reporte = []

print("=" * 72)
print("BANCO DORADO MOTT 7.ª ED. — CAPÍTULO 11")
print("=" * 72)

# ------------------------------------------------------------------
# 1) CLASE I — Ejemplo 11.1
# ------------------------------------------------------------------
print("[1/6] Ejemplo 11.1 — Clase I...")
c = CASOS["I_11_1"]
tramos = [base_tramo(t) for t in c["tramos"]]
sistema = calcular_sistema_para_q(c["Q"], tramos, c["nu"])
hL = float(sistema["hL_total"])
hA = float(resolver_clase_i(
    incognita="hA",
    P1=c["P1"], P2=c["P2"], z1=c["z1"], z2=c["z2"],
    V1=0.0, V2=0.0, hA=None, hR=0.0, hL=hL, gamma=c["gamma"],
))
residual = float(residuo_energia(
    P1=c["P1"], P2=c["P2"], z1=c["z1"], z2=c["z2"],
    V1=0.0, V2=0.0, hA=hA, hR=0.0, hL=hL, gamma=c["gamma"],
))
pin_kw = float(potencia_entrada_bomba(c["gamma"], c["Q"], hA, c["eficiencia"])) / 1000.0

e1 = exigir_rel(hL, c["esperado"]["hL_m"], c["tolerancia_rel"], "11.1 hL")
e2 = exigir_rel(hA, c["esperado"]["hA_m"], c["tolerancia_rel"], "11.1 hA")
e3 = exigir_rel(pin_kw, c["esperado"]["potencia_entrada_kW"], c["tolerancia_rel"], "11.1 potencia")
if abs(residual) > 1e-7:
    raise AssertionError(f"11.1 residual de energía alto: {residual:.3e} m")
print(f"  OK: hL={hL:.3f} m | hA={hA:.3f} m | Pentrada={pin_kw:.3f} kW")
reporte.append({
    "caso": "11.1", "clase": "I", "estado": "OK",
    "obtenido": {"hL_m": hL, "hA_m": hA, "potencia_entrada_kW": pin_kw, "residual_m": residual},
    "referencia_mott": c["esperado"],
    "error_rel_max_pct": 100.0 * max(e1, e2, e3),
})

# ------------------------------------------------------------------
# 2-4) CLASE II — Ejemplos 11.2, 11.3 y 11.4
# ------------------------------------------------------------------
for idx, clave in enumerate(("IIA_11_2", "IIB_11_3", "IIC_11_4"), start=2):
    c = CASOS[clave]
    metodo = c["clase"].replace("Clase ", "")
    print(f"[{idx}/6] Ejemplo {c['nombre'].split('Ejemplo ')[1].split(' —')[0]} — {c['clase']}...")
    sol = resolver_clase_ii_mott_v9(
        metodo=metodo,
        tramos=[base_tramo(t) for t in c["tramos"]],
        nu=c["nu"], gamma=c["gamma"],
        P1=c["P1"], P2=c["P2"], z1=c["z1"], z2=c["z2"],
        hA=c["hA"], hR=c["hR"],
        tipo_v1=c["tipo_v1"], tipo_v2=c["tipo_v2"],
        transiciones=[],
    )
    q = float(sol["Q_final"])
    err = exigir_rel(q, c["esperado"]["Q_m3s"], c["tolerancia_rel"], f"{metodo} Q")

    if metodo in ("II-B", "II-C") and abs(float(sol["residual"])) > 1e-7:
        raise AssertionError(f"{metodo}: residual alto {sol['residual']:.3e} m")
    if metodo == "II-B":
        if not q < float(sol["Q_IIA"]):
            raise AssertionError("II-B: Q final debe ser menor que la estimación II-A al añadir pérdidas menores.")
        hist = sol.get("historial_iteracion", [])
        if not hist or hist[0].get("Iteración") != 0:
            raise AssertionError("II-B: el historial debe iniciar con Iteración 0 = estimación II-A.")
    if metodo == "II-C":
        f_final = float(sol["sistema"]["resultados"][0]["f Darcy"])
        exigir_rel(f_final, c["esperado"]["f"], 0.05, "II-C f")

    print(f"  OK: Q={q:.8f} m³/s | Mott={c['esperado']['Q_m3s']:.8f} | error={100*err:.3f}%")
    reporte.append({
        "caso": c["nombre"].split("Ejemplo ")[1].split(" —")[0],
        "clase": metodo, "estado": "OK",
        "obtenido": {"Q_m3s": q, "residual_m": float(sol["residual"]), "iteraciones": int(sol.get("iteraciones", 0))},
        "referencia_mott": c["esperado"], "error_rel_Q_pct": 100.0 * err,
    })

# ------------------------------------------------------------------
# 5) CLASE III-A — Ejemplo 11.5
# ------------------------------------------------------------------
print("[5/6] Ejemplo 11.5 — Clase III-A...")
c = CASOS["IIIA_11_5"]
r3 = resolver_clase_iii_a_mott_v9(
    Q=c["Q"], L=c["L"], epsilon=c["epsilon"], nu=c["nu"],
    hL_permitida=c["hL_permitida"], catalogo_comercial=c["catalogo"],
)
dm = float(r3["D_mott"])
err_d = exigir_rel(dm, c["esperado"]["D_min_m"], c["tolerancia_rel"], "III-A Dmín")
comercial = r3.get("tamano_comercial")
if not comercial:
    raise AssertionError("III-A: no se recomendó tamaño comercial.")
if comercial["nps"] != c["esperado"]["nps"]:
    raise AssertionError(f"III-A: se esperaba NPS {c['esperado']['nps']}, se obtuvo {comercial['nps']}")
exigir_abs(comercial["id_m"], 0.1023, 2e-4, "III-A ID comercial NPS 4")
if comercial["id_m"] < dm:
    raise AssertionError("III-A: el diámetro comercial seleccionado quedó por debajo de Dmín.")
print(f"  OK: Dmín={dm:.6f} m ({dm/FT_TO_M:.4f} ft) | NPS {comercial['nps']} | ID={comercial['id_m']:.4f} m")
reporte.append({
    "caso": "11.5", "clase": "III-A", "estado": "OK",
    "obtenido": {"D_mott_m": dm, "D_numerico_m": float(r3["D_numerico_verificacion"]), "nps": comercial["nps"], "D_comercial_m": comercial["id_m"]},
    "referencia_mott": c["esperado"], "error_rel_D_pct": 100.0 * err_d,
})

# ------------------------------------------------------------------
# 6) CLASE III-B — Ejemplo 11.6
# ------------------------------------------------------------------
print("[6/6] Ejemplo 11.6 — Clase III-B...")
c = CASOS["IIIB_11_6"]
r = verificar_clase_iii_b(
    D_actual=c["D"], Q=c["Q"], L=c["L"], epsilon=c["epsilon"], nu=c["nu"], K=c["K"],
    gamma=c["gamma"], P1=c["P1"], P2_deseada=c["P2_deseada"],
    z1=c["z1"], z2=c["z2"], hA=c["hA"], hR=c["hR"],
    tipo_v1=c["tipo_v1"], tipo_v2=c["tipo_v2"],
)
p2_psi = float(r["P2_calculada"]) / PSI_TO_PA
hl_ft = float(r["hL"]) / FT_TO_M
v_fts = float(r["V"]) / FT_TO_M
exigir_abs(p2_psi, c["esperado"]["P2_psi"], 0.15, "III-B P2")
exigir_abs(hl_ft, c["esperado"]["hL_ft"], 0.15, "III-B hL")
exigir_abs(v_fts, c["esperado"]["V_fts"], 0.08, "III-B V")
if not bool(r.get("cumple", float(r["P2_calculada"]) >= c["P2_deseada"])):
    raise AssertionError("III-B: el diseño de Mott debería cumplir P2 >= 100 psig.")
print(f"  OK: P2={p2_psi:.3f} psig | hL={hl_ft:.3f} ft | V={v_fts:.3f} ft/s")
reporte.append({
    "caso": "11.6", "clase": "III-B", "estado": "OK",
    "obtenido": {"P2_psi": p2_psi, "hL_ft": hl_ft, "V_fts": v_fts, "f": float(r["f"])},
    "referencia_mott": c["esperado"],
})

# Reporte legible y JSON para conservar evidencia de regresión.
json_path = BASE / "reporte_mott_cap11_v13.json"
json_path.write_text(json.dumps(reporte, indent=2, ensure_ascii=False), encoding="utf-8")

md = [
    "# Reporte de regresión — Mott 7.ª ed., Capítulo 11",
    "",
    "| Caso | Clase | Estado | Resultado clave |",
    "|---|---|---|---|",
]
for fila in reporte:
    obt = fila["obtenido"]
    if "Q_m3s" in obt:
        clave = f"Q = {obt['Q_m3s']:.8f} m³/s"
    elif "D_mott_m" in obt:
        clave = f"Dmin = {obt['D_mott_m']:.6f} m; NPS {obt['nps']}"
    elif "P2_psi" in obt:
        clave = f"P2 = {obt['P2_psi']:.3f} psig"
    else:
        clave = f"hA = {obt['hA_m']:.3f} m; Pin = {obt['potencia_entrada_kW']:.3f} kW"
    md.append(f"| {fila['caso']} | {fila['clase']} | {fila['estado']} | {clave} |")
md.extend([
    "",
    "> Las tolerancias admiten las pequeñas diferencias esperables entre lecturas manuales del diagrama de Moody usadas en el libro y el cálculo numérico de Colebrook de la aplicación.",
])
(BASE / "reporte_mott_cap11_v13.md").write_text("\n".join(md), encoding="utf-8")

print("\n" + "=" * 72)
print("✅ LOS SEIS CASOS DE MOTT PASARON.")
print("Se generaron:")
print("  - reporte_mott_cap11_v13.json")
print("  - reporte_mott_cap11_v13.md")
print("=" * 72)
