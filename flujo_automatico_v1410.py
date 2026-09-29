"""Flujo automático supervisado de principio a fin — V14.10.

V14.10 NO sustituye la revisión humana de V14.7 ni modifica los solvers.
Automatiza únicamente la ejecución posterior a un snapshot ya completo y
confirmado: prepara entradas, resuelve, audita con V14.8.3 y construye el
reporte trazable V14.9.

Principios:
- la firma V14.7 debe coincidir exactamente;
- no se inventan velocidades manuales ni propiedades faltantes;
- el modo manual sigue disponible como respaldo;
- cada ejecución conserva una lista de etapas y un resumen reproducible.
"""
from __future__ import annotations

import copy
import math

from catalogos_mott import (
    FLUIDOS,
    MATERIALES,
    calcular_k_accesorio,
    propiedades_agua_interpoladas,
)
from transiciones_mott import (
    calcular_k_curva_tuberia,
    calcular_sistema_con_transiciones,
    residuo_clase_ii_con_transiciones,
)
from solvers_robustos import resolver_biseccion_historial
from transferencia_v147 import (
    VERSION_TRANSFERENCIA,
    construir_previsualizacion_transferencia,
    confirmacion_corresponde,
)
from reporte_final_v149 import (
    VERSION_REPORTE,
    construir_manifiesto_ejecucion,
    construir_reporte_final,
)
from auditoria_solucion_v148 import (
    auditar_sistema_hidraulico,
    auditar_clase_ii_mott,
    auditar_clase_iii_a,
    auditar_clase_iii_b,
)
from metodos_mott import resolver_clase_ii_mott_v9, resolver_clase_iii_a_mott_v9
from calculos.hidraulica import (
    peso_especifico,
    resolver_clase_i,
    residuo_energia,
    verificar_clase_iii_b,
)
from auditoria_fisica_v1416 import auditar_fisica, VERSION_AUDITORIA_FISICA
from procedimiento_mott_v1419 import construir_procedimiento_mott

VERSION_FLUJO = "V14.10"
VERSION_DIAGRAMAS_V1415 = "V14.15"


class ErrorFlujoV1410(ValueError):
    pass


def _finito(v):
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def _positivo(v):
    return _finito(v) and float(v) > 0.0


def _propiedades_fluido(prefill: dict) -> dict:
    nombre = prefill.get("fluido_app") or prefill.get("fluido_detectado")
    propiedades_explicitas_v1412 = bool(prefill.get("propiedades_explicitas_v1412"))
    rho_exp_v1412 = prefill.get("rho_usuario") if propiedades_explicitas_v1412 else None
    nu_exp_v1412 = prefill.get("nu_usuario_m2s") if propiedades_explicitas_v1412 else None

    # V14.17.7.1: si el enunciado proporciona ρ/ν explícitos (por ejemplo
    # mediante SG + μ), esas propiedades bastan para ejecutar aunque OCR no
    # consiga identificar un nombre de fluido del catálogo.
    if not nombre and _positivo(rho_exp_v1412) and _positivo(nu_exp_v1412):
        rho = float(rho_exp_v1412)
        nu = float(nu_exp_v1412)
        return {
            "nombre": "Propiedades explícitas",
            "rho": rho,
            "nu": nu,
            "gamma": peso_especifico(rho),
        }

    if not nombre:
        raise ErrorFlujoV1410("No hay un fluido confirmado ni propiedades ρ/ν suficientes en el expediente.")

    if nombre == "Personalizado":
        rho = prefill.get("rho_usuario")
        nu = prefill.get("nu_usuario_m2s")
        if not _positivo(rho) or not _positivo(nu):
            raise ErrorFlujoV1410("El fluido personalizado requiere ρ > 0 y ν > 0.")
        rho = float(rho); nu = float(nu)
        return {"nombre": nombre, "rho": rho, "nu": nu, "gamma": peso_especifico(rho)}

    if nombre not in FLUIDOS:
        raise ErrorFlujoV1410(f"El fluido confirmado no existe en el catálogo: {nombre}")

    datos = FLUIDOS[nombre]
    if datos.get("tipo") == "agua_interpolar":
        T = prefill.get("temperatura_c")
        if not _finito(T):
            raise ErrorFlujoV1410("El agua interpolada requiere una temperatura confirmada.")
        d = propiedades_agua_interpoladas(float(T))
        rho = float(d["rho"]); nu = float(d["nu"])
    else:
        rho = datos.get("rho")
        nu = datos.get("nu")
        if nu is None:
            nu = prefill.get("nu_usuario_m2s")
        if not _positivo(rho) or not _positivo(nu):
            raise ErrorFlujoV1410(f"{nombre} no tiene ρ/ν suficientes para ejecutar automáticamente.")
        rho = float(rho); nu = float(nu)

    # V14.12: si el enunciado suministra propiedades físicas explícitas, estas
    # prevalecen sobre la tabla para esa ejecución. No se inventa ninguna: solo
    # se reemplaza la propiedad que fue leída y normalizada del enunciado.
    if propiedades_explicitas_v1412:
        if _positivo(rho_exp_v1412):
            rho = float(rho_exp_v1412)
        if _positivo(nu_exp_v1412):
            nu = float(nu_exp_v1412)

    return {"nombre": nombre, "rho": rho, "nu": nu, "gamma": peso_especifico(rho)}


