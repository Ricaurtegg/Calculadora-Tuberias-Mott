import math
import re

import numpy as np
from scipy.optimize import brentq

from calculos.hidraulica import (
    G,
    area_circular,
    velocidad,
    carga_velocidad,
    calcular_sistema_para_q,
)
from catalogos_mott import calcular_ft_mott


# ============================================================
# MOTT 7a ED. — CAPÍTULO 10
# CAMBIOS DE SECCIÓN Y CURVAS DE TUBERÍA
# ============================================================

TIPO_SIN = "Sin pérdida adicional / unión ideal"
TIPO_EXP_SUD = "Ensanchamiento súbito"
TIPO_EXP_GRAD = "Ensanchamiento gradual"
TIPO_CON_SUD = "Contracción súbita"
TIPO_CON_GRAD = "Contracción gradual"


# Tabla 10.2 — resistencia en ensanchamiento gradual.
_ANG_EXP = np.array([2, 6, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60], dtype=float)
_RATIO_EXP = np.array([1.1, 1.2, 1.4, 1.6, 1.8, 2.0, 2.5, 3.0, 100.0], dtype=float)
_K_EXP = np.array([
    [0.01, 0.01, 0.03, 0.05, 0.10, 0.13, 0.16, 0.18, 0.19, 0.20, 0.21, 0.23],
    [0.02, 0.02, 0.04, 0.09, 0.16, 0.21, 0.25, 0.29, 0.31, 0.33, 0.35, 0.37],
    [0.02, 0.03, 0.06, 0.12, 0.23, 0.30, 0.36, 0.41, 0.44, 0.47, 0.50, 0.53],
    [0.03, 0.04, 0.07, 0.14, 0.26, 0.35, 0.42, 0.47, 0.51, 0.54, 0.57, 0.61],
    [0.03, 0.04, 0.07, 0.15, 0.28, 0.37, 0.44, 0.50, 0.54, 0.58, 0.61, 0.65],
    [0.03, 0.04, 0.07, 0.16, 0.29, 0.38, 0.46, 0.52, 0.56, 0.60, 0.63, 0.68],
    [0.03, 0.04, 0.08, 0.16, 0.30, 0.39, 0.48, 0.54, 0.58, 0.62, 0.65, 0.70],
    [0.03, 0.04, 0.08, 0.16, 0.31, 0.40, 0.48, 0.55, 0.59, 0.63, 0.66, 0.71],
    [0.03, 0.05, 0.08, 0.16, 0.31, 0.40, 0.49, 0.56, 0.60, 0.64, 0.67, 0.72],
], dtype=float)


# Tabla 10.3B — contracción súbita, datos métricos.
_V_CON = np.array([0.6, 1.2, 1.8, 2.4, 3.0, 4.5, 6.0, 9.0, 12.0], dtype=float)
_RATIO_CON = np.array([1.0, 1.1, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.5, 3.0, 4.0, 5.0, 10.0, 100.0], dtype=float)
_K_CON = np.array([
    [0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00],
    [0.03, 0.04, 0.04, 0.04, 0.04, 0.04, 0.05, 0.05, 0.06],
    [0.07, 0.07, 0.07, 0.07, 0.08, 0.08, 0.09, 0.10, 0.11],
    [0.17, 0.17, 0.17, 0.17, 0.18, 0.18, 0.18, 0.19, 0.20],
    [0.26, 0.26, 0.26, 0.26, 0.26, 0.25, 0.25, 0.25, 0.24],
    [0.34, 0.34, 0.34, 0.33, 0.33, 0.32, 0.31, 0.29, 0.27],
    [0.38, 0.37, 0.37, 0.36, 0.36, 0.34, 0.33, 0.31, 0.29],
    [0.40, 0.40, 0.39, 0.39, 0.38, 0.37, 0.35, 0.33, 0.30],
    [0.42, 0.42, 0.41, 0.40, 0.40, 0.38, 0.37, 0.34, 0.31],
    [0.44, 0.44, 0.43, 0.42, 0.42, 0.40, 0.39, 0.36, 0.33],
    [0.47, 0.46, 0.45, 0.45, 0.44, 0.42, 0.41, 0.37, 0.34],
    [0.48, 0.47, 0.47, 0.46, 0.45, 0.44, 0.42, 0.38, 0.35],
    [0.49, 0.48, 0.48, 0.47, 0.46, 0.45, 0.43, 0.40, 0.36],
    [0.49, 0.48, 0.48, 0.47, 0.47, 0.45, 0.44, 0.41, 0.38],
], dtype=float)


