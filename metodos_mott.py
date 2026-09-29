import math

from calculos.hidraulica import (
    G,
    area_circular,
    reynolds,
    calcular_para_diametro,
    buscar_diametro_clase_iii_a,
)

from transiciones_mott import (
    calcular_sistema_con_transiciones,
    residuo_clase_ii_con_transiciones,
    resolver_clase_ii_mott_con_transiciones,
)


# ============================================================
# MOTT 7a ED. — CAPÍTULO 11
# BLOQUE DE MÉTODOS DIRECTOS / VERIFICACIÓN
# ============================================================


def caudal_ii_a_mott_ec_11_3(D, L, epsilon, nu, h_f, g=G):
    """
    Método II-A de Mott, Ec. (11-3), basada en Swamee-Jain.

    Q = -0.965 D^2 sqrt(g D h_f/L)
        ln[epsilon/(3.7D) + 1.78 nu/(D sqrt(g D h_f/L))]

    Aplicación: una tubería de diámetro uniforme, pérdidas menores
    despreciadas y h_f disponible conocido.
    """
    D = float(D)
    L = float(L)
    epsilon = float(epsilon)
    nu = float(nu)
    h_f = float(h_f)

    if D <= 0:
        raise ValueError("D debe ser mayor que cero.")
    if L <= 0:
        raise ValueError("L debe ser mayor que cero.")
    if epsilon < 0:
        raise ValueError("La rugosidad no puede ser negativa.")
    if nu <= 0:
        raise ValueError("La viscosidad cinemática debe ser mayor que cero.")
    if h_f <= 0:
        raise ValueError("La pérdida por fricción disponible h_f debe ser mayor que cero.")

    raiz = math.sqrt(g * D * h_f / L)
    argumento_log = epsilon / (3.7 * D) + 1.78 * nu / (D * raiz)

    if argumento_log <= 0:
        raise ValueError("El argumento del logaritmo de la Ec. 11-3 no es válido.")

    Q = -0.965 * D**2 * raiz * math.log(argumento_log)

    if Q <= 0:
        raise ValueError(
            "La Ec. 11-3 produjo un caudal no físico. Revise h_f, D, L, ε y ν."
        )

    A = area_circular(D)
    V = Q / A
    Re = reynolds(V, D, nu)

    return {
        "Q": Q,
        "A": A,
        "V": V,
        "Re": Re,
        "h_f_disponible": h_f,
        "raiz_gDhL": raiz,
        "argumento_log": argumento_log,
        "ecuacion": "Mott 7a ed. — Ec. (11-3), basada en Swamee-Jain",
        "aplicable_turbulento": Re > 4000,
    }


def _carga_velocidad(v, g=G):
    return float(v) ** 2 / (2.0 * g)


def _hf_disponible_para_ii_a(
    tramos,
    gamma,
    P1,
    P2,
    z1,
    z2,
    hA,
    hR,
    tipo_v1,
    tipo_v2,
    V1_manual=0.0,
    V2_manual=0.0,
    g=G,
):
    """
    Determina si la Ec. 11-3 puede aplicarse directamente.

    Con una sola tubería, si ambos puntos están en esa misma tubería,
    sus cargas de velocidad son iguales y se cancelan. Si ambos son
    depósitos o velocidades manuales conocidas, también puede obtenerse
    h_f directamente. Si solo uno de los extremos tiene velocidad que
    depende de Q, hace falta solución numérica y la Ec. 11-3 deja de ser
    directa.
    """
    if len(tramos) != 1:
        return None, (
            "La Ec. 11-3 de Mott se aplica directamente a una tubería de diámetro uniforme. "
            "Este sistema tiene varios tramos; se mantiene el solucionador numérico general."
        )

    D = float(tramos[0]["D"])

    variable_1 = tipo_v1 == "tuberia"
    variable_2 = tipo_v2 == "tuberia"

    if variable_1 and variable_2:
        # Misma tubería: V1 = V2 y las cargas cinéticas se cancelan.
        hv1_menos_hv2 = 0.0
    elif not variable_1 and not variable_2:
        V1 = 0.0 if tipo_v1 == "deposito" else float(V1_manual)
        V2 = 0.0 if tipo_v2 == "deposito" else float(V2_manual)
        hv1_menos_hv2 = _carga_velocidad(V1, g) - _carga_velocidad(V2, g)
    else:
        return None, (
            "Uno de los extremos está en la tubería y el otro tiene velocidad fija/depósito. "
            "La diferencia de carga cinética depende de Q, por lo que la Ec. 11-3 no puede "
            "usarse como solución directa sin una iteración adicional."
        )

    h_f = (
        P1 / gamma
        + float(z1)
        + hv1_menos_hv2
        + float(hA)
        - float(hR)
        - P2 / gamma
        - float(z2)
    )

    if h_f <= 0:
        return None, (
            f"La carga disponible para fricción resultó h_f={h_f:.6g} m, que no es positiva."
        )

    return h_f, None


