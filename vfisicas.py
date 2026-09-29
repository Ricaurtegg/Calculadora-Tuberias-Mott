import math
import re
import unicodedata


def _diag(nivel, codigo, mensaje, sugerencia=None, bloqueante=False):
    return {
        "nivel": nivel,
        "codigo": codigo,
        "mensaje": mensaje,
        "sugerencia": sugerencia,
        "bloqueante": bool(bloqueante),
    }


def _norm(texto):
    texto = unicodedata.normalize("NFD", str(texto or ""))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto.lower().replace(",", ".")


def _hay_perdidas_menores(tramos, transiciones=None):
    for t in tramos or []:
        if float(t.get("K", 0.0) or 0.0) > 0:
            return True
        if float(t.get("K_extra", 0.0) or 0.0) > 0:
            return True
        if t.get("accesorios_detalle"):
            return True
        if t.get("curvas_detalle"):
            return True
    for trans in transiciones or []:
        tipo = str(trans.get("tipo", "") or "").lower()
        if tipo and "sin" not in tipo:
            return True
    return False


def validar_tramos_basicos(tramos, nu=None):
    diags = []
    if not tramos:
        return [_diag("error", "SIN_TRAMOS", "No existe ningún tramo definido.", "Agregue al menos un tramo de tubería.", True)]

    if nu is not None and (not math.isfinite(float(nu)) or float(nu) <= 0):
        diags.append(_diag("error", "NU_INVALIDA", "La viscosidad cinemática debe ser mayor que cero.", bloqueante=True))

    for i, t in enumerate(tramos, 1):
        try:
            L = float(t.get("L"))
            D = float(t.get("D"))
            eps = float(t.get("epsilon", 0.0) or 0.0)
        except Exception:
            diags.append(_diag("error", f"TRAMO_{i}_INCOMPLETO", f"El tramo {i} contiene datos no numéricos o incompletos.", bloqueante=True))
            continue
        if not math.isfinite(L) or L <= 0:
            diags.append(_diag("error", f"L_{i}_INVALIDA", f"La longitud del tramo {i} debe ser mayor que cero.", bloqueante=True))
        if not math.isfinite(D) or D <= 0:
            diags.append(_diag("error", f"D_{i}_INVALIDO", f"El diámetro del tramo {i} debe ser mayor que cero.", bloqueante=True))
        if not math.isfinite(eps) or eps < 0:
            diags.append(_diag("error", f"EPS_{i}_INVALIDA", f"La rugosidad del tramo {i} no puede ser negativa.", bloqueante=True))
        k = float(t.get("K", 0.0) or 0.0) + float(t.get("K_extra", 0.0) or 0.0)
        if not math.isfinite(k) or k < 0:
            diags.append(_diag("error", f"K_{i}_INVALIDO", f"ΣK del tramo {i} no puede ser negativo.", bloqueante=True))
    return diags


def validar_clase_ii_previa(
    metodo, tramos, transiciones, nu, gamma,
    P1, P2, z1, z2, hA, hR,
    tipo_v1="deposito", tipo_v2="deposito",
    V1_manual=0.0, V2_manual=0.0,
):
    diags = validar_tramos_basicos(tramos, nu)
    if not math.isfinite(float(gamma)) or float(gamma) <= 0:
        diags.append(_diag("error", "GAMMA_INVALIDO", "El peso específico debe ser mayor que cero.", bloqueante=True))
        return diags

    hay_menores = _hay_perdidas_menores(tramos, transiciones)
    if metodo == "II-A" and hay_menores:
        diags.append(_diag(
            "warning", "IIA_CON_MENORES",
            "Se configuraron pérdidas menores, pero el Método II-A de Mott las desprecia.",
            "Use II-B/II-C si desea incorporarlas; en II-A se excluirán del cálculo principal.",
        ))
    if metodo in ("II-B", "II-C") and not hay_menores:
        diags.append(_diag(
            "warning", "IIB_IIC_SIN_MENORES",
            f"{metodo} no tiene pérdidas menores configuradas; el resultado tenderá a coincidir con II-A.",
            "Revise si el enunciado realmente incluye accesorios, entradas, salidas o transiciones.",
        ))

    # Si ambas velocidades son conocidas, se puede saber antes de iterar si queda carga positiva.
    v1_conocida = tipo_v1 != "tuberia"
    v2_conocida = tipo_v2 != "tuberia"
    if v1_conocida and v2_conocida:
        V1 = 0.0 if tipo_v1 == "deposito" else float(V1_manual)
        V2 = 0.0 if tipo_v2 == "deposito" else float(V2_manual)
        g = 9.81
        h_disp = (
            float(P1) / float(gamma) + float(z1) + V1**2/(2*g) + float(hA)
            - float(P2) / float(gamma) - float(z2) - V2**2/(2*g) - float(hR)
        )
        if h_disp <= 0:
            diags.append(_diag(
                "error", "CARGA_DISPONIBLE_NO_POSITIVA",
                f"La carga disponible en el sentido 1→2 es {h_disp:.6g} m, por lo que no existe una solución de caudal positivo con ese sentido de flujo y esos datos.",
                "Revise elevaciones, presiones, bomba/turbina o el sentido supuesto del flujo.",
                True,
            ))
        else:
            diags.append(_diag("ok", "CARGA_DISPONIBLE", f"Carga disponible preliminar para pérdidas: {h_disp:.6g} m."))

    return diags