# Figuras 10.11 y 10.12 — contracción gradual.
# Mott no ofrece una tabla numérica; esta malla es una digitalización aproximada
# de las curvas para permitir autocalculo. La interfaz lo identifica como aproximación.
_RATIO_CG = np.array([1.2, 1.5, 2.0, 2.5, 3.0], dtype=float)
_ANG_CG = np.array([3.0, 5.0, 10.0, 15.0, 40.0, 50.0, 60.0, 76.0, 90.0, 105.0, 120.0, 150.0], dtype=float)
_K_CG = np.array([
    # 3,    5,    10,   15,   40,   50,   60,   76,   90,   105,  120,  150
    [0.073, 0.069, 0.055, 0.037, 0.037, 0.045, 0.045, 0.055, 0.065, 0.075, 0.090, 0.110],
    [0.080, 0.064, 0.052, 0.050, 0.050, 0.070, 0.070, 0.100, 0.120, 0.150, 0.180, 0.220],
    [0.100, 0.071, 0.047, 0.045, 0.045, 0.060, 0.060, 0.120, 0.170, 0.215, 0.265, 0.345],
    [0.109, 0.084, 0.048, 0.045, 0.045, 0.075, 0.075, 0.135, 0.188, 0.230, 0.280, 0.360],
    [0.116, 0.092, 0.053, 0.050, 0.050, 0.080, 0.080, 0.135, 0.190, 0.235, 0.280, 0.360],
], dtype=float)


# Figura 10.28 — 90° pipe bend. Le/D frente a r/D.
_RD_BEND = np.array([1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 20.0], dtype=float)
_LED_BEND = np.array([20.0, 14.0, 12.0, 12.0, 14.0, 17.0, 24.0, 30.0, 34.0, 38.0, 42.0, 50.0], dtype=float)


def _interp_2d(x, y, xs, ys, tabla):
    """Interpolación bilineal acotada en una tabla rectangular."""
    x = float(np.clip(float(x), xs[0], xs[-1]))
    y = float(np.clip(float(y), ys[0], ys[-1]))

    fila_interp = np.array([
        np.interp(y, ys, fila)
        for fila in tabla
    ], dtype=float)
    return float(np.interp(x, xs, fila_interp))


def k_ensanchamiento_subito(D1, D2):
    D1 = float(D1)
    D2 = float(D2)
    if not (D2 > D1 > 0):
        raise ValueError("Para ensanchamiento súbito debe cumplirse D2 > D1 > 0.")
    return (1.0 - (D1 / D2) ** 2) ** 2


def k_ensanchamiento_gradual(D1, D2, angulo_grados):
    D1 = float(D1)
    D2 = float(D2)
    theta = float(angulo_grados)
    if not (D2 > D1 > 0):
        raise ValueError("Para ensanchamiento gradual debe cumplirse D2 > D1 > 0.")
    if not (2.0 <= theta <= 60.0):
        raise ValueError("La Tabla 10.2 de Mott incluida cubre ángulos de cono de 2° a 60°.")
    ratio = D2 / D1
    # Para la fila ∞ se usa 100 como aproximación numérica del límite.
    ratio_interp = min(max(ratio, 1.1), 100.0)
    return _interp_2d(ratio_interp, theta, _RATIO_EXP, _ANG_EXP, _K_EXP)


def k_contraccion_subita(D1, D2, v2):
    D1 = float(D1)
    D2 = float(D2)
    v2 = abs(float(v2))
    if not (D1 > D2 > 0):
        raise ValueError("Para contracción súbita debe cumplirse D1 > D2 > 0.")
    ratio = D1 / D2
    ratio_interp = min(max(ratio, 1.0), 100.0)
    v_interp = min(max(v2, _V_CON[0]), _V_CON[-1])
    k = _interp_2d(ratio_interp, v_interp, _RATIO_CON, _V_CON, _K_CON)
    advertencia = None
    if v2 < _V_CON[0] or v2 > _V_CON[-1]:
        advertencia = (
            "La velocidad en la tubería pequeña queda fuera de 0.6–12 m/s, "
            "rango de la Tabla 10.3B; K se evaluó en el extremo tabulado más cercano."
        )
    return k, advertencia