def _copiar_sin_perdidas_menores(tramos):
    salida = []
    for tramo in tramos:
        t = dict(tramo)
        t["K"] = 0.0
        t["K_extra"] = 0.0
        t["accesorios_detalle"] = []
        salida.append(t)
    return salida


def resolver_clase_ii_mott_v8(
    metodo,
    tramos,
    nu,
    gamma,
    P1,
    P2,
    z1,
    z2,
    hA,
    hR,
    tipo_v1,
    tipo_v2,
    transiciones=None,
    V1_manual=0.0,
    V2_manual=0.0,
    Q_min=1e-7,
    Q_max=10.0,
    g=G,
):
    """
    V8: conserva el motor robusto existente, pero cuando el caso permite
    aplicar literalmente el Método II-A de Mott usa la Ec. (11-3) como
    resultado principal y deja el solver numérico como verificación.

    Para II-B, la Ec. (11-3) se usa como estimación inicial Mott cuando es
    aplicable; el resultado final sigue incluyendo las pérdidas menores.
    """
    numerica = resolver_clase_ii_mott_con_transiciones(
        metodo=metodo,
        tramos=tramos,
        nu=nu,
        gamma=gamma,
        P1=P1,
        P2=P2,
        z1=z1,
        z2=z2,
        hA=hA,
        hR=hR,
        tipo_v1=tipo_v1,
        tipo_v2=tipo_v2,
        transiciones=transiciones or [],
        V1_manual=V1_manual,
        V2_manual=V2_manual,
        Q_min=Q_min,
        Q_max=Q_max,
        g=g,
    )

    numerica["mott_directo"] = {
        "aplicable": False,
        "motivo": "No corresponde aplicar Ec. 11-3 en este método/configuración.",
    }

    if metodo not in ("II-A", "II-B"):
        return numerica

    h_f, motivo = _hf_disponible_para_ii_a(
        tramos=tramos,
        gamma=gamma,
        P1=P1,
        P2=P2,
        z1=z1,
        z2=z2,
        hA=hA,
        hR=hR,
        tipo_v1=tipo_v1,
        tipo_v2=tipo_v2,
        V1_manual=V1_manual,
        V2_manual=V2_manual,
        g=g,
    )

    if h_f is None:
        numerica["mott_directo"] = {
            "aplicable": False,
            "motivo": motivo,
        }
        return numerica

    tramo = tramos[0]
    directo = caudal_ii_a_mott_ec_11_3(
        D=tramo["D"],
        L=tramo["L"],
        epsilon=tramo["epsilon"],
        nu=nu,
        h_f=h_f,
        g=g,
    )

    if not directo["aplicable_turbulento"]:
        numerica["mott_directo"] = {
            "aplicable": False,
            "motivo": (
                f"La Ec. 11-3 dio Re={directo['Re']:.0f}; no se aplicó como resultado principal "
                "porque el caso no queda claramente en régimen turbulento."
            ),
            "tentativo": directo,
        }
        return numerica

    Q_mott = directo["Q"]
    Q_num = float(numerica["Q_final"])
    diferencia_pct = (Q_mott - Q_num) / Q_num * 100.0 if Q_num != 0 else 0.0

    directo.update({
        "aplicable": True,
        "Q_numerico_verificacion": Q_num,
        "diferencia_porcentaje_vs_numerico": diferencia_pct,
    })

    numerica["mott_directo"] = directo

    if metodo == "II-A":
        tramos_A = _copiar_sin_perdidas_menores(tramos)
        sistema_mott = calcular_sistema_con_transiciones(
            Q_mott,
            tramos_A,
            nu,
            [],
            g=g,
        )
        residual_mott = residuo_clase_ii_con_transiciones(
            Q_mott,
            tramos_A,
            nu,
            gamma,
            P1,
            P2,
            z1,
            z2,
            hA,
            hR,
            tipo_v1,
            tipo_v2,
            [],
            V1_manual,
            V2_manual,
            g,
        )

        numerica["Q_numerico_verificacion"] = Q_num
        numerica["residual_numerico_verificacion"] = float(numerica["residual"])
        numerica["Q"] = Q_mott
        numerica["Q_final"] = Q_mott
        numerica["sistema"] = sistema_mott
        numerica["residual"] = residual_mott
        numerica["iteraciones"] = 0
        numerica["convergencia"] = True
        numerica["metodo_calculo_principal"] = "Mott Ec. (11-3) — solución directa"

    elif metodo == "II-B":
        numerica["Q_IIA_numerico_anterior"] = numerica.get("Q_IIA")
        numerica["Q_IIA"] = Q_mott
        numerica["correccion_porcentaje"] = (
            (Q_mott - numerica["Q_final"]) / Q_mott * 100.0
        )
        numerica["metodo_estimacion_inicial"] = "Mott Ec. (11-3)"

    return numerica