def validar_clase_iii_a_previa(Q, L, epsilon, nu, hL_permitida):
    diags = []
    valores = {"Q": Q, "L": L, "ν": nu}
    for nombre, valor in valores.items():
        try:
            valor = float(valor)
        except Exception:
            diags.append(_diag("error", f"{nombre}_INVALIDO", f"{nombre} debe ser numérico.", bloqueante=True))
            continue
        if not math.isfinite(valor) or valor <= 0:
            diags.append(_diag("error", f"{nombre}_INVALIDO", f"{nombre} debe ser mayor que cero.", bloqueante=True))
    if float(epsilon) < 0:
        diags.append(_diag("error", "EPS_INVALIDA", "La rugosidad no puede ser negativa.", bloqueante=True))
    if not math.isfinite(float(hL_permitida)) or float(hL_permitida) <= 0:
        diags.append(_diag(
            "error", "HL_NO_POSITIVA",
            f"La carga disponible para pérdidas es {float(hL_permitida):.6g} m y debe ser positiva para calcular un diámetro por III-A.",
            "Revise presiones, cotas, bomba/turbina y el sentido del flujo.", True,
        ))
    return diags


def validar_clase_iii_b_previa(D, Q, L, epsilon, nu, D_minimo_previo=None):
    diags = []
    for nombre, valor in (("D", D), ("Q", Q), ("L", L), ("ν", nu)):
        if not math.isfinite(float(valor)) or float(valor) <= 0:
            diags.append(_diag("error", f"{nombre}_INVALIDO", f"{nombre} debe ser mayor que cero.", bloqueante=True))
    if float(epsilon) < 0:
        diags.append(_diag("error", "EPS_INVALIDA", "La rugosidad no puede ser negativa.", bloqueante=True))
    if D_minimo_previo is not None and float(D) + 1e-12 < float(D_minimo_previo):
        diags.append(_diag(
            "error", "D_COMERCIAL_MENOR_DMIN",
            f"El diámetro seleccionado ({float(D)*1000:.3f} mm) es menor que Dmín de III-A ({float(D_minimo_previo)*1000:.3f} mm).",
            "Seleccione el siguiente tamaño comercial cuyo diámetro interior sea ≥ Dmín.", True,
        ))
    elif D_minimo_previo is not None:
        diags.append(_diag("ok", "D_COMERCIAL_CUMPLE_DMIN", "El diámetro seleccionado es mayor o igual que Dmín de III-A."))
    return diags