def k_contraccion_gradual(D1, D2, angulo_grados):
    D1 = float(D1)
    D2 = float(D2)
    theta = float(angulo_grados)
    if not (D1 > D2 > 0):
        raise ValueError("Para contracción gradual debe cumplirse D1 > D2 > 0.")
    if not (3.0 <= theta <= 150.0):
        raise ValueError("Las Figuras 10.11–10.12 implementadas cubren aproximadamente 3° a 150°.")

    ratio = D1 / D2
    ratio_interp = min(max(ratio, _RATIO_CG[0]), _RATIO_CG[-1])

    # En Fig. 10.11 Mott agrupa 15°–40° y 50°–60°.
    if 15.0 <= theta <= 40.0:
        theta_interp = 15.0
    elif 50.0 <= theta <= 60.0:
        theta_interp = 50.0
    else:
        theta_interp = theta

    k = _interp_2d(ratio_interp, theta_interp, _RATIO_CG, _ANG_CG, _K_CG)
    advertencia = (
        "K se obtuvo por interpolación de una digitalización aproximada de las Figuras 10.11 y 10.12 "
        "de Mott. Para una entrega que exija lectura exacta de la gráfica, puede sustituirlo por K manual."
    )
    if ratio < _RATIO_CG[0] or ratio > _RATIO_CG[-1]:
        advertencia += " El cociente D1/D2 quedó fuera de 1.2–3.0 y se acotó al extremo más cercano."
    return k, advertencia


def le_d_curva_90(r_D):
    r_D = float(r_D)
    if r_D <= 0:
        raise ValueError("r/D debe ser mayor que cero.")
    r_eval = min(max(r_D, _RD_BEND[0]), _RD_BEND[-1])
    led = float(np.interp(r_eval, _RD_BEND, _LED_BEND))
    advertencia = None
    if r_D < _RD_BEND[0] or r_D > _RD_BEND[-1]:
        advertencia = "r/D quedó fuera del rango 1–20 de la Fig. 10.28; se usó el extremo más cercano."
    return led, advertencia


def calcular_k_curva_tuberia(diametro_m, material, r_D, angulo_grados=90.0):
    """
    Mott §10.11.
    - 90°: K = fT (Le/D), con Le/D de Fig. 10.28.
    - Otro ángulo: Ec. 10-10, usando n = ángulo/90.
    """
    D = float(diametro_m)
    theta = float(angulo_grados)
    if D <= 0:
        raise ValueError("El diámetro debe ser mayor que cero.")
    if theta <= 0:
        raise ValueError("El ángulo de la curva debe ser mayor que cero.")

    led, adv_led = le_d_curva_90(r_D)
    ft_info = calcular_ft_mott(D, material)
    ft = float(ft_info["ft"])
    K90 = ft * led

    if abs(theta - 90.0) < 1e-9:
        K = K90
        metodo = "Mott Fig. 10.28"
    else:
        n = theta / 90.0
        K = (n - 1.0) * (0.25 * math.pi * ft * float(r_D) + 0.5 * K90) + K90
        K = max(K, 0.0)
        metodo = "Mott Ec. 10-10 + Fig. 10.28"

    advertencias = [x for x in (adv_led, ft_info.get("advertencia")) if x]
    return {
        "k": float(K),
        "K90": float(K90),
        "le_d_90": float(led),
        "ft": ft,
        "r_D": float(r_D),
        "angulo_grados": theta,
        "fuente": metodo,
        "descripcion": f"r/D={float(r_D):.3g}; θ={theta:.3g}°; fT={ft:.4f}; K={K:.4g}",
        "advertencia": " ".join(advertencias) if advertencias else None,
    }