# ============================================================
# CLASE III-A — MOTT EC. (11-8)
# ============================================================


def diametro_iii_a_mott_ec_11_8(Q, L, epsilon, nu, h_L, g=G):
    """
    Método III-A de Mott, Ec. (11-8), SI.

    D = 0.66 [ ε^1.25 (LQ²/(g hL))^4.75
               + ν Q^9.4 (L/(g hL))^5.2 ]^0.04
    """
    Q = float(Q)
    L = float(L)
    epsilon = float(epsilon)
    nu = float(nu)
    h_L = float(h_L)

    if Q <= 0:
        raise ValueError("Q debe ser mayor que cero.")
    if L <= 0:
        raise ValueError("L debe ser mayor que cero.")
    if epsilon < 0:
        raise ValueError("La rugosidad no puede ser negativa.")
    if nu <= 0:
        raise ValueError("ν debe ser mayor que cero.")
    if h_L <= 0:
        raise ValueError("hL debe ser mayor que cero.")

    L_sobre_gh = L / (g * h_L)
    termino_rugosidad = epsilon**1.25 * (L * Q**2 / (g * h_L))**4.75
    termino_viscosidad = nu * Q**9.4 * (L_sobre_gh)**5.2
    argumento = termino_rugosidad + termino_viscosidad

    if argumento <= 0:
        raise ValueError("El argumento de la Ec. 11-8 no es válido.")

    D = 0.66 * argumento**0.04

    return {
        "D_minimo": D,
        "L_sobre_ghL": L_sobre_gh,
        "termino_rugosidad": termino_rugosidad,
        "termino_viscosidad": termino_viscosidad,
        "argumento": argumento,
        "ecuacion": "Mott 7a ed. — Ec. (11-8), Método III-A",
    }


