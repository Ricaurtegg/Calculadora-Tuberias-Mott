"""Auditoría independiente de resultados hidráulicos — V14.8.

No reemplaza ni modifica los solvers. Recalcula identidades básicas a partir de
los resultados ya obtenidos y comprueba coherencia interna:
- A = pi D²/4;
- Q = A V;
- Darcy-Weisbach por tramo;
- hm = K V²/(2g) cuando el tramo reporta K;
- sumas hf, hm y transiciones;
- hL total;
- residual de energía/convergencia cuando exista;
- coherencia básica de Clase III-A / III-B.
"""
from __future__ import annotations

import copy
import json
import math
from datetime import datetime, timezone

VERSION_AUDITORIA = "V14.8.3"
G = 9.81


def _finito(v):
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def _valor(d: dict, *claves):
    """Devuelve el primer valor no nulo disponible entre varios alias de esquema."""
    for clave in claves:
        if clave in d and d.get(clave) is not None:
            return d.get(clave)
    return None


def _normalizar_texto(s):
    import unicodedata
    txt = str(s or "").strip().lower()
    txt = unicodedata.normalize("NFD", txt)
    return "".join(c for c in txt if unicodedata.category(c) != "Mn")


def _rel_error(a, b, piso=1e-12):
    a = float(a); b = float(b)
    return abs(a-b) / max(abs(a), abs(b), piso)


def _check(nivel, codigo, mensaje, esperado=None, obtenido=None, error_rel=None):
    return {
        "nivel": nivel,
        "codigo": codigo,
        "mensaje": mensaje,
        "esperado": esperado,
        "obtenido": obtenido,
        "error_rel": error_rel,
    }


def _nivel_por_error(err, tol_ok=2e-6, tol_warn=2e-4):
    if err <= tol_ok:
        return "ok"
    if err <= tol_warn:
        return "warning"
    return "error"