def validar_resultados_hidraulicos(resultados, residual=None, tolerancia_residual=1e-7):
    diags = []
    filas = resultados or []
    for i, r in enumerate(filas, 1):
        Re = float(r.get("Re", 0.0) or 0.0)
        f = float(r.get("f Darcy", r.get("f", 0.0)) or 0.0)
        V = float(r.get("V (m/s)", r.get("V", 0.0)) or 0.0)
        if 2000.0 < Re < 4000.0:
            diags.append(_diag(
                "warning", f"RE_TRANSICION_{i}",
                f"El tramo {i} queda en la región de transición (Re={Re:.0f}). El factor de fricción y la solución pueden ser sensibles.",
                "Revise las condiciones del problema; evite presentar el factor de fricción como inequívocamente laminar o turbulento.",
            ))
        elif 0 < Re <= 2000.0:
            diags.append(_diag("info", f"RE_LAMINAR_{i}", f"El tramo {i} está en régimen laminar (Re={Re:.0f}); corresponde usar f=64/Re."))
        if f <= 0 or not math.isfinite(f):
            diags.append(_diag("error", f"F_INVALIDO_{i}", f"El factor de fricción del tramo {i} no es físico: f={f}.", bloqueante=True))
        elif f > 0.2:
            diags.append(_diag("warning", f"F_ALTO_{i}", f"El factor de fricción del tramo {i} es inusualmente alto (f={f:.4g}). Revise Re, diámetro, rugosidad y unidades."))
        if not math.isfinite(V):
            diags.append(_diag("error", f"V_INVALIDA_{i}", f"La velocidad del tramo {i} no es finita.", bloqueante=True))

    if residual is not None:
        residual = float(residual)
        if not math.isfinite(residual):
            diags.append(_diag("error", "RESIDUAL_NO_FINITO", "El residual de energía no es finito.", bloqueante=True))
        elif abs(residual) <= tolerancia_residual:
            diags.append(_diag("ok", "RESIDUAL_OK", f"Residual de energía satisfactorio: {residual:.3e} m."))
        else:
            diags.append(_diag(
                "warning", "RESIDUAL_ALTO",
                f"El residual de energía es {residual:.3e} m, mayor que la tolerancia recomendada de {tolerancia_residual:.1e} m.",
                "Revise convergencia, intervalos y datos de entrada.",
            ))
    return diags