def resolver_clase_iii_a_mott_v8(
    Q,
    L,
    epsilon,
    nu,
    hL_permitida,
    D_min=0.005,
    D_max=2.0,
    g=G,
):
    """
    Usa la Ec. 11-8 de Mott como resultado principal y ejecuta el método
    iterativo previo como verificación independiente con Colebrook.
    """
    mott = diametro_iii_a_mott_ec_11_8(
        Q=Q,
        L=L,
        epsilon=epsilon,
        nu=nu,
        h_L=hL_permitida,
        g=g,
    )

    D_mott = mott["D_minimo"]
    estado_mott = calcular_para_diametro(
        D=D_mott,
        Q=Q,
        L=L,
        epsilon=epsilon,
        nu=nu,
        K=0.0,
        g=g,
    )

    numerico = buscar_diametro_clase_iii_a(
        Q=Q,
        L=L,
        epsilon=epsilon,
        nu=nu,
        hL_permitida=hL_permitida,
        D_min=D_min,
        D_max=D_max,
        g=g,
    )

    D_num = float(numerico["D_minimo"])
    diferencia_pct = (D_mott - D_num) / D_num * 100.0 if D_num != 0 else 0.0
    residual_mott = estado_mott["hf"] - float(hL_permitida)

    resultado = dict(estado_mott)
    resultado.update(mott)
    resultado.update({
        "D_minimo": D_mott,
        "D_mott": D_mott,
        "D_numerico_verificacion": D_num,
        "diferencia_porcentaje_vs_numerico": diferencia_pct,
        "residual": residual_mott,
        "residual_numerico_verificacion": float(numerico["residual"]),
        "iteraciones_verificacion": int(numerico.get("iteraciones", 0)),
        "convergencia_verificacion": bool(numerico.get("convergencia", True)),
        "metodo_calculo_principal": "Mott Ec. (11-8) — solución directa",
    })

    return resultado

# ============================================================
# V9 — ROBUSTEZ: INTERVALOS AUTOMÁTICOS + HISTORIAL + TAMAÑO COMERCIAL
# ============================================================

from solvers_robustos import resolver_caudal_auto, resolver_diametro_auto
from catalogo_tuberias_mott import seleccionar_tamano_comercial


def _fila_historial_q_cero(q, sistema, residual):
    resultados = sistema.get("resultados", [])
    res = [float(r.get("Re", 0.0)) for r in resultados] or [0.0]
    fs = [float(r.get("f Darcy", 0.0)) for r in resultados] or [0.0]
    vs = [float(r.get("V (m/s)", 0.0)) for r in resultados] or [0.0]
    return {
        "Iteración": 0,
        "Q (m³/s)": float(q),
        "hL total (m)": float(sistema.get("hL_total", 0.0)),
        "Residual (m)": float(residual),
        "Re mín": min(res),
        "Re máx": max(res),
        "f mín": min(fs),
        "f máx": max(fs),
        "V máx (m/s)": max(vs),
    }


def _estimacion_iia_v9(
    tramos, nu, gamma, P1, P2, z1, z2, hA, hR,
    tipo_v1, tipo_v2, V1_manual=0.0, V2_manual=0.0, g=G,
):
    """Obtiene la estimación II-A preferentemente con Ec. 11-3."""
    h_f, motivo = _hf_disponible_para_ii_a(
        tramos=tramos, gamma=gamma, P1=P1, P2=P2, z1=z1, z2=z2,
        hA=hA, hR=hR, tipo_v1=tipo_v1, tipo_v2=tipo_v2,
        V1_manual=V1_manual, V2_manual=V2_manual, g=g,
    )

    if h_f is not None:
        t = tramos[0]
        directo = caudal_ii_a_mott_ec_11_3(
            D=t["D"], L=t["L"], epsilon=t["epsilon"], nu=nu, h_f=h_f, g=g
        )
        if directo["aplicable_turbulento"]:
            return directo["Q"], {
                **directo,
                "aplicable": True,
                "motivo": None,
            }

    tA = _copiar_sin_perdidas_menores(tramos)
    sol = resolver_caudal_auto(
        tA, nu, gamma, P1, P2, z1, z2, hA, hR,
        tipo_v1, tipo_v2, [], V1_manual, V2_manual,
    )
    return sol["Q_final"], {
        "aplicable": False,
        "motivo": motivo or (
            "La Ec. 11-3 no quedó en régimen turbulento; se obtuvo la estimación II-A "
            "con el solver automático sin pérdidas menores."
        ),
        "Q": sol["Q_final"],
    }