def auditar_sistema_hidraulico(sistema: dict, Q_referencia=None, residual=None, convergencia=None) -> dict:
    """Audita un sistema sin depender de un único esquema de nombres.

    V14.8.1 acepta resultados históricos donde A y/o la etiqueta de régimen no
    se almacenaban explícitamente. En esos casos reconstruye A desde D y el
    régimen desde Re; la ausencia de un dato redundante no se considera error.
    """
    sistema = copy.deepcopy(sistema or {})
    filas = list(sistema.get("resultados") or [])
    checks = []
    errores_max = []

    if not filas:
        checks.append(_check("error", "SIN_RESULTADOS", "El sistema no contiene resultados por tramo."))
    else:
        for idx, r in enumerate(filas, 1):
            D = _valor(r, "D (m)", "D", "diametro_m", "diámetro_m", "diametro")
            A_reportada = _valor(r, "A (m2)", "A (m²)", "A", "area_m2", "área_m2", "area")
            V = _valor(r, "V (m/s)", "V", "velocidad_m_s", "velocidad")
            L = _valor(r, "L (m)", "L", "longitud_m", "longitud")
            f = _valor(r, "f Darcy", "f", "factor_friccion", "factor de fricción")
            hf = _valor(r, "hf (m)", "hf", "h_f", "perdida_friccion_m")
            hm = _valor(r, "hm (m)", "hm", "h_m", "perdidas_menores_m")
            K = _valor(r, "K", "K_total", "k_total")
            Re = _valor(r, "Re", "Reynolds", "reynolds")
            regimen = _valor(r, "regimen", "régimen", "Regimen", "Régimen")

            A_calc = None
            if _finito(D) and float(D) > 0:
                A_calc = math.pi * float(D)**2 / 4.0
                if _finito(A_reportada):
                    err = _rel_error(A_calc, A_reportada)
                    errores_max.append(err)
                    nivel = _nivel_por_error(err)
                    checks.append(_check(nivel, f"AREA_{idx}", f"Tramo {idx}: A = πD²/4.", A_calc, float(A_reportada), err))
                else:
                    # A es una variable derivada. Si el solver histórico no la
                    # expone, reconstruirla desde D es suficiente para auditar.
                    checks.append(_check(
                        "ok", f"AREA_{idx}",
                        f"Tramo {idx}: área reconstruida desde D porque el solver no la reportó explícitamente.",
                        A_calc, None, 0.0,
                    ))
            elif _finito(A_reportada) and float(A_reportada) > 0:
                checks.append(_check(
                    "warning", f"AREA_{idx}",
                    f"Tramo {idx}: existe A, pero falta D para verificar independientemente A = πD²/4.",
                    None, float(A_reportada), None,
                ))
            else:
                checks.append(_check("error", f"AREA_{idx}", f"Tramo {idx}: D/A no válidos para verificar el área."))

            # Para continuidad se prioriza el área reconstruida desde D. Así la
            # comprobación no depende del mismo A reportado por el solver.
            A_cont = A_calc if _finito(A_calc) else A_reportada
            if Q_referencia is not None and all(_finito(x) for x in (A_cont, V, Q_referencia)):
                Q_calc = float(A_cont) * float(V)
                err = _rel_error(Q_calc, Q_referencia)
                errores_max.append(err)
                nivel = _nivel_por_error(err)
                checks.append(_check(nivel, f"CONTINUIDAD_{idx}", f"Tramo {idx}: continuidad Q = A·V.", float(Q_referencia), Q_calc, err))
            elif Q_referencia is not None:
                checks.append(_check("error", f"CONTINUIDAD_{idx}", f"Tramo {idx}: datos insuficientes para verificar Q = A·V."))

            if all(_finito(x) for x in (f, L, D, V, hf)) and float(D) > 0:
                hf_calc = float(f) * float(L) / float(D) * float(V)**2 / (2.0 * G)
                err = _rel_error(hf_calc, hf)
                errores_max.append(err)
                nivel = _nivel_por_error(err)
                checks.append(_check(nivel, f"DARCY_{idx}", f"Tramo {idx}: Darcy–Weisbach consistente.", hf_calc, float(hf), err))
            else:
                checks.append(_check("error", f"DARCY_{idx}", f"Tramo {idx}: datos insuficientes para verificar Darcy–Weisbach."))

            if all(_finito(x) for x in (K, V, hm)) and float(K) >= 0:
                hm_calc = float(K) * float(V)**2 / (2.0 * G)
                err = _rel_error(hm_calc, hm)
                errores_max.append(err)
                nivel = _nivel_por_error(err)
                checks.append(_check(nivel, f"HM_{idx}", f"Tramo {idx}: pérdidas menores K·V²/(2g).", hm_calc, float(hm), err))

            if _finito(Re):
                Re_num = float(Re)
                if Re_num <= 2000:
                    esperado = "laminar"
                elif Re_num < 4000:
                    esperado = "transicion"
                else:
                    esperado = "turbulento"

                reg_norm = _normalizar_texto(regimen)
                if not reg_norm:
                    # El régimen es derivable de Re; su ausencia como etiqueta no
                    # invalida el cálculo ni merece una advertencia.
                    checks.append(_check(
                        "ok", f"REGIMEN_{idx}",
                        f"Tramo {idx}: régimen {esperado} determinado independientemente desde Re={Re_num:.0f}; el solver no reportó etiqueta.",
                    ))
                else:
                    if esperado == "laminar":
                        coincide = "lamin" in reg_norm
                    elif esperado == "transicion":
                        coincide = "trans" in reg_norm
                    else:
                        coincide = "turb" in reg_norm
                    checks.append(_check(
                        "ok" if coincide else "warning",
                        f"REGIMEN_{idx}",
                        f"Tramo {idx}: régimen reportado compatible con Reynolds." if coincide else f"Tramo {idx}: revise la etiqueta de régimen para Re={Re_num:.0f}.",
                    ))

    total_hf_calc = sum(float(_valor(r, "hf (m)", "hf", "h_f", "perdida_friccion_m") or 0.0) for r in filas)
    total_hm_calc = sum(float(_valor(r, "hm (m)", "hm", "h_m", "perdidas_menores_m") or 0.0) for r in filas)
    total_hf = _valor(sistema, "total_hf", "hf_total", "total_hf_m")
    total_hm_acc = _valor(sistema, "total_hm_accesorios", "total_hm", "hm_total", "total_hm_m")
    total_hm_trans = _valor(sistema, "total_hm_transiciones", "hm_transiciones", "total_hm_transiciones_m")
    if total_hm_trans is None:
        total_hm_trans = 0.0
    hL_total = _valor(sistema, "hL_total", "hL", "hl_total", "perdida_total_m")

    for codigo, etiqueta, calc, rep in (
        ("SUM_HF", "Σhf por tramos", total_hf_calc, total_hf),
        ("SUM_HM", "Σhm de accesorios", total_hm_calc, total_hm_acc),
    ):
        if _finito(rep):
            err = _rel_error(calc, rep)
            errores_max.append(err)
            checks.append(_check(_nivel_por_error(err), codigo, f"{etiqueta} consistente.", calc, float(rep), err))

    if all(_finito(x) for x in (total_hf, total_hm_acc, total_hm_trans, hL_total)):
        hL_calc = float(total_hf) + float(total_hm_acc) + float(total_hm_trans)
        err = _rel_error(hL_calc, hL_total)
        errores_max.append(err)
        checks.append(_check(_nivel_por_error(err), "SUM_HL", "hL,total = Σhf + Σhm accesorios + Σhm transiciones.", hL_calc, float(hL_total), err))

    if residual is not None:
        if _finito(residual):
            res = abs(float(residual))
            ref = max(abs(float(hL_total)) if _finito(hL_total) else 1.0, 1.0)
            rel = res / ref
            if res <= 1e-7 or rel <= 1e-9:
                nivel = "ok"
            elif res <= 1e-5 or rel <= 1e-7:
                nivel = "warning"
            else:
                nivel = "error"
            checks.append(_check(nivel, "RESIDUAL", "Residual de energía/convergencia.", 0.0, float(residual), rel))
        else:
            checks.append(_check("error", "RESIDUAL", "El residual no es finito."))

    if convergencia is not None:
        checks.append(_check("ok" if bool(convergencia) else "error", "CONVERGENCIA", "El solver reporta convergencia." if bool(convergencia) else "El solver no reporta convergencia."))

    n_error = sum(c["nivel"] == "error" for c in checks)
    n_warn = sum(c["nivel"] == "warning" for c in checks)
    estado = "ERROR" if n_error else ("REVISAR" if n_warn else "OK")

    return {
        "version": VERSION_AUDITORIA,
        "tipo": "sistema",
        "estado": estado,
        "checks": checks,
        "errores": n_error,
        "advertencias": n_warn,
        "comprobaciones": len(checks),
        "error_rel_max": max(errores_max) if errores_max else 0.0,
        "resumen": {
            "Q_referencia_m3s": Q_referencia,
            "total_hf_m": total_hf,
            "total_hm_accesorios_m": total_hm_acc,
            "total_hm_transiciones_m": total_hm_trans,
            "hL_total_m": hL_total,
            "residual_m": residual,
        },
    }