def calcular_perdida_transicion(Q, transicion, tramos, g=G):
    i = int(transicion["entre"])
    if i < 1 or i >= len(tramos):
        raise ValueError("Índice de transición fuera del sistema.")

    t1 = tramos[i - 1]
    t2 = tramos[i]
    D1 = float(t1["D"])
    D2 = float(t2["D"])
    V1 = velocidad(Q, D1)
    V2 = velocidad(Q, D2)
    tipo = transicion.get("tipo", TIPO_SIN)
    theta = transicion.get("angulo_grados")

    if tipo == TIPO_SIN or abs(D1 - D2) < 1e-12:
        return {
            "entre": i,
            "tipo": tipo,
            "D1": D1,
            "D2": D2,
            "V_ref": 0.0,
            "K": 0.0,
            "hL": 0.0,
            "referencia_velocidad": "—",
            "fuente": "—",
            "advertencia": None,
        }

    if tipo == TIPO_EXP_SUD:
        K = k_ensanchamiento_subito(D1, D2)
        Vref = V1
        ref = "V1 (tubería menor, aguas arriba)"
        fuente = "Mott 7e §10.3 — ensanchamiento súbito"
        advertencia = None

    elif tipo == TIPO_EXP_GRAD:
        K = k_ensanchamiento_gradual(D1, D2, theta)
        Vref = V1
        ref = "V1 (tubería menor, aguas arriba)"
        fuente = "Mott 7e Tabla 10.2"
        advertencia = None

    elif tipo == TIPO_CON_SUD:
        K, advertencia = k_contraccion_subita(D1, D2, V2)
        Vref = V2
        ref = "V2 (tubería menor, aguas abajo)"
        fuente = "Mott 7e Tabla 10.3B"

    elif tipo == TIPO_CON_GRAD:
        K, advertencia = k_contraccion_gradual(D1, D2, theta)
        Vref = V2
        ref = "V2 (tubería menor, aguas abajo)"
        fuente = "Mott 7e Figuras 10.11–10.12 (interpolación aproximada)"

    else:
        raise ValueError(f"Tipo de transición no reconocido: {tipo}")

    hL = float(K) * carga_velocidad(Vref, g)
    return {
        "entre": i,
        "tipo": tipo,
        "D1": D1,
        "D2": D2,
        "V1": V1,
        "V2": V2,
        "V_ref": Vref,
        "K": float(K),
        "hL": float(hL),
        "angulo_grados": theta,
        "referencia_velocidad": ref,
        "fuente": fuente,
        "advertencia": advertencia,
    }


def calcular_transiciones_para_q(Q, tramos, transiciones, g=G):
    resultados = []
    total = 0.0
    for transicion in transiciones or []:
        r = calcular_perdida_transicion(Q, transicion, tramos, g=g)
        resultados.append(r)
        total += float(r["hL"])
    return resultados, total


def calcular_sistema_con_transiciones(Q, tramos, nu, transiciones=None, g=G):
    base = calcular_sistema_para_q(Q, tramos, nu, g)
    detalles, h_trans = calcular_transiciones_para_q(Q, tramos, transiciones or [], g=g)

    resultado = dict(base)
    hm_accesorios = float(base.get("total_hm", 0.0))
    resultado["total_hm_accesorios"] = hm_accesorios
    resultado["total_hm_transiciones"] = float(h_trans)
    resultado["total_hm"] = hm_accesorios + float(h_trans)
    resultado["hL_total"] = float(base.get("total_hf", 0.0)) + resultado["total_hm"]
    resultado["transiciones_resultados"] = detalles
    return resultado


def _velocidad_extremo(Q, tipo, D, manual=0.0):
    if tipo == "deposito":
        return 0.0
    if tipo == "manual":
        return float(manual)
    return velocidad(Q, D)


def residuo_clase_ii_con_transiciones(
    Q, tramos, nu, gamma, P1, P2, z1, z2, hA, hR,
    tipo_v1, tipo_v2, transiciones=None,
    V1_manual=0.0, V2_manual=0.0, g=G,
):
    sistema = calcular_sistema_con_transiciones(Q, tramos, nu, transiciones, g=g)
    V1 = _velocidad_extremo(Q, tipo_v1, tramos[0]["D"], V1_manual)
    V2 = _velocidad_extremo(Q, tipo_v2, tramos[-1]["D"], V2_manual)
    E1 = float(P1) / gamma + float(z1) + carga_velocidad(V1, g)
    E2 = float(P2) / gamma + float(z2) + carga_velocidad(V2, g)
    return E1 + float(hA) - float(hR) - sistema["hL_total"] - E2