def resolver_clase_ii_mott_v9(
    metodo,
    tramos,
    nu,
    gamma,
    P1,
    P2,
    z1,
    z2,
    hA,
    hR,
    tipo_v1,
    tipo_v2,
    transiciones=None,
    V1_manual=0.0,
    V2_manual=0.0,
    modo_avanzado=False,
    Q_min=None,
    Q_max=None,
    estrategia_iia=None,
    g=G,
):
    """
    V9:
    - modo normal: busca automáticamente el intervalo de Q;
    - II-B parte realmente de la estimación II-A y la muestra como iteración 0;
    - guarda tabla de convergencia;
    - modo avanzado permite imponer Qmin/Qmax.
    """
    if metodo not in ("II-A", "II-B", "II-C"):
        raise ValueError("Método de Clase II no válido.")

    transiciones = transiciones or []
    tA = _copiar_sin_perdidas_menores(tramos)

    # Estimación II-A: Ec. 11-3 cuando aplica; solver automático si no.
    Q_iia, info_iia = _estimacion_iia_v9(
        tramos, nu, gamma, P1, P2, z1, z2, hA, hR,
        tipo_v1, tipo_v2, V1_manual, V2_manual, g,
    )

    # Si el enunciado exige explícitamente "prueba y error", la Ec. (11-3)
    # se conserva solo como estimación inicial y el resultado principal se cierra
    # iterativamente con Darcy-Weisbach.
    forzar_prueba_error = (metodo == "II-A" and estrategia_iia == "prueba_y_error_darcy")

    if metodo == "II-A" and info_iia.get("aplicable") and not forzar_prueba_error:
        Q_mott = float(Q_iia)
        sistema = calcular_sistema_con_transiciones(Q_mott, tA, nu, [], g=g)
        residual = residuo_clase_ii_con_transiciones(
            Q_mott, tA, nu, gamma, P1, P2, z1, z2, hA, hR,
            tipo_v1, tipo_v2, [], V1_manual, V2_manual, g,
        )
        verif = resolver_caudal_auto(
            tA, nu, gamma, P1, P2, z1, z2, hA, hR,
            tipo_v1, tipo_v2, [], V1_manual, V2_manual,
            seed=Q_mott,
            q_min_abs=(float(Q_min) if modo_avanzado and Q_min else 1e-10),
            q_max_abs=(float(Q_max) if modo_avanzado and Q_max else 100.0),
        )
        diferencia_pct = (
            (Q_mott - verif["Q_final"]) / verif["Q_final"] * 100.0
            if verif["Q_final"] else 0.0
        )
        info = dict(info_iia)
        info.update({
            "Q_numerico_verificacion": verif["Q_final"],
            "diferencia_porcentaje_vs_numerico": diferencia_pct,
        })
        return {
            "metodo": metodo,
            "Q": Q_mott,
            "Q_final": Q_mott,
            "Q_IIA": Q_mott,
            "sistema": sistema,
            "residual": residual,
            "iteraciones": 0,
            "convergencia": abs(residual) < 1e-7,
            "mott_directo": info,
            "historial_iteracion": verif["historial_iteracion"],
            "historial_verificacion": verif["historial_iteracion"],
            "intervalo_automatico": verif["intervalo_automatico"],
            "metodo_calculo_principal": "Mott Ec. (11-3) — solución directa",
        }

    # En II-A no directo se excluyen pérdidas menores. En II-B/C se usan completas.
    tramos_solver = tA if metodo == "II-A" else tramos
    trans_solver = [] if metodo == "II-A" else transiciones

    q_min_abs = float(Q_min) if modo_avanzado and Q_min is not None else 1e-10
    q_max_abs = float(Q_max) if modo_avanzado and Q_max is not None else 100.0

    sol = resolver_caudal_auto(
        tramos_solver, nu, gamma, P1, P2, z1, z2, hA, hR,
        tipo_v1, tipo_v2, trans_solver, V1_manual, V2_manual,
        seed=Q_iia,
        q_min_abs=q_min_abs,
        q_max_abs=q_max_abs,
    )
    sol["metodo"] = metodo
    sol["Q_IIA"] = float(Q_iia)
    sol["mott_directo"] = info_iia
    sol["metodo_calculo_principal"] = (
        "Mott II-A + corrección iterativa con pérdidas menores"
        if metodo == "II-B"
        else (
            "Solver iterativo completo II-C"
            if metodo == "II-C"
            else (
                "Prueba y error Darcy-Weisbach — iterativo (enunciado)"
                if forzar_prueba_error
                else "Solver automático sin pérdidas menores"
            )
        )
    )
    if forzar_prueba_error:
        sol["metodo_solicitado"] = "prueba_y_error_darcy"
        sol["Q_mott_referencia"] = float(Q_iia)
        sol["diferencia_porcentaje_vs_mott_referencia"] = (
            (float(sol["Q_final"]) - float(Q_iia)) / float(Q_iia) * 100.0
            if float(Q_iia) != 0 else 0.0
        )

    if metodo == "II-B":
        sistema_iia_full = calcular_sistema_con_transiciones(
            Q_iia, tramos, nu, transiciones, g=g
        )
        residual_iia_full = residuo_clase_ii_con_transiciones(
            Q_iia, tramos, nu, gamma, P1, P2, z1, z2, hA, hR,
            tipo_v1, tipo_v2, transiciones, V1_manual, V2_manual, g,
        )
        sol["historial_iteracion"] = [
            _fila_historial_q_cero(Q_iia, sistema_iia_full, residual_iia_full)
        ] + list(sol.get("historial_iteracion", []))
        sol["correccion_porcentaje"] = (
            (Q_iia - sol["Q_final"]) / Q_iia * 100.0 if Q_iia else 0.0
        )
    elif metodo == "II-A":
        sol["Q_IIA"] = sol["Q_final"]

    return sol