def auditar_clase_ii_mott(solucion: dict) -> dict:
    """Audita Clase II respetando el método principal de Mott.

    Para II-B/II-C (y II-A iterativa) se exige residual/convergencia como antes.
    Cuando II-A usa literalmente la Ec. (11-3), el resultado principal es una
    expresión explícita aproximada de Mott/Swamee-Jain; en ese caso se audita
    contra la verificación numérica independiente y se informa el cierre de
    energía sin exigir residual nulo como si fuera una raíz iterativa.
    """
    sol = copy.deepcopy(solucion or {})
    metodo = str(sol.get("metodo") or "").strip().upper()
    directo = sol.get("mott_directo") or {}
    principal = _normalizar_texto(sol.get("metodo_calculo_principal"))
    es_iia_directo = (
        metodo == "II-A"
        and bool(directo.get("aplicable"))
        and ("11-3" in principal or "solucion directa" in principal)
    )

    if not es_iia_directo:
        return auditar_sistema_hidraulico(
            sol.get("sistema") or {},
            Q_referencia=sol.get("Q_final", sol.get("Q")),
            residual=sol.get("residual"),
            convergencia=sol.get("convergencia", True),
        )

    # Comprobaciones internas del sistema (A, continuidad, Darcy, K y sumas)
    # siguen siendo idénticas. Solo cambia la interpretación del cierre de II-A.
    audit = auditar_sistema_hidraulico(
        sol.get("sistema") or {},
        Q_referencia=sol.get("Q_final", sol.get("Q")),
        residual=None,
        convergencia=None,
    )
    checks = list(audit.get("checks") or [])

    q_mott = sol.get("Q_final", sol.get("Q"))
    q_num = directo.get("Q_numerico_verificacion")
    if q_num is None:
        q_num = sol.get("Q_numerico_verificacion")

    if _finito(q_mott) and _finito(q_num) and float(q_num) != 0.0:
        err_q = _rel_error(q_mott, q_num)
        if err_q <= 0.01:          # misma regla que la interfaz histórica: <= 1 %
            nivel_q = "ok"
        elif err_q <= 0.03:
            nivel_q = "warning"
        else:
            nivel_q = "error"
        checks.append(_check(
            nivel_q, "IIA_MOTT_VS_NUMERICO",
            "II-A: Ec. (11-3) de Mott coherente con la verificación numérica independiente.",
            float(q_num), float(q_mott), err_q,
        ))
    else:
        checks.append(_check(
            "error", "IIA_MOTT_VS_NUMERICO",
            "II-A directo: falta la verificación numérica independiente del caudal de Mott.",
        ))

    residual = sol.get("residual")
    hL = _valor(sol.get("sistema") or {}, "hL_total", "hL", "hl_total", "perdida_total_m")
    if _finito(residual):
        ref = max(abs(float(hL)) if _finito(hL) else 1.0, 1.0)
        cierre_rel = abs(float(residual)) / ref
        if cierre_rel <= 0.01:
            nivel_r = "ok"
        elif cierre_rel <= 0.03:
            nivel_r = "warning"
        else:
            nivel_r = "error"
        checks.append(_check(
            nivel_r, "IIA_CIERRE_ENERGIA_DIRECTO",
            "II-A: cierre de energía de la solución explícita de Mott; no se exige residual iterativo nulo.",
            0.0, float(residual), cierre_rel,
        ))
    else:
        checks.append(_check(
            "warning", "IIA_CIERRE_ENERGIA_DIRECTO",
            "II-A directo: no se recibió residual para cuantificar el cierre de energía.",
        ))

    checks.append(_check(
        "ok", "IIA_METODO_DIRECTO",
        "II-A usa Mott Ec. (11-3) como método principal; la convergencia se valida por comparación numérica, no por iteraciones del resultado directo.",
    ))

    n_error = sum(c.get("nivel") == "error" for c in checks)
    n_warn = sum(c.get("nivel") == "warning" for c in checks)
    estado = "ERROR" if n_error else ("REVISAR" if n_warn else "OK")
    audit.update({
        "version": VERSION_AUDITORIA,
        "tipo": "Clase II-A — Mott directo",
        "estado": estado,
        "checks": checks,
        "errores": n_error,
        "advertencias": n_warn,
        "comprobaciones": len(checks),
    })
    resumen = dict(audit.get("resumen") or {})
    resumen.update({
        "metodo": "II-A",
        "metodo_principal": sol.get("metodo_calculo_principal"),
        "Q_mott_m3s": q_mott,
        "Q_numerico_verificacion_m3s": q_num,
        "residual_mott_directo_m": residual,
        "convergencia_iterativa_no_aplica": True,
    })
    audit["resumen"] = resumen
    return audit