def buscar_caudal_con_transiciones(
    tramos, nu, gamma, P1, P2, z1, z2, hA, hR,
    tipo_v1, tipo_v2, transiciones=None,
    V1_manual=0.0, V2_manual=0.0,
    Q_min=1e-7, Q_max=10.0, muestras=450, g=G,
):
    if Q_min <= 0 or Q_max <= Q_min:
        raise ValueError("El intervalo de Q no es válido.")

    valores = np.logspace(np.log10(Q_min), np.log10(Q_max), int(muestras))
    q_ant = r_ant = None

    for q in valores:
        try:
            r = residuo_clase_ii_con_transiciones(
                q, tramos, nu, gamma, P1, P2, z1, z2, hA, hR,
                tipo_v1, tipo_v2, transiciones,
                V1_manual, V2_manual, g,
            )
        except ValueError:
            q_ant = r_ant = None
            continue

        if abs(r) < 1e-10:
            return {
                "Q": q,
                "sistema": calcular_sistema_con_transiciones(q, tramos, nu, transiciones, g=g),
                "residual": r,
                "iteraciones": 0,
                "convergencia": True,
            }

        if q_ant is not None and r_ant is not None and r_ant * r < 0:
            raiz, info = brentq(
                lambda qq: residuo_clase_ii_con_transiciones(
                    qq, tramos, nu, gamma, P1, P2, z1, z2, hA, hR,
                    tipo_v1, tipo_v2, transiciones,
                    V1_manual, V2_manual, g,
                ),
                q_ant, q,
                xtol=1e-12, rtol=1e-10, maxiter=200, full_output=True,
            )
            sistema = calcular_sistema_con_transiciones(raiz, tramos, nu, transiciones, g=g)
            residual = residuo_clase_ii_con_transiciones(
                raiz, tramos, nu, gamma, P1, P2, z1, z2, hA, hR,
                tipo_v1, tipo_v2, transiciones,
                V1_manual, V2_manual, g,
            )
            return {
                "Q": raiz,
                "sistema": sistema,
                "residual": residual,
                "iteraciones": info.iterations,
                "convergencia": info.converged,
            }

        q_ant, r_ant = q, r

    raise ValueError(
        "No se encontró una solución física para Q dentro del intervalo. "
        "Revise las condiciones de energía, las transiciones o amplíe Q mínimo/máximo."
    )


def _sin_perdidas_menores(tramos):
    nuevos = []
    for t in tramos:
        c = dict(t)
        c["K"] = 0.0
        c["K_extra"] = 0.0
        c["accesorios_detalle"] = []
        nuevos.append(c)
    return nuevos


def resolver_clase_ii_mott_con_transiciones(
    metodo, tramos, nu, gamma, P1, P2, z1, z2, hA, hR,
    tipo_v1, tipo_v2, transiciones=None,
    V1_manual=0.0, V2_manual=0.0,
    Q_min=1e-7, Q_max=10.0, g=G,
):
    if metodo not in ("II-A", "II-B", "II-C"):
        raise ValueError("Método de Clase II no válido.")

    if metodo == "II-A":
        tA = _sin_perdidas_menores(tramos)
        sol = buscar_caudal_con_transiciones(
            tA, nu, gamma, P1, P2, z1, z2, hA, hR,
            tipo_v1, tipo_v2, [], V1_manual, V2_manual,
            Q_min, Q_max, g=g,
        )
        sol["metodo"] = metodo
        sol["Q_IIA"] = sol["Q"]
        sol["Q_final"] = sol["Q"]
        return sol

    if metodo == "II-B":
        tA = _sin_perdidas_menores(tramos)
        est = buscar_caudal_con_transiciones(
            tA, nu, gamma, P1, P2, z1, z2, hA, hR,
            tipo_v1, tipo_v2, [], V1_manual, V2_manual,
            Q_min, Q_max, g=g,
        )
        sol = buscar_caudal_con_transiciones(
            tramos, nu, gamma, P1, P2, z1, z2, hA, hR,
            tipo_v1, tipo_v2, transiciones or [], V1_manual, V2_manual,
            Q_min, Q_max, g=g,
        )
        sol["metodo"] = metodo
        sol["Q_IIA"] = est["Q"]
        sol["Q_final"] = sol["Q"]
        sol["correccion_porcentaje"] = (est["Q"] - sol["Q"]) / est["Q"] * 100.0
        return sol

    sol = buscar_caudal_con_transiciones(
        tramos, nu, gamma, P1, P2, z1, z2, hA, hR,
        tipo_v1, tipo_v2, transiciones or [], V1_manual, V2_manual,
        Q_min, Q_max, g=g,
    )
    sol["metodo"] = metodo
    sol["Q_IIA"] = None
    sol["Q_final"] = sol["Q"]
    return sol