def _epsilon_tramo(t: dict) -> float:
    material = t.get("material")
    if material == "Personalizada":
        eps = t.get("epsilon_m")
        if eps is None or not _finito(eps) or float(eps) < 0:
            raise ErrorFlujoV1410("Un material personalizado requiere ε ≥ 0.")
        return float(eps)
    if material not in MATERIALES:
        raise ErrorFlujoV1410(f"Material no reconocido por el catálogo: {material}")
    return float(MATERIALES[material])


def _detalle_accesorio(nombre: str, cantidad: int, k_unit: float, item: dict) -> list[dict]:
    posiciones = list(item.get("posiciones_fraccion") or [])
    if not posiciones and item.get("posicion_fraccion") is not None:
        posiciones = [item.get("posicion_fraccion")]
    posiciones = [min(max(float(x), 0.0), 1.0) for x in posiciones if _finito(x)]
    if not posiciones:
        posiciones = [0.70]
    while len(posiciones) < cantidad:
        posiciones.append(posiciones[-1])
    return [
        {"nombre": nombre, "cantidad": 1, "K_unitario": float(k_unit), "posicion_fraccion": posiciones[i]}
        for i in range(cantidad)
    ]


def construir_tramos_solver(prefill: dict, clase: str) -> list[dict]:
    """Convierte los tramos confirmados V14.7 al formato exacto de los solvers."""
    out = []
    for i, t in enumerate(prefill.get("tramos") or [], 1):
        n = int(t.get("numero", i) or i)
        L = t.get("L_m"); D = t.get("D_m")
        if not _positivo(L):
            raise ErrorFlujoV1410(f"Tramo {n}: L no válida.")
        if clase != "Clase III-A" and not _positivo(D):
            raise ErrorFlujoV1410(f"Tramo {n}: D no válida.")
        if clase == "Clase III-A" and D is None:
            # III-A no usa D como dato, pero el tramo queda disponible para trazabilidad.
            D_solver = None
        else:
            D_solver = float(D)

        material = t.get("material")
        epsilon = _epsilon_tramo(t)
        K_total = 0.0
        detalles = []

        # III-A no incorpora pérdidas menores en la Ec. 11-8 de esta implementación.
        if clase != "Clase III-A":
            for acc in t.get("accesorios") or []:
                nombre = acc.get("nombre")
                cantidad = max(1, int(acc.get("cantidad", 1) or 1))
                try:
                    info = calcular_k_accesorio(nombre, float(D_solver), material)
                except Exception as e:
                    raise ErrorFlujoV1410(f"Tramo {n}: no se pudo calcular K de '{nombre}': {e}") from e
                k_unit = float(info["k"])
                K_total += cantidad * k_unit
                detalles.extend(_detalle_accesorio(nombre, cantidad, k_unit, acc))

            for curva in t.get("curvas") or []:
                r_D = curva.get("r_D")
                ang = curva.get("angulo_grados", 90.0)
                if not _positivo(r_D) or not _positivo(ang):
                    raise ErrorFlujoV1410(f"Tramo {n}: curva sin r/D o ángulo válido.")
                info = calcular_k_curva_tuberia(float(D_solver), material, float(r_D), float(ang))
                k = float(info["k"])
                K_total += k
                pos = curva.get("posicion_fraccion", 0.60)
                pos = min(max(float(pos), 0.0), 1.0) if _finito(pos) else 0.60
                detalles.append({
                    "nombre": f"Curva θ={float(ang):.1f}°, r/D={float(r_D):.2f}",
                    "cantidad": 1, "K_unitario": k, "posicion_fraccion": pos,
                })

            k_extra = t.get("K_extra")
            if k_extra is not None and _finito(k_extra) and float(k_extra) > 0:
                K_total += float(k_extra)
        else:
            k_extra = 0.0

        out.append({
            "numero": n,
            "L": float(L),
            "D": D_solver,
            "material": material,
            "epsilon": epsilon,
            "K": float(K_total),
            "K_extra": float(k_extra or 0.0),
            "K_extra_posicion_fraccion": float(t.get("K_extra_posicion_fraccion", 0.85) or 0.85),
            "accesorios_detalle": detalles,
            "componentes_graficos": copy.deepcopy(t.get("componentes_graficos") or []),
        })
    if not out:
        raise ErrorFlujoV1410("No existen tramos confirmados para ejecutar.")
    return out