def _detectar_extremos_abiertos(texto_normalizado):
    """Asocia cada mención de ``abierto/atmósfera`` al extremo más cercano.

    Esto evita falsos positivos como::

        depósito 1 presurizado ... depósito 2 abierto a la atmósfera

    donde una expresión regular amplia puede recorrer desde ``depósito 1`` hasta
    la palabra ``abierto`` que en realidad describe al depósito 2.
    """
    t = texto_normalizado or ""

    refs_pat = {
        1: re.compile(
            r"(?:deposito\s*(?:n(?:umero)?\.?\s*)?1|deposito\s+uno|primer\s+deposito|"
            r"deposito\s+inicial|reservorio\s*(?:n(?:umero)?\.?\s*)?1|primer\s+reservorio|"
            r"punto\s*(?:n(?:umero)?\.?\s*)?1|punto\s+uno)"
        ),
        2: re.compile(
            r"(?:deposito\s*(?:n(?:umero)?\.?\s*)?2|deposito\s+dos|segundo\s+deposito|"
            r"deposito\s+final|reservorio\s*(?:n(?:umero)?\.?\s*)?2|segundo\s+reservorio|"
            r"punto\s*(?:n(?:umero)?\.?\s*)?2|punto\s+dos)"
        ),
    }

    apertura_pat = re.compile(
        r"(?:abiert[oa](?:\s+a\s+la\s+atmosfera)?|"
        r"a\s+la\s+atmosfera|presion\s+atmosferica|atmosferic[oa])"
    )

    referencias = []
    for punto, patron in refs_pat.items():
        for m in patron.finditer(t):
            referencias.append((punto, m.start(), m.end()))

    abiertos = set()

    # Formas globales inequívocas: "ambos/los dos depósitos están abiertos".
    if re.search(
        r"(?:ambos|los\s+dos)\s+(?:depositos|reservorios)[^.\n;]{0,55}"
        r"(?:abiert[oa]s?|atmosfera|atmosferic)",
        t,
    ) or re.search(
        r"(?:depositos|reservorios)[^.\n;]{0,35}(?:ambos|los\s+dos)[^.\n;]{0,35}"
        r"(?:abiert[oa]s?|atmosfera|atmosferic)",
        t,
    ):
        abiertos.update((1, 2))

    # Para cada descriptor atmosférico, elegimos la referencia de extremo más
    # cercana dentro de una ventana local. Así una referencia al extremo 2
    # "corta" naturalmente la asociación con el extremo 1.
    for a in apertura_pat.finditer(t):
        candidatos = []
        for punto, ini, fin in referencias:
            if fin <= a.start():
                entre = t[fin:a.start()]
                # OCR puede perder el número del segundo depósito, por ejemplo:
                # "deposito 1 presurizado hasta un deposito abierto".
                # Si aparece otra referencia genérica de extremo entre el punto
                # identificado y la palabra "abierto", no dejamos que la
                # condición atmosférica salte hacia atrás hasta el punto 1.
                if re.search(r"\b(?:deposito|reservorio|punto)\b", entre):
                    continue
                distancia = a.start() - fin
                lado = 0
            elif ini >= a.end():
                entre = t[a.end():ini]
                if re.search(r"\b(?:deposito|reservorio|punto)\b", entre):
                    continue
                distancia = ini - a.end()
                lado = 1
            else:
                distancia = 0
                lado = 0

            if distancia <= 90:
                candidatos.append((distancia, lado, punto, ini, fin))

        if not candidatos:
            continue

        candidatos.sort(key=lambda x: (x[0], x[1], abs(((x[3] + x[4]) / 2) - ((a.start() + a.end()) / 2))))
        mejor_distancia = candidatos[0][0]
        mejor_lado = candidatos[0][1]
        mejores = [c for c in candidatos if c[0] == mejor_distancia and c[1] == mejor_lado]

        puntos = {c[2] for c in mejores}
        if len(puntos) == 1:
            abiertos.add(next(iter(puntos)))

    # Respaldo OCR: si se perdió el número 2 pero la estructura conserva
    # "desde deposito 1 ... hasta un deposito abierto", inferimos que ese
    # segundo depósito corresponde al extremo 2. No se usa esta inferencia
    # si el texto no contiene la relación direccional desde/hasta.
    if re.search(
        r"desde\s+(?:un\s+|el\s+)?deposito\s*1[^.\n;]{0,120}"
        r"hasta\s+(?:un\s+|el\s+)?deposito[^.\n;]{0,35}"
        r"(?:abiert[oa]|atmosfera|atmosferic)",
        t,
    ):
        abiertos.add(2)
        # Si el punto 1 quedó marcado solo por una asociación ambigua, la
        # estructura direccional anterior indica que la apertura pertenece al 2.
        if re.search(r"deposito\s*1[^.\n;]{0,45}(?:presuriz|cerrad)", t):
            abiertos.discard(1)

    return abiertos


def detectar_atmosfera_y_conflictos(enunciado, prefill=None):
    """Diagnósticos textuales previos al autollenado; no altera los datos.

    V14.2.1: la condición ``abierto a la atmósfera`` se asocia al extremo
    explícito más cercano para no confundir descripciones del tipo
    ``depósito 1 presurizado ... depósito 2 abierto``.
    """
    t = _norm(enunciado)
    diags = []
    prefill = prefill or {}

    abiertos = _detectar_extremos_abiertos(t)

    for punto in (1, 2):
        if punto not in abiertos:
            continue

        P = prefill.get(f"P{punto}_kpa")
        if P is not None and abs(float(P)) > 1e-6:
            diags.append(_diag(
                "error", f"P{punto}_ATMOSFERA_CONTRADICCION",
                f"El enunciado describe el punto/depósito {punto} como abierto a la atmósfera, pero también se detectó P{punto}={float(P):g} kPa manométricos.",
                f"Para una superficie libre abierta y presión manométrica, P{punto} debe ser 0 kPa; confirme cuál dato del enunciado debe prevalecer.",
                True,
            ))
        else:
            diags.append(_diag(
                "ok", f"P{punto}_ATMOSFERA",
                f"Punto/depósito {punto} detectado como abierto a la atmósfera; P{punto}=0 kPa manométricos es consistente."
            ))
    return diags

def hay_bloqueantes(diags):
    return any(bool(d.get("bloqueante")) for d in diags or [])
