import math

from calculos.hidraulica import calcular_para_diametro
from transiciones_mott import (
    calcular_sistema_con_transiciones,
    residuo_clase_ii_con_transiciones,
)


# ============================================================
# SOLVERS TRANSPARENTES Y AUTO-ACOTADOS
# Se evita pedir Qmin/Qmax o Dmin/Dmax al usuario en el modo normal.
# ============================================================


def _signo_cambio(a, b):
    return a == 0 or b == 0 or (a < 0 < b) or (b < 0 < a)


def _candidatos_log(seed, minimo, maximo, niveles=28, factor=2.0):
    seed = min(max(float(seed), minimo), maximo)
    valores = {seed, minimo, maximo}
    for k in range(1, niveles + 1):
        valores.add(max(minimo, seed / (factor ** k)))
        valores.add(min(maximo, seed * (factor ** k)))
    return sorted(v for v in valores if minimo <= v <= maximo)


def encontrar_intervalo_automatico(func, seed, minimo, maximo, niveles=28):
    """Busca un cambio de signo alrededor de una semilla y guarda el escaneo."""
    puntos = _candidatos_log(seed, minimo, maximo, niveles=niveles)
    evaluados = []
    prev = None

    for x in puntos:
        try:
            r = float(func(x))
        except Exception:
            continue
        if not math.isfinite(r):
            continue
        evaluados.append({"x": x, "residual": r})
        if abs(r) < 1e-12:
            return (x, x), evaluados
        if prev is not None and _signo_cambio(prev[1], r):
            return (prev[0], x), evaluados
        prev = (x, r)

    raise ValueError(
        "No se encontró automáticamente un intervalo con cambio de signo. "
        "Revise si existe una solución física o use el modo avanzado para fijar límites manuales."
    )


def resolver_biseccion_historial(func, a, b, tol_residual=1e-9, tol_rel=1e-9, max_iter=100, estado_func=None):
    fa = float(func(a))
    fb = float(func(b))
    if a == b:
        x = a
        fx = fa
        estado = estado_func(x) if estado_func else None
        return x, fx, [], estado
    if not _signo_cambio(fa, fb):
        raise ValueError("El intervalo no encierra una raíz.")

    historial = []
    estado_final = None

    for i in range(1, max_iter + 1):
        c = 0.5 * (a + b)
        fc = float(func(c))
        estado = estado_func(c) if estado_func else None
        fila = {"iteracion": i, "x": c, "residual": fc, "a": a, "b": b}
        if estado is not None:
            fila["estado"] = estado
        historial.append(fila)

        if abs(fc) <= tol_residual or abs(b - a) <= tol_rel * max(abs(c), 1.0):
            estado_final = estado
            return c, fc, historial, estado_final

        if _signo_cambio(fa, fc):
            b, fb = c, fc
        else:
            a, fa = c, fc

    c = 0.5 * (a + b)
    fc = float(func(c))
    estado_final = estado_func(c) if estado_func else None
    return c, fc, historial, estado_final


def _resumen_estado_sistema(sistema):
    resultados = sistema.get("resultados", [])
    if not resultados:
        return {}
    res = [float(r.get("Re", 0.0)) for r in resultados]
    fs = [float(r.get("f Darcy", 0.0)) for r in resultados]
    vs = [float(r.get("V (m/s)", 0.0)) for r in resultados]
    return {
        "hL_total": float(sistema.get("hL_total", 0.0)),
        "Re_min": min(res),
        "Re_max": max(res),
        "f_min": min(fs),
        "f_max": max(fs),
        "V_max": max(vs),
    }


def resolver_caudal_auto(
    tramos, nu, gamma, P1, P2, z1, z2, hA, hR,
    tipo_v1, tipo_v2, transiciones=None,
    V1_manual=0.0, V2_manual=0.0,
    seed=None, q_min_abs=1e-10, q_max_abs=100.0,
    tol_residual=1e-9, max_iter=100,
):
    if not tramos:
        raise ValueError("Debe existir al menos un tramo.")
    if seed is None or seed <= 0:
        d_ref = min(float(t["D"]) for t in tramos)
        area = math.pi * d_ref**2 / 4.0
        seed = max(area * 1.5, 1e-6)  # semilla ~1.5 m/s en el diámetro menor

    def residual(q):
        return residuo_clase_ii_con_transiciones(
            q, tramos, nu, gamma, P1, P2, z1, z2, hA, hR,
            tipo_v1, tipo_v2, transiciones or [], V1_manual, V2_manual,
        )

    def estado(q):
        return calcular_sistema_con_transiciones(q, tramos, nu, transiciones or [])

    intervalo, escaneo = encontrar_intervalo_automatico(
        residual, seed, q_min_abs, q_max_abs
    )
    a, b = intervalo
    raiz, res, historial_raw, sistema_final = resolver_biseccion_historial(
        residual, a, b,
        tol_residual=tol_residual,
        tol_rel=1e-10,
        max_iter=max_iter,
        estado_func=estado,
    )

    historial = []
    for item in historial_raw:
        resumen = _resumen_estado_sistema(item["estado"])
        historial.append({
            "Iteración": item["iteracion"],
            "Q (m³/s)": item["x"],
            "hL total (m)": resumen.get("hL_total"),
            "Residual (m)": item["residual"],
            "Re mín": resumen.get("Re_min"),
            "Re máx": resumen.get("Re_max"),
            "f mín": resumen.get("f_min"),
            "f máx": resumen.get("f_max"),
            "V máx (m/s)": resumen.get("V_max"),
        })

    if sistema_final is None:
        sistema_final = estado(raiz)

    return {
        "Q": raiz,
        "Q_final": raiz,
        "residual": res,
        "sistema": sistema_final,
        "iteraciones": len(historial),
        "convergencia": abs(res) <= max(tol_residual * 10, 1e-8),
        "intervalo_automatico": {"Q_inf": a, "Q_sup": b},
        "escaneo_intervalo": escaneo,
        "historial_iteracion": historial,
        "seed": seed,
    }


def resolver_diametro_auto(Q, L, epsilon, nu, hL_permitida, seed=None, d_min_abs=0.001, d_max_abs=5.0, max_iter=100):
    if seed is None or seed <= 0:
        seed = 0.05

    def estado(d):
        return calcular_para_diametro(
            D=d, Q=Q, L=L, epsilon=epsilon, nu=nu, K=0.0
        )

    def residual(d):
        e = estado(d)
        return float(e["hf"]) - float(hL_permitida)

    intervalo, escaneo = encontrar_intervalo_automatico(
        residual, seed, d_min_abs, d_max_abs
    )
    a, b = intervalo
    raiz, res, historial_raw, estado_final = resolver_biseccion_historial(
        residual, a, b,
        tol_residual=1e-9,
        tol_rel=1e-10,
        max_iter=max_iter,
        estado_func=estado,
    )

    historial = []
    for item in historial_raw:
        e = item["estado"]
        historial.append({
            "Iteración": item["iteracion"],
            "D (m)": item["x"],
            "V (m/s)": float(e["V"]),
            "Re": float(e["Re"]),
            "f": float(e["f"]),
            "hf (m)": float(e["hf"]),
            "Residual (m)": item["residual"],
        })

    if estado_final is None:
        estado_final = estado(raiz)

    return {
        **estado_final,
        "D_minimo": raiz,
        "residual": res,
        "iteraciones": len(historial),
        "convergencia": abs(res) <= 1e-8,
        "intervalo_automatico": {"D_inf": a, "D_sup": b},
        "escaneo_intervalo": escaneo,
        "historial_iteracion": historial,
        "seed": seed,
    }