def _transiciones(prefill: dict) -> list[dict]:
    return [
        {"entre": int(x.get("entre", i) or i), "tipo": x.get("tipo"), "angulo_grados": x.get("angulo_grados")}
        for i, x in enumerate(prefill.get("transiciones") or [], 1)
    ]


def _tipo_velocidad(prefill: dict, clave: str, default="tuberia") -> str:
    valor = str(prefill.get(clave) or default).strip().lower()
    aliases = {
        "deposito": "deposito", "depósito": "deposito", "superficie libre": "deposito",
        "tuberia": "tuberia", "tubería": "tuberia", "manual": "manual",
    }
    valor = aliases.get(valor, valor)
    if valor not in {"deposito", "tuberia", "manual"}:
        raise ErrorFlujoV1410(f"Condición de velocidad no reconocida: {valor}")
    if valor == "manual":
        raise ErrorFlujoV1410(
            "V14.10 no inventa una velocidad extrema manual. Revise ese dato en el modo manual."
        )
    return valor


def _p_pa(prefill, clave):
    v = prefill.get(clave)
    return None if v is None else float(v) * 1000.0


def _valor(prefill, clave, *, requerido=True, default=None):
    v = prefill.get(clave, default)
    if requerido and v is None:
        raise ErrorFlujoV1410(f"Falta {clave} en el snapshot confirmado.")
    return None if v is None else float(v)


def _incognita_i(prefill: dict) -> tuple[str, str]:
    etiqueta = prefill.get("incognita_clase_i")
    mapa = {
        "Presión P2": "P2", "Presión P1": "P1",
        "Carga agregada por bomba hA": "hA", "Carga retirada hR": "hR",
        "Elevación z2": "z2", "Elevación z1": "z1",
        "P2": "P2", "P1": "P1", "hA": "hA", "hR": "hR", "z2": "z2", "z1": "z1",
    }
    if etiqueta not in mapa:
        raise ErrorFlujoV1410("Clase I requiere una incógnita explícita compatible con el solver.")
    return mapa[etiqueta], str(etiqueta)


def construir_estado_flujo(resultado: dict, enunciado: str = "", previsualizacion: dict | None = None,
                           firma_confirmada: str | None = None) -> dict:
    """Resumen determinista de las etapas del flujo supervisado."""
    preview = copy.deepcopy(previsualizacion) if previsualizacion else construir_previsualizacion_transferencia(resultado, enunciado)
    base = preview.get("resultado_consolidado") or resultado or {}
    exp = base.get("expediente_v145") or {}
    confianza = base.get("confianza_datos_v1411") or {}
    pasos = [
        {"id": "interpretacion", "titulo": "Interpretación", "estado": "OK" if base.get("clase") else "PENDIENTE"},
        {"id": "consolidacion", "titulo": "Consolidación V14.5", "estado": "OK" if exp else "PENDIENTE"},
        {"id": "faltantes", "titulo": "Completado V14.6", "estado": "OK" if exp and not exp.get("faltantes") else "PENDIENTE"},
    ]
    if confianza:
        pasos.append({
            "id": "confianza", "titulo": "Confianza individual V14.11",
            "estado": "OK" if confianza.get("listo_para_v147") else "BLOQUEADO",
        })
    pasos += [
        {"id": "revision", "titulo": "Revisión V14.7", "estado": "OK" if preview.get("listo_para_transferir") else "BLOQUEADO"},
        {"id": "confirmacion", "titulo": "Confirmación humana", "estado": "OK" if confirmacion_corresponde(preview, firma_confirmada) else "PENDIENTE"},
        {"id": "solver", "titulo": "Solver", "estado": "PENDIENTE"},
        {"id": "auditoria", "titulo": "Auditoría V14.8.3", "estado": "PENDIENTE"},
        {"id": "auditoria_fisica", "titulo": "Auditoría física V14.16", "estado": "PENDIENTE"},
        {"id": "reporte", "titulo": "Reporte V14.9", "estado": "PENDIENTE"},
    ]
    confianza_ok = (not confianza) or bool(confianza.get("listo_para_v147"))
    bloqueos = list(preview.get("bloqueos") or [])
    if confianza and not confianza_ok:
        bloqueos.append("V14.11 conserva datos de confianza media/baja sin confirmar.")
    return {
        "version": VERSION_FLUJO,
        "clase": base.get("clase"),
        "firma_v147": preview.get("firma"),
        "listo_para_ejecutar": bool(confianza_ok and preview.get("listo_para_transferir") and confirmacion_corresponde(preview, firma_confirmada)),
        "pasos": pasos,
        "bloqueos": bloqueos,
    }