def auditar_clase_iii_a(resultado: dict) -> dict:
    r = copy.deepcopy(resultado or {})
    checks = []
    for clave in ("D_mott", "D_numerico_verificacion", "V", "Re", "f", "hf"):
        val = r.get(clave)
        checks.append(_check("ok" if _finito(val) and float(val) > 0 else "error", f"IIIA_{clave}", f"III-A: {clave} es físico y positivo."))
    if _finito(r.get("residual")):
        res = abs(float(r["residual"]))
        checks.append(_check("ok" if res <= 1e-7 else "warning", "IIIA_RESIDUAL", "III-A: residual de verificación de D de Mott.", 0.0, r["residual"], res))
    if _finito(r.get("D_mott")) and _finito(r.get("D_numerico_verificacion")):
        err = _rel_error(r["D_mott"], r["D_numerico_verificacion"])
        checks.append(_check("ok" if err <= 0.05 else "warning", "IIIA_D_COMPARACION", "III-A: D de Mott y verificación numérica son coherentes.", r["D_numerico_verificacion"], r["D_mott"], err))
    n_error = sum(c["nivel"] == "error" for c in checks); n_warn = sum(c["nivel"] == "warning" for c in checks)
    return {"version": VERSION_AUDITORIA, "tipo": "III-A", "estado": "ERROR" if n_error else ("REVISAR" if n_warn else "OK"), "checks": checks, "errores": n_error, "advertencias": n_warn, "comprobaciones": len(checks), "resumen": {k:r.get(k) for k in ("D_mott","D_numerico_verificacion","V","Re","f","hf","residual")}}