def resolver_clase_iii_a_mott_v9(
    Q,
    L,
    epsilon,
    nu,
    hL_permitida,
    catalogo_comercial=None,
    modo_avanzado=False,
    D_min=None,
    D_max=None,
    g=G,
):
    """
    III-A con Ec. 11-8 como resultado principal, verificación numérica auto-acotada
    y selección del siguiente diámetro interior comercial de Mott cuando se solicita.
    """
    mott = diametro_iii_a_mott_ec_11_8(Q, L, epsilon, nu, hL_permitida, g=g)
    D_mott = float(mott["D_minimo"])

    estado_mott = calcular_para_diametro(
        D=D_mott, Q=Q, L=L, epsilon=epsilon, nu=nu, K=0.0, g=g
    )

    verif = resolver_diametro_auto(
        Q=Q,
        L=L,
        epsilon=epsilon,
        nu=nu,
        hL_permitida=hL_permitida,
        seed=D_mott,
        d_min_abs=(float(D_min) if modo_avanzado and D_min is not None else 0.001),
        d_max_abs=(float(D_max) if modo_avanzado and D_max is not None else 5.0),
    )

    D_num = float(verif["D_minimo"])
    diferencia_pct = (D_mott - D_num) / D_num * 100.0 if D_num else 0.0
    residual_mott = float(estado_mott["hf"]) - float(hL_permitida)

    resultado = dict(estado_mott)
    resultado.update(mott)
    resultado.update({
        "D_minimo": D_mott,
        "D_mott": D_mott,
        "D_numerico_verificacion": D_num,
        "diferencia_porcentaje_vs_numerico": diferencia_pct,
        "residual": residual_mott,
        "residual_numerico_verificacion": float(verif["residual"]),
        "iteraciones_verificacion": int(verif["iteraciones"]),
        "convergencia_verificacion": bool(verif["convergencia"]),
        "historial_iteracion": verif["historial_iteracion"],
        "intervalo_automatico": verif["intervalo_automatico"],
        "metodo_calculo_principal": "Mott Ec. (11-8) — solución directa",
        "tamano_comercial": None,
    })

    if catalogo_comercial:
        resultado["tamano_comercial"] = seleccionar_tamano_comercial(
            D_mott, catalogo_comercial
        )

    return resultado