def _refinar_clase_ii_si_necesario(solucion: dict, metodo: str, tramos: list[dict], nu: float, gamma: float,
                                    P1: float, P2: float, z1: float, z2: float, hA: float, hR: float,
                                    tipo_v1: str, tipo_v2: str, transiciones: list[dict]) -> dict:
    """Cierra una raíz ya encontrada cuando el criterio histórico paró por ancho de intervalo.

    No cambia el modelo hidráulico ni la solución principal de II-A. Solo se activa
    en II-B/II-C si el residual es pequeño pero ``convergencia`` quedó falso.
    """
    s = copy.deepcopy(solucion or {})
    if metodo not in ("II-B", "II-C") or s.get("convergencia", True):
        return s
    residual_pre = s.get("residual")
    if not _finito(residual_pre) or abs(float(residual_pre)) > 1e-4:
        return s
    inter = s.get("intervalo_automatico") or {}
    a = inter.get("Q_inf"); b = inter.get("Q_sup")
    if not (_positivo(a) and _positivo(b)):
        return s

    def residual(q):
        return residuo_clase_ii_con_transiciones(
            q, tramos, nu, gamma, P1, P2, z1, z2, hA, hR,
            tipo_v1, tipo_v2, transiciones, 0.0, 0.0,
        )

    def estado(q):
        return calcular_sistema_con_transiciones(q, tramos, nu, transiciones)

    try:
        raiz, res, historial, sistema = resolver_biseccion_historial(
            residual, float(a), float(b), tol_residual=1e-11, tol_rel=1e-13,
            max_iter=180, estado_func=estado,
        )
    except Exception:
        return s

    if sistema is None:
        sistema = estado(raiz)
    if abs(float(res)) >= abs(float(residual_pre)):
        return s

    s["Q"] = float(raiz)
    s["Q_final"] = float(raiz)
    s["residual"] = float(res)
    s["sistema"] = sistema
    s["iteraciones"] = int(s.get("iteraciones", 0) or 0) + len(historial)
    s["convergencia"] = abs(float(res)) <= 1e-8
    if metodo == "II-B" and s.get("Q_IIA"):
        s["correccion_porcentaje"] = (float(s["Q_IIA"]) - float(raiz)) / float(s["Q_IIA"]) * 100.0
    s["refinamiento_v1410"] = {
        "aplicado": True,
        "residual_antes_m": float(residual_pre),
        "residual_despues_m": float(res),
        "iteraciones_adicionales": len(historial),
        "criterio": "cierre numérico de la misma ecuación de energía",
    }
    return s


def _entrada_actual(prefill: dict, clase: str) -> dict:
    inc_i = None
    if clase == "Clase I":
        try: inc_i = _incognita_i(prefill)[0]
        except Exception: inc_i = None
    gen = {
        "fluido_app": (prefill.get("fluido_app") or prefill.get("fluido_detectado")
                       or ("Propiedades explícitas" if (prefill.get("propiedades_explicitas_v1412")
                           and _positivo(prefill.get("rho_usuario")) and _positivo(prefill.get("nu_usuario_m2s"))) else None)),
        "Q_m3s": None if clase in ("Clase II-A", "Clase II-B", "Clase II-C") else prefill.get("Q_m3s"),
        "P1_kpa": None if inc_i == "P1" else prefill.get("P1_kpa"),
        "P2_kpa": None if inc_i == "P2" else prefill.get("P2_kpa"),
        "z1_m": None if inc_i == "z1" else prefill.get("z1_m"),
        "z2_m": None if inc_i == "z2" else prefill.get("z2_m"),
        "hA_m": None if inc_i == "hA" else prefill.get("hA_m"),
        "hR_m": None if inc_i == "hR" else prefill.get("hR_m"),
    }
    trs = []
    for t in prefill.get("tramos") or []:
        trs.append({"L_m": t.get("L_m"), "D_m": None if clase == "Clase III-A" else t.get("D_m"), "material": t.get("material")})
    return {"generales": gen, "tramos": trs}