def auditar_clase_iii_b(resultado: dict, P2_requerida_pa=None) -> dict:
    r = copy.deepcopy(resultado or {})
    checks = []
    for clave in ("V", "Re", "f", "hf", "hm", "hL", "P2_calculada"):
        val = r.get(clave)
        valido = _finito(val) and (float(val) >= 0 if clave not in ("P2_calculada",) else True)
        checks.append(_check("ok" if valido else "error", f"IIIB_{clave}", f"III-B: {clave} es numéricamente válido."))
    if all(_finito(r.get(k)) for k in ("hf", "hm", "hL")):
        calc = float(r["hf"]) + float(r["hm"])
        err = _rel_error(calc, r["hL"])
        checks.append(_check(_nivel_por_error(err), "IIIB_HL", "III-B: hL = hf + hm.", calc, r["hL"], err))
    if P2_requerida_pa is not None and _finito(P2_requerida_pa) and _finito(r.get("P2_calculada")):
        margen_calc = float(r["P2_calculada"]) - float(P2_requerida_pa)
        if _finito(r.get("margen_presion")):
            err = _rel_error(margen_calc, r["margen_presion"])
            checks.append(_check(_nivel_por_error(err), "IIIB_MARGEN", "III-B: margen de presión consistente.", margen_calc, r["margen_presion"], err))
        satis_calc = margen_calc >= -1e-9
        if "satisfactorio" in r:
            checks.append(_check("ok" if bool(r["satisfactorio"]) == satis_calc else "error", "IIIB_CUMPLE", "III-B: indicador de cumplimiento coherente con el margen."))
    n_error = sum(c["nivel"] == "error" for c in checks); n_warn = sum(c["nivel"] == "warning" for c in checks)
    return {"version": VERSION_AUDITORIA, "tipo": "III-B", "estado": "ERROR" if n_error else ("REVISAR" if n_warn else "OK"), "checks": checks, "errores": n_error, "advertencias": n_warn, "comprobaciones": len(checks), "resumen": {k:r.get(k) for k in ("V","Re","f","hf","hm","hL","P2_calculada","margen_presion","satisfactorio")}}


def reporte_texto(auditoria: dict, titulo="Auditoría V14.8") -> str:
    a = auditoria or {}
    lineas = [titulo, "=" * len(titulo), f"Versión: {a.get('version','—')}", f"Estado: {a.get('estado','—')}", f"Comprobaciones: {a.get('comprobaciones',0)}", f"Errores: {a.get('errores',0)}", f"Advertencias: {a.get('advertencias',0)}", "", "COMPROBACIONES"]
    for i, c in enumerate(a.get("checks") or [], 1):
        lineas.append(f"{i:02d}. [{str(c.get('nivel','')).upper()}] {c.get('codigo','')}: {c.get('mensaje','')}")
        if c.get("esperado") is not None or c.get("obtenido") is not None:
            lineas.append(f"    esperado={c.get('esperado')} | obtenido={c.get('obtenido')}")
        if c.get("error_rel") is not None:
            lineas.append(f"    error_rel={float(c['error_rel']):.6e}")
    return "\n".join(lineas) + "\n"


def reporte_json(auditoria: dict) -> str:
    payload = {"generado_utc": datetime.now(timezone.utc).isoformat(), "auditoria": auditoria}
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)