# ============================================================
# DETECCIÓN BÁSICA DESDE ENUNCIADO
# ============================================================

def _normalizar(texto):
    import unicodedata
    t = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _tipo_desde_contexto(ctx, D1, D2):
    if D2 > D1:
        if re.search(r"(?:ensanchamiento|expansion|difusor)[^\.\n]{0,40}(?:subit|brusc|repentin)", ctx) or re.search(r"(?:subit|brusc|repentin)[^\.\n]{0,25}(?:ensanchamiento|expansion)", ctx):
            return TIPO_EXP_SUD
        if re.search(r"(?:ensanchamiento|expansion|difusor)[^\.\n]{0,40}(?:gradual|conic)", ctx) or re.search(r"(?:gradual|conic)[^\.\n]{0,25}(?:ensanchamiento|expansion|difusor)", ctx):
            return TIPO_EXP_GRAD
    elif D2 < D1:
        if re.search(r"(?:contraccion|reduccion|reductor)[^\.\n]{0,40}(?:subit|brusc|repentin)", ctx) or re.search(r"(?:subit|brusc|repentin)[^\.\n]{0,25}(?:contraccion|reduccion|reductor)", ctx):
            return TIPO_CON_SUD
        if re.search(r"(?:contraccion|reduccion|reductor)[^\.\n]{0,40}(?:gradual|conic)", ctx) or re.search(r"(?:gradual|conic)[^\.\n]{0,25}(?:contraccion|reduccion|reductor)", ctx):
            return TIPO_CON_GRAD
    return None


def _angulo_desde_contexto(ctx):
    patrones = [
        r"(?:angulo(?:\s+incluido|\s+del\s+cono)?|cono)\s*(?:de|=|:)??\s*(\d+(?:[\.,]\d+)?)\s*(?:°|grados?)",
        r"(\d+(?:[\.,]\d+)?)\s*(?:°|grados?)\s*(?:de\s+angulo|de\s+cono)",
    ]
    for p in patrones:
        m = re.search(p, ctx)
        if m:
            return float(m.group(1).replace(",", "."))
    return None


def detectar_transiciones_en_texto(texto_original, tramos):
    texto = _normalizar(texto_original)
    if not tramos or len(tramos) < 2:
        return []

    marcas = list(re.finditer(r"\btramo\s*(\d+)\b", texto))
    por_numero = {int(m.group(1)): m.start() for m in marcas}
    resultados = []

    for i in range(1, len(tramos)):
        D1 = tramos[i - 1].get("D_m") or tramos[i - 1].get("D")
        D2 = tramos[i].get("D_m") or tramos[i].get("D")
        if D1 is None or D2 is None or abs(float(D1) - float(D2)) < 1e-12:
            continue

        # Contexto preferente alrededor de la frontera entre los dos tramos.
        if i in por_numero and (i + 1) in por_numero:
            a = por_numero[i]
            b = por_numero[i + 1]
            ctx = texto[max(0, a):min(len(texto), b + 180)]
        else:
            ctx = texto

        tipo = _tipo_desde_contexto(ctx, float(D1), float(D2))

        # Si hay una sola transición geométrica en todo el sistema, acepta la frase global.
        if tipo is None and len(tramos) == 2:
            tipo = _tipo_desde_contexto(texto, float(D1), float(D2))
            ctx = texto

        if tipo is None:
            continue

        angulo = _angulo_desde_contexto(ctx) if "gradual" in tipo.lower() else None
        resultados.append({
            "entre": i,
            "tipo": tipo,
            "angulo_grados": angulo,
        })

    return resultados


def detectar_curvas_tuberia(texto_original):
    """Reconoce frases simples del tipo 'curva de 60° con r/D = 3.2'."""
    texto = _normalizar(texto_original)
    curvas = []
    patron = re.compile(
        r"(?:curva|doblez|bend)[^\.\n]{0,60}?(\d+(?:[\.,]\d+)?)\s*(?:°|grados?)"
        r"[^\.\n]{0,60}?(?:r\s*/\s*d|radio\s*/\s*diametro)\s*(?:=|:)\s*(\d+(?:[\.,]\d+)?)"
    )
    for m in patron.finditer(texto):
        curvas.append({
            "angulo_grados": float(m.group(1).replace(",", ".")),
            "r_D": float(m.group(2).replace(",", ".")),
        })
    return curvas