def _fila_resultado_unico_v1415(tramo: dict, r: dict, *, D=None) -> dict:
    """Normaliza un resultado de una sola tubería al esquema tabular de diagramas."""
    Dv = float(D if D is not None else r.get("D", tramo.get("D", 0.0)) or 0.0)
    return {
        "Tramo": int(tramo.get("numero", 1) or 1),
        "L (m)": float(tramo.get("L", 0.0) or 0.0),
        "D (m)": Dv,
        "Material": tramo.get("material"),
        "ε (m)": float(tramo.get("epsilon", 0.0) or 0.0),
        "A (m2)": float(r.get("A", 0.0) or 0.0),
        "V (m/s)": float(r.get("V", 0.0) or 0.0),
        "Re": float(r.get("Re", 0.0) or 0.0),
        "regimen": r.get("regimen"),
        "ε/D": float(r.get("eps_rel", 0.0) or 0.0),
        "f Darcy": float(r.get("f", 0.0) or 0.0),
        "ΣK": float(tramo.get("K", 0.0) or 0.0),
        "hf (m)": float(r.get("hf", 0.0) or 0.0),
        "hm (m)": float(r.get("hm", 0.0) or 0.0),
    }


def construir_contexto_diagramas_v1415(base: dict, resultado_solver: dict, propiedades: dict) -> dict:
    """Crea el contexto gráfico desde los mismos datos usados por el solver.

    No infiere magnitudes nuevas. Si una clase no permite construir un perfil
    reproducible con los datos ya resueltos, devuelve ``disponible=False``.
    """
    clase = str((base or {}).get("clase") or "")
    prefill = copy.deepcopy((base or {}).get("prefill") or {})
    gamma = float((propiedades or {}).get("gamma", 0.0) or 0.0)
    if gamma <= 0:
        return {"version": VERSION_DIAGRAMAS_V1415, "disponible": False, "motivo": "γ no disponible"}

    try:
        tramos = construir_tramos_solver(prefill, clase)
    except Exception as exc:
        return {"version": VERSION_DIAGRAMAS_V1415, "disponible": False, "motivo": str(exc)}

    default_extremo = "tuberia" if clase in ("Clase II-A", "Clase II-B", "Clase II-C") else "deposito"
    tipo_v1 = str(prefill.get("v1_tipo") or default_extremo).lower().replace("depósito", "deposito").replace("tubería", "tuberia")
    tipo_v2 = str(prefill.get("v2_tipo") or default_extremo).lower().replace("depósito", "deposito").replace("tubería", "tuberia")
    if tipo_v1 not in {"deposito", "tuberia"}: tipo_v1 = "deposito"
    if tipo_v2 not in {"deposito", "tuberia"}: tipo_v2 = "deposito"

    P1 = _p_pa(prefill, "P1_kpa")
    P2 = _p_pa(prefill, "P2_kpa")
    z1 = prefill.get("z1_m")
    z2 = prefill.get("z2_m")
    hA = float(prefill.get("hA_m", 0.0) or 0.0)
    hR = float(prefill.get("hR_m", 0.0) or 0.0)
    Q = prefill.get("Q_m3s")
    sistema = resultado_solver.get("sistema") if isinstance(resultado_solver, dict) else None

    # Clase I: usa las condiciones finales ya resueltas por la EGE.
    if clase == "Clase I":
        finales = copy.deepcopy(resultado_solver.get("estado_final") or {})
        P1 = finales.get("P1", P1); P2 = finales.get("P2", P2)
        z1 = finales.get("z1", z1); z2 = finales.get("z2", z2)
        hA = float(finales.get("hA", hA) or 0.0); hR = float(finales.get("hR", hR) or 0.0)
        Q = resultado_solver.get("Q_m3s", Q)

    elif clase in ("Clase II-A", "Clase II-B", "Clase II-C"):
        Q = resultado_solver.get("Q_final", resultado_solver.get("Q", Q))

    elif clase == "Clase III-A":
        if len(tramos) != 1:
            return {"version": VERSION_DIAGRAMAS_V1415, "disponible": False, "motivo": "III-A gráfico requiere un tramo"}
        Dm = float(resultado_solver.get("D_mott", resultado_solver.get("D_minimo", 0.0)) or 0.0)
        if Dm <= 0:
            return {"version": VERSION_DIAGRAMAS_V1415, "disponible": False, "motivo": "D resuelto no disponible"}
        tramos[0]["D"] = Dm
        fila = _fila_resultado_unico_v1415(tramos[0], resultado_solver, D=Dm)
        sistema = {
            "resultados": [fila],
            "total_hf": float(resultado_solver.get("hf", 0.0) or 0.0),
            "total_hm_accesorios": 0.0,
            "total_hm_transiciones": 0.0,
            "total_hm": 0.0,
            "hL_total": float(resultado_solver.get("hf", 0.0) or 0.0),
            "transiciones_resultados": [],
        }
        Q = prefill.get("Q_m3s")
        tipo_v1 = "deposito"; tipo_v2 = "deposito"

    elif clase == "Clase III-B":
        if len(tramos) != 1:
            return {"version": VERSION_DIAGRAMAS_V1415, "disponible": False, "motivo": "III-B gráfico requiere un tramo"}
        fila = _fila_resultado_unico_v1415(tramos[0], resultado_solver)
        sistema = {
            "resultados": [fila],
            "total_hf": float(resultado_solver.get("hf", 0.0) or 0.0),
            "total_hm_accesorios": float(resultado_solver.get("hm", 0.0) or 0.0),
            "total_hm_transiciones": 0.0,
            "total_hm": float(resultado_solver.get("hm", 0.0) or 0.0),
            "hL_total": float(resultado_solver.get("hL", 0.0) or 0.0),
            "transiciones_resultados": [],
        }
        P2 = float(resultado_solver.get("P2_calculada", P2) or 0.0)
        Q = prefill.get("Q_m3s")

    if not sistema or not sistema.get("resultados"):
        return {"version": VERSION_DIAGRAMAS_V1415, "disponible": False, "motivo": "Resultados por tramo no disponibles"}
    if any(v is None for v in (P1, P2, z1, z2)):
        return {"version": VERSION_DIAGRAMAS_V1415, "disponible": False, "motivo": "Condiciones de frontera incompletas"}

    filas = sistema.get("resultados") or []
    V_t1 = float(filas[0].get("V (m/s)", 0.0) or 0.0)
    V_t2 = float(filas[-1].get("V (m/s)", 0.0) or 0.0)
    V1 = 0.0 if tipo_v1 == "deposito" else V_t1
    V2 = 0.0 if tipo_v2 == "deposito" else V_t2
    trans_calc = copy.deepcopy(sistema.get("transiciones_resultados") or [])

    total_L = sum(float(t.get("L", 0.0) or 0.0) for t in tramos)
    pb = prefill.get("posicion_bomba_m")
    pt = prefill.get("posicion_turbina_m")
    if pb is None and hA > 0 and total_L > 0: pb = 0.05 * total_L
    if pt is None and hR > 0 and total_L > 0: pt = 0.75 * total_L

    return {
        "version": VERSION_DIAGRAMAS_V1415,
        "disponible": True,
        "clase": clase,
        "Q_m3s": None if Q is None else float(Q),
        "gamma": gamma,
        "P1_pa": float(P1), "P2_pa": float(P2),
        "z1_m": float(z1), "z2_m": float(z2),
        "V1_ms": float(V1), "V2_ms": float(V2),
        "hA_m": float(hA), "hR_m": float(hR),
        "tipo_v1": tipo_v1, "tipo_v2": tipo_v2,
        "tramos": copy.deepcopy(tramos),
        "sistema": copy.deepcopy(sistema),
        "transiciones": trans_calc,
        "posicion_bomba_m": None if pb is None else float(pb),
        "posicion_turbina_m": None if pt is None else float(pt),
        "z_nodos_m": copy.deepcopy(prefill.get("z_nodos_m") or []),
    }


def resolver_flujo_confirmado(resultado: dict, enunciado: str, previsualizacion: dict,
                               firma_confirmada: str, manifiesto: dict | None = None) -> dict:
    """Ejecuta solver + auditoría + reporte solo después de confirmación V14.7 válida."""
    preview = copy.deepcopy(previsualizacion or {})
    if preview.get("version") != VERSION_TRANSFERENCIA:
        raise ErrorFlujoV1410("Se requiere una previsualización V14.7 válida.")
    if not preview.get("listo_para_transferir"):
        raise ErrorFlujoV1410("V14.7 no está listo para transferir.")
    if not confirmacion_corresponde(preview, firma_confirmada):
        raise ErrorFlujoV1410("La confirmación humana no corresponde al snapshot V14.7 actual.")

    base = copy.deepcopy(preview.get("resultado_consolidado") or resultado or {})
    confianza_v1411 = base.get("confianza_datos_v1411") or {}
    if confianza_v1411 and not confianza_v1411.get("listo_para_v147"):
        raise ErrorFlujoV1410("V14.11 conserva datos de confianza media/baja sin confirmar.")
    clase = str(base.get("clase") or "")
    prefill = base.get("prefill") or {}
    prop = _propiedades_fluido(prefill)
    rho, nu, gamma = prop["rho"], prop["nu"], prop["gamma"]
    trans = _transiciones(prefill)

    if manifiesto is None:
        manifiesto = construir_manifiesto_ejecucion(base, enunciado, preview)
    if manifiesto.get("version") != VERSION_REPORTE:
        raise ErrorFlujoV1410("El manifiesto trazable V14.9 no es válido.")

    if clase in ("Clase II-A", "Clase II-B", "Clase II-C"):
        tramos = construir_tramos_solver(prefill, clase)
        tipo_v1 = _tipo_velocidad(prefill, "v1_tipo", "tuberia")
        tipo_v2 = _tipo_velocidad(prefill, "v2_tipo", "tuberia")
        metodo = clase.replace("Clase ", "")
        P1_pa = _p_pa(prefill, "P1_kpa"); P2_pa = _p_pa(prefill, "P2_kpa")
        z1 = _valor(prefill, "z1_m"); z2 = _valor(prefill, "z2_m")
        hA = _valor(prefill, "hA_m", requerido=False, default=0.0) or 0.0
        hR = _valor(prefill, "hR_m", requerido=False, default=0.0) or 0.0
        solucion = resolver_clase_ii_mott_v9(
            metodo=metodo, tramos=tramos, nu=nu, gamma=gamma,
            P1=P1_pa, P2=P2_pa, z1=z1, z2=z2, hA=hA, hR=hR,
            tipo_v1=tipo_v1, tipo_v2=tipo_v2, transiciones=trans,
            V1_manual=0.0, V2_manual=0.0, modo_avanzado=False,
            estrategia_iia=prefill.get("metodo_solicitado_v1421"),
        )
        solucion = _refinar_clase_ii_si_necesario(
            solucion, metodo, tramos, nu, gamma, P1_pa, P2_pa, z1, z2, hA, hR,
            tipo_v1, tipo_v2, trans,
        )
        auditoria = auditar_clase_ii_mott(solucion)
        resultado_solver = solucion

    elif clase == "Clase I":
        tramos = construir_tramos_solver(prefill, clase)
        Q = _valor(prefill, "Q_m3s")
        sistema = calcular_sistema_con_transiciones(Q, tramos, nu, trans)
        tipo_v1 = _tipo_velocidad(prefill, "v1_tipo", "tuberia")
        tipo_v2 = _tipo_velocidad(prefill, "v2_tipo", "tuberia")
        V1 = 0.0 if tipo_v1 == "deposito" else float(sistema["resultados"][0]["V (m/s)"])
        V2 = 0.0 if tipo_v2 == "deposito" else float(sistema["resultados"][-1]["V (m/s)"])
        inc, etiqueta = _incognita_i(prefill)
        P1 = None if inc == "P1" else _p_pa(prefill, "P1_kpa")
        P2 = None if inc == "P2" else _p_pa(prefill, "P2_kpa")
        z1 = None if inc == "z1" else _valor(prefill, "z1_m")
        z2 = None if inc == "z2" else _valor(prefill, "z2_m")
        hA = None if inc == "hA" else (_valor(prefill, "hA_m", requerido=False, default=0.0) or 0.0)
        hR = None if inc == "hR" else (_valor(prefill, "hR_m", requerido=False, default=0.0) or 0.0)
        valor = resolver_clase_i(inc, P1, P2, z1, z2, V1, V2, hA, hR, sistema["hL_total"], gamma)
        finales = {"P1": P1, "P2": P2, "z1": z1, "z2": z2, "hA": hA, "hR": hR}
        finales[inc] = valor
        residual = residuo_energia(
            finales["P1"], finales["P2"], finales["z1"], finales["z2"], V1, V2,
            finales["hA"], finales["hR"], sistema["hL_total"], gamma,
        )
        resultado_solver = {
            "incognita": inc, "incognita_etiqueta": etiqueta, "valor": valor,
            "unidad": "Pa" if inc in ("P1", "P2") else "m", "residual": residual,
            "Q_m3s": Q, "sistema": sistema,
            "estado_final": copy.deepcopy(finales),
        }
        auditoria = auditar_sistema_hidraulico(sistema, Q_referencia=Q, residual=residual, convergencia=True)

    elif clase == "Clase III-A":
        tramos = construir_tramos_solver(prefill, clase)
        if len(tramos) != 1:
            raise ErrorFlujoV1410("La implementación actual de III-A automática requiere un solo tramo.")
        t = tramos[0]
        Q = _valor(prefill, "Q_m3s")
        P1_pa = _p_pa(prefill, "P1_kpa")
        P2_pa = _p_pa(prefill, "P2_kpa")
        z1 = _valor(prefill, "z1_m"); z2 = _valor(prefill, "z2_m")
        hA = _valor(prefill, "hA_m", requerido=False, default=0.0) or 0.0
        hR = _valor(prefill, "hR_m", requerido=False, default=0.0) or 0.0
        hL = P1_pa/gamma + z1 + hA - (P2_pa/gamma + z2 + hR)
        if hL <= 0:
            raise ErrorFlujoV1410("La carga disponible para III-A debe ser positiva.")
        catalogo = "Acero Schedule 40 — Mott Apéndice F" if t.get("material") in ("Acero comercial", "Acero comercial o soldado") else None
        resultado_solver = resolver_clase_iii_a_mott_v9(
            Q=Q, L=t["L"], epsilon=t["epsilon"], nu=nu, hL_permitida=hL,
            catalogo_comercial=catalogo, modo_avanzado=False,
        )
        auditoria = auditar_clase_iii_a(resultado_solver)

    elif clase == "Clase III-B":
        tramos = construir_tramos_solver(prefill, clase)
        if len(tramos) != 1:
            raise ErrorFlujoV1410("La implementación actual de III-B automática requiere un solo tramo.")
        t = tramos[0]
        tipo_v1 = _tipo_velocidad(prefill, "v1_tipo", "tuberia")
        tipo_v2 = _tipo_velocidad(prefill, "v2_tipo", "tuberia")
        resultado_solver = verificar_clase_iii_b(
            D_actual=t["D"], Q=_valor(prefill, "Q_m3s"), L=t["L"], epsilon=t["epsilon"], nu=nu,
            K=t["K"], gamma=gamma, P1=_p_pa(prefill, "P1_kpa"),
            P2_deseada=_p_pa(prefill, "P2_kpa"), z1=_valor(prefill, "z1_m"), z2=_valor(prefill, "z2_m"),
            hA=_valor(prefill, "hA_m", requerido=False, default=0.0) or 0.0,
            hR=_valor(prefill, "hR_m", requerido=False, default=0.0) or 0.0,
            tipo_v1=tipo_v1, tipo_v2=tipo_v2, V1_manual=0.0, V2_manual=0.0,
        )
        if "satisfactorio" not in resultado_solver:
            resultado_solver["satisfactorio"] = bool(resultado_solver.get("cumple"))
        auditoria = auditar_clase_iii_b(resultado_solver, P2_requerida_pa=_p_pa(prefill, "P2_kpa"))

    else:
        raise ErrorFlujoV1410(f"Clase no compatible con el flujo automático: {clase or '—'}")

    auditoria_fisica = auditar_fisica(
        base, resultado_solver, propiedades_fluido=prop, auditoria_matematica=auditoria
    )
    contexto_diagramas_v1415 = construir_contexto_diagramas_v1415(base, resultado_solver, prop)
    reporte = construir_reporte_final(manifiesto, resultado_solver, auditoria, auditoria_fisica)
    procedimiento_v1419 = construir_procedimiento_mott(
        clase=clase, resultado_solver=resultado_solver, manifiesto=manifiesto,
        propiedades_fluido=prop, contexto_diagramas=contexto_diagramas_v1415, auditoria=auditoria,
    )
    entrada = _entrada_actual(prefill, clase)
    pasos = construir_estado_flujo(base, enunciado, preview, firma_confirmada)["pasos"]

    estado_math = str(auditoria.get("estado") or "ERROR")
    estado_fis = str(auditoria_fisica.get("estado") or "REVISAR")
    if "ERROR" in (estado_math, estado_fis):
        estado_global = "ERROR"
    elif "REVISAR" in (estado_math, estado_fis):
        estado_global = "REVISAR"
    else:
        estado_global = "OK"

    for p in pasos:
        if p["id"] == "solver":
            p["estado"] = "OK"
        elif p["id"] == "auditoria":
            p["estado"] = estado_math
        elif p["id"] == "auditoria_fisica":
            p["estado"] = estado_fis
        elif p["id"] == "reporte":
            p["estado"] = estado_global

    return {
        "version": VERSION_FLUJO,
        # Compatibilidad histórica V14.10: ``estado`` conserva el significado
        # matemático de V14.8.3. V14.16 añade un estado integral separado para
        # no convertir una bandera heurística de diseño en fallo del solver.
        "estado": estado_math,
        "estado_integral": estado_global,
        "estado_fisico": estado_fis,
        "clase": clase,
        "firma_v147": preview.get("firma"),
        "firma_corta": preview.get("firma_corta"),
        "propiedades_fluido": prop,
        "resultado_solver": resultado_solver,
        "auditoria": auditoria,
        "auditoria_fisica_v1416": auditoria_fisica,
        "contexto_diagramas_v1415": contexto_diagramas_v1415,
        "procedimiento_v1419": procedimiento_v1419,
        "reporte_v149": reporte,
        "manifiesto_v149": copy.deepcopy(manifiesto),
        "entrada_actual": entrada,
        "pasos": pasos,
    }
