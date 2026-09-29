"""V14.16 — Auditoría física ampliada para sistemas de tuberías.

Esta capa NO recalcula ni modifica la solución hidráulica. Complementa la
Auditoría matemática V14.8.3 con comprobaciones físicas/ingenieriles:
- velocidades extremas o llamativas;
- Reynolds en transición;
- geometría/rugosidad dimensionalmente sospechosa;
- gradientes de pérdida altos;
- presión absoluta imposible o próxima al vacío;
- proximidad a presión de vapor para agua cuando hay T suficiente;
- signos/magnitudes de bomba y turbina;
- advertencia de alcance NPSH/cavitación cuando no existen datos suficientes;
- alerta por fluidos del catálogo con posible comportamiento no newtoniano.

Los umbrales no se presentan como límites normativos universales. Se usan como
banderas de revisión conservadoras y quedan documentados en la salida.
"""
from __future__ import annotations

import copy
import json
import math
import re
import unicodedata
from typing import Any

from catalogos_mott import MATERIALES

VERSION_AUDITORIA_FISICA = "V14.16"
P_ATM_KPA = 101.325
G = 9.81


def _finito(v: Any) -> bool:
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def _norm(s: Any) -> str:
    txt = unicodedata.normalize("NFD", str(s or "").lower())
    return "".join(c for c in txt if unicodedata.category(c) != "Mn")


def _check(nivel: str, codigo: str, mensaje: str, *, valor=None, unidad=None,
           criterio=None, sugerencia=None, evaluable=True) -> dict:
    return {
        "nivel": nivel,
        "codigo": codigo,
        "mensaje": mensaje,
        "valor": valor,
        "unidad": unidad,
        "criterio": criterio,
        "sugerencia": sugerencia,
        "evaluable": bool(evaluable),
    }


def _prefill(contexto: dict | None) -> dict:
    c = contexto or {}
    return copy.deepcopy(c.get("prefill") or c.get("resultado_consolidado", {}).get("prefill") or c)


def _clase(contexto: dict | None, resultado: dict | None) -> str:
    c = contexto or {}
    return str(c.get("clase") or c.get("resultado_consolidado", {}).get("clase") or (resultado or {}).get("clase") or "")


def _material_epsilon(tramo: dict) -> float | None:
    eps = tramo.get("epsilon_m")
    if _finito(eps) and float(eps) >= 0:
        return float(eps)
    mat = tramo.get("material")
    if mat in MATERIALES and MATERIALES[mat] is not None:
        return float(MATERIALES[mat])
    return None


def _valor_fila(fila: dict, *claves):
    for k in claves:
        if k in fila and fila.get(k) is not None:
            return fila.get(k)
    return None


def _filas_hidraulicas(contexto: dict, resultado: dict) -> list[dict]:
    """Normaliza resultados por tramo para I/II/III-A/III-B."""
    pre = _prefill(contexto)
    clase = _clase(contexto, resultado)
    sistema = (resultado or {}).get("sistema") or {}
    filas = copy.deepcopy(sistema.get("resultados") or [])
    if filas:
        # Añade ε desde expediente si el motor histórico no lo reportó.
        trs = pre.get("tramos") or []
        for i, fila in enumerate(filas):
            if i < len(trs):
                fila.setdefault("epsilon_contexto_m", _material_epsilon(trs[i]))
        return filas

    trs = pre.get("tramos") or []
    if clase == "Clase III-A" and trs:
        t = trs[0]
        return [{
            "L (m)": t.get("L_m"), "D (m)": (resultado or {}).get("D_mott"),
            "epsilon_contexto_m": _material_epsilon(t),
            "V (m/s)": (resultado or {}).get("V"), "Re": (resultado or {}).get("Re"),
            "f Darcy": (resultado or {}).get("f"), "hf (m)": (resultado or {}).get("hf"),
            "hm (m)": 0.0,
        }]
    if clase == "Clase III-B" and trs:
        t = trs[0]
        return [{
            "L (m)": t.get("L_m"), "D (m)": t.get("D_m"),
            "epsilon_contexto_m": _material_epsilon(t),
            "V (m/s)": (resultado or {}).get("V"), "Re": (resultado or {}).get("Re"),
            "f Darcy": (resultado or {}).get("f"), "hf (m)": (resultado or {}).get("hf"),
            "hm (m)": (resultado or {}).get("hm"),
        }]
    return []


def _final_general(contexto: dict, resultado: dict, clave: str):
    """Obtiene el valor final de P1/P2/z/hA/hR respetando incógnitas Clase I."""
    pre = _prefill(contexto)
    mapa = {
        "P1_kpa": "P1", "P2_kpa": "P2", "z1_m": "z1", "z2_m": "z2",
        "hA_m": "hA", "hR_m": "hR",
    }
    inc = str((resultado or {}).get("incognita") or "")
    if mapa.get(clave) == inc and _finito((resultado or {}).get("valor")):
        val = float(resultado["valor"])
        return val / 1000.0 if clave in ("P1_kpa", "P2_kpa") else val
    if clave == "P2_kpa" and _clase(contexto, resultado) == "Clase III-B" and _finito((resultado or {}).get("P2_calculada")):
        return float(resultado["P2_calculada"]) / 1000.0
    return pre.get(clave)


def _temperatura_agua(contexto: dict, propiedades: dict | None) -> float | None:
    pre = _prefill(contexto)
    if _finito(pre.get("temperatura_c")):
        return float(pre["temperatura_c"])
    nombre = str((propiedades or {}).get("nombre") or pre.get("fluido_app") or pre.get("fluido_detectado") or "")
    m = re.search(r"agua\s+a\s+(-?\d+(?:[\.,]\d+)?)\s*°?c", _norm(nombre))
    if m:
        return float(m.group(1).replace(",", "."))
    return None


def presion_vapor_agua_kpa(temperatura_c: float) -> float | None:
    """Presión de vapor aproximada de agua 0–100 °C mediante Antoine.

    Solo se usa como bandera física, no como propiedad principal del solver.
    """
    if not _finito(temperatura_c):
        return None
    T = float(temperatura_c)
    if T < 0 or T > 100:
        return None
    # Antoine, P en mmHg; buena aproximación académica en este intervalo.
    A, B, C = 8.07131, 1730.63, 233.426
    p_mmhg = 10.0 ** (A - B / (C + T))
    return p_mmhg * 0.133322368


def _auditar_filas(filas: list[dict]) -> list[dict]:
    out = []
    for i, r in enumerate(filas, 1):
        V = _valor_fila(r, "V (m/s)", "V", "velocidad_m_s")
        Re = _valor_fila(r, "Re", "Reynolds")
        f = _valor_fila(r, "f Darcy", "f")
        D = _valor_fila(r, "D (m)", "D", "diametro_m")
        L = _valor_fila(r, "L (m)", "L", "longitud_m")
        hf = _valor_fila(r, "hf (m)", "hf")
        hm = _valor_fila(r, "hm (m)", "hm")
        eps = _valor_fila(r, "ε (m)", "epsilon (m)", "epsilon_m", "epsilon_contexto_m")
        rr = _valor_fila(r, "ε/D", "epsilon/D", "rugosidad_relativa")

        # Velocidad: solo los valores extraordinarios cambian el estado global.
        if not _finito(V) or float(V) <= 0:
            out.append(_check("error", f"VELOCIDAD_{i}", f"Tramo {i}: velocidad no física o no finita.", valor=V, unidad="m/s"))
        else:
            Vn = float(V)
            if Vn >= 15.0:
                out.append(_check("warning", f"VELOCIDAD_{i}", f"Tramo {i}: velocidad extraordinariamente alta ({Vn:.3g} m/s).", valor=Vn, unidad="m/s", criterio="≥15 m/s: bandera fuerte de revisión, no límite normativo", sugerencia="Revise diámetro, caudal y unidades; confirme que el problema realmente exige esta velocidad."))
            elif Vn >= 8.0:
                out.append(_check("warning", f"VELOCIDAD_{i}", f"Tramo {i}: velocidad muy alta ({Vn:.3g} m/s).", valor=Vn, unidad="m/s", criterio="≥8 m/s: revisión recomendada", sugerencia="Compruebe pérdidas, golpe de ariete/ruido si el problema es de diseño y no solo académico."))
            elif Vn >= 5.0:
                out.append(_check("info", f"VELOCIDAD_{i}", f"Tramo {i}: velocidad elevada pero físicamente plausible ({Vn:.3g} m/s).", valor=Vn, unidad="m/s", criterio="5–8 m/s: información"))
            elif Vn < 0.05:
                out.append(_check("info", f"VELOCIDAD_{i}", f"Tramo {i}: velocidad muy baja ({Vn:.3g} m/s).", valor=Vn, unidad="m/s"))
            else:
                out.append(_check("ok", f"VELOCIDAD_{i}", f"Tramo {i}: velocidad sin bandera física genérica.", valor=Vn, unidad="m/s"))

        # Reynolds.
        if not _finito(Re) or float(Re) <= 0:
            out.append(_check("error", f"REYNOLDS_{i}", f"Tramo {i}: Reynolds no físico o no finito.", valor=Re))
        else:
            Ren = float(Re)
            if 2000.0 < Ren < 4000.0:
                out.append(_check("warning", f"REYNOLDS_{i}", f"Tramo {i}: Re={Ren:.0f} está en transición; el factor de fricción puede ser sensible.", valor=Ren, criterio="2000 < Re < 4000"))
            else:
                out.append(_check("ok", f"REYNOLDS_{i}", f"Tramo {i}: Reynolds fuera de la zona de transición.", valor=Ren))

        # Diámetro y L/D.
        if not _finito(D) or float(D) <= 0:
            out.append(_check("error", f"DIAMETRO_{i}", f"Tramo {i}: diámetro no físico.", valor=D, unidad="m"))
        else:
            Dn = float(D)
            if Dn < 0.003 or Dn > 3.0:
                out.append(_check("warning", f"DIAMETRO_{i}", f"Tramo {i}: diámetro {Dn:.4g} m fuera del rango usual de los ejercicios de tuberías; revise unidades/contexto.", valor=Dn, unidad="m", criterio="<3 mm o >3 m: bandera de plausibilidad"))
            else:
                out.append(_check("ok", f"DIAMETRO_{i}", f"Tramo {i}: diámetro físicamente plausible.", valor=Dn, unidad="m"))
            if _finito(L) and float(L) > 0:
                ld = float(L) / Dn
                if ld < 5.0:
                    out.append(_check("warning", f"RELACION_LD_{i}", f"Tramo {i}: L/D={ld:.2f} es extremadamente corto para tratarlo como tramo desarrollado sin revisar efectos locales.", valor=ld, criterio="L/D < 5: revisar aplicabilidad de Darcy como tramo plenamente desarrollado"))
                elif ld < 20.0:
                    out.append(_check("info", f"RELACION_LD_{i}", f"Tramo {i}: L/D={ld:.1f} es corto; compruebe si las pérdidas locales dominan.", valor=ld))

        # Rugosidad relativa.
        if rr is None and _finito(eps) and _finito(D) and float(D) > 0:
            rr = float(eps) / float(D)
        if _finito(rr):
            rrn = float(rr)
            if rrn < 0:
                out.append(_check("error", f"RUGOSIDAD_REL_{i}", f"Tramo {i}: rugosidad relativa negativa.", valor=rrn))
            elif rrn > 0.05:
                out.append(_check("warning", f"RUGOSIDAD_REL_{i}", f"Tramo {i}: ε/D={rrn:.4g} es muy alta; revise material, diámetro y unidades de ε.", valor=rrn, criterio="ε/D > 0.05: plausibilidad"))
            else:
                out.append(_check("ok", f"RUGOSIDAD_REL_{i}", f"Tramo {i}: ε/D sin bandera de plausibilidad.", valor=rrn))

        # Factor de fricción: evita juzgar laminar con un umbral turbulento.
        if not _finito(f) or float(f) <= 0:
            out.append(_check("error", f"FACTOR_F_{i}", f"Tramo {i}: factor de fricción no físico.", valor=f))
        elif _finito(Re) and float(Re) > 4000 and float(f) > 0.10:
            out.append(_check("warning", f"FACTOR_F_{i}", f"Tramo {i}: f={float(f):.4g} es inusualmente alto para flujo turbulento; revise Re, ε/D y unidades.", valor=float(f)))

        # Gradiente de pérdidas distribuidas.
        if all(_finito(x) for x in (hf, L)) and float(L) > 0 and float(hf) >= 0:
            j = float(hf) / float(L)
            if j > 1.0:
                out.append(_check("warning", f"GRADIENTE_HF_{i}", f"Tramo {i}: hf/L={j:.3g} m/m es extraordinariamente alto.", valor=j, unidad="m/m", sugerencia="Revise diámetro, caudal, rugosidad y unidades."))
            elif j > 0.20:
                out.append(_check("info", f"GRADIENTE_HF_{i}", f"Tramo {i}: hf/L={j:.3g} m/m es elevado; puede ser correcto en tuberías pequeñas/caudales altos.", valor=j, unidad="m/m"))

        # Pérdida menor negativa sería imposible.
        if _finito(hm) and float(hm) < -1e-12:
            out.append(_check("error", f"HM_NEGATIVA_{i}", f"Tramo {i}: pérdidas menores negativas.", valor=float(hm), unidad="m"))
    return out


def _auditar_presiones(contexto: dict, resultado: dict, propiedades: dict | None) -> list[dict]:
    out = []
    pre = _prefill(contexto)
    fluido = str((propiedades or {}).get("nombre") or pre.get("fluido_app") or pre.get("fluido_detectado") or "")
    agua = _norm(fluido).startswith("agua") and "mar" not in _norm(fluido)
    T = _temperatura_agua(contexto, propiedades) if agua else None
    pvap = presion_vapor_agua_kpa(T) if T is not None else None

    if pre.get("presiones_relativas_desde_deltaP"):
        out.append(_check(
            "info", "PRESION_REFERENCIA_RELATIVA",
            "Las presiones P1/P2 fueron construidas únicamente como referencia relativa a partir de ΔP; V14.16 no las interpreta como presiones absolutas reales para vacío/cavitación.",
            evaluable=False,
        ))
        return out

    for punto, clave in ((1, "P1_kpa"), (2, "P2_kpa")):
        pg = _final_general(contexto, resultado, clave)
        if pg in (None, "INCÓGNITA") or not _finito(pg):
            continue
        pg = float(pg)
        pabs = pg + P_ATM_KPA
        if pabs <= 0:
            out.append(_check("error", f"PABS_{punto}", f"Punto {punto}: Pabs={pabs:.3g} kPa sería ≤0, físicamente imposible.", valor=pabs, unidad="kPa abs", sugerencia="Revise si la presión fue introducida como manométrica/absoluta y sus unidades."))
            continue
        if pabs < 5.0:
            out.append(_check("warning", f"PABS_{punto}", f"Punto {punto}: presión absoluta extremadamente baja ({pabs:.3g} kPa).", valor=pabs, unidad="kPa abs", criterio="Pabs < 5 kPa: proximidad al vacío"))
        else:
            out.append(_check("ok", f"PABS_{punto}", f"Punto {punto}: presión absoluta positiva.", valor=pabs, unidad="kPa abs"))

        if agua and _finito(pvap):
            margen = pabs - float(pvap)
            if margen <= 0:
                out.append(_check("error", f"VAPOR_AGUA_{punto}", f"Punto {punto}: Pabs={pabs:.3g} kPa ≤ Pvap≈{float(pvap):.3g} kPa a {T:.1f} °C; el estado líquido sería inconsistente/cercano a vaporización.", valor=margen, unidad="kPa de margen"))
            elif margen < 5.0:
                out.append(_check("warning", f"VAPOR_AGUA_{punto}", f"Punto {punto}: margen sobre presión de vapor ≈{margen:.3g} kPa, muy pequeño.", valor=margen, unidad="kPa", sugerencia="Si existe una bomba o punto alto, evalúe NPSH y presión local con la geometría real."))
            else:
                out.append(_check("ok", f"VAPOR_AGUA_{punto}", f"Punto {punto}: presión absoluta por encima de la presión de vapor del agua con margen amplio.", valor=margen, unidad="kPa"))
    return out


def _auditar_equipos(contexto: dict, resultado: dict, propiedades: dict | None) -> list[dict]:
    out = []
    pre = _prefill(contexto)
    hA = _final_general(contexto, resultado, "hA_m")
    hR = _final_general(contexto, resultado, "hR_m")
    for clave, val, nombre in (("HA", hA, "bomba"), ("HR", hR, "turbina")):
        if val is None or not _finito(val):
            continue
        v = float(val)
        if v < -1e-12:
            out.append(_check("error", f"{clave}_SIGNO", f"La carga de {nombre} resultó negativa ({v:.4g} m) con la convención actual.", valor=v, unidad="m", sugerencia="Revise si el equipo fue clasificado como bomba/turbina o si el signo se introdujo al revés."))
        elif v > 500.0:
            out.append(_check("warning", f"{clave}_MAGNITUD", f"La carga de {nombre} es muy grande ({v:.4g} m); revise unidades y contexto.", valor=v, unidad="m"))
        else:
            out.append(_check("ok", f"{clave}_SIGNO", f"Carga de {nombre} compatible con la convención de signos.", valor=v, unidad="m"))

    if _finito(hA) and float(hA) > 0:
        out.append(_check(
            "info", "NPSH_ALCANCE",
            "Existe una bomba, pero V14.16 no declara NPSH disponible sin una presión/elevación de succión local y las pérdidas entre el depósito/punto de referencia y la entrada de la bomba.",
            criterio="NPSHa requiere geometría y presión local de succión",
            sugerencia="Cuando esos datos estén explícitos, una versión futura puede calcular NPSHa y compararlo con NPSHr del fabricante.",
            evaluable=False,
        ))
    return out


def _auditar_modelo_fluido(contexto: dict, propiedades: dict | None) -> list[dict]:
    pre = _prefill(contexto)
    nombre = str((propiedades or {}).get("nombre") or pre.get("fluido_app") or pre.get("fluido_detectado") or "")
    n = _norm(nombre)
    sensibles = ("miel", "ketchup", "mantequilla de mani", "sangre")
    if any(x in n for x in sensibles):
        return [_check(
            "warning", "FLUIDO_MODELO_NEWTONIANO",
            f"El fluido '{nombre}' puede presentar comportamiento no newtoniano o propiedades muy dependientes de composición/temperatura; Darcy/Colebrook usa una viscosidad representativa constante.",
            sugerencia="Use este resultado solo si el enunciado autoriza tratar el fluido como newtoniano con la viscosidad indicada.",
        )]
    return []


def _auditar_balance_perdidas(resultado: dict) -> list[dict]:
    sistema = (resultado or {}).get("sistema") or {}
    hf = sistema.get("total_hf")
    hm = sistema.get("total_hm_accesorios", sistema.get("total_hm"))
    ht = sistema.get("total_hm_transiciones", 0.0)
    hL = sistema.get("hL_total")
    if not all(_finito(x) for x in (hf, hm, ht, hL)) or float(hL) <= 0:
        # III-B usa esquema plano.
        hf = (resultado or {}).get("hf")
        hm = (resultado or {}).get("hm")
        hL = (resultado or {}).get("hL")
        ht = 0.0
    if all(_finito(x) for x in (hf, hm, ht, hL)) and float(hL) > 0:
        menores = float(hm) + float(ht)
        frac = menores / float(hL)
        if frac > 0.90:
            return [_check("info", "DOMINIO_PERDIDAS_MENORES", f"Las pérdidas menores/transiciones representan {100*frac:.1f}% de hL; el sistema está dominado por accesorios/transiciones.", valor=frac, unidad="fracción")]
    return []


def auditar_fisica(contexto: dict, resultado_solver: dict, propiedades_fluido: dict | None = None,
                   auditoria_matematica: dict | None = None) -> dict:
    """Construye la auditoría física V14.16 sin modificar el solver."""
    contexto = copy.deepcopy(contexto or {})
    resultado = copy.deepcopy(resultado_solver or {})
    filas = _filas_hidraulicas(contexto, resultado)
    checks: list[dict] = []

    if auditoria_matematica and str(auditoria_matematica.get("estado")) == "ERROR":
        checks.append(_check(
            "warning", "BASE_MATEMATICA_EN_ERROR",
            "La auditoría matemática V14.8.3 está en ERROR; las banderas físicas se muestran, pero la interpretación final no debe usarse hasta corregir esa inconsistencia.",
            evaluable=False,
        ))

    if not filas:
        checks.append(_check("warning", "SIN_FILAS_FISICAS", "No hay resultados por tramo suficientes para evaluar velocidades/Re/gradientes físicamente.", evaluable=False))
    else:
        checks.extend(_auditar_filas(filas))

    checks.extend(_auditar_presiones(contexto, resultado, propiedades_fluido))
    checks.extend(_auditar_equipos(contexto, resultado, propiedades_fluido))
    checks.extend(_auditar_modelo_fluido(contexto, propiedades_fluido))
    checks.extend(_auditar_balance_perdidas(resultado))

    # Clase II-A: si hay menores configuradas, recuerda el alcance del método directo.
    clase = _clase(contexto, resultado)
    if clase == "Clase II-A":
        pre = _prefill(contexto)
        hay_acc = any((t.get("accesorios") or t.get("K_extra")) for t in pre.get("tramos") or [])
        hay_trans = any("sin" not in _norm(x.get("tipo")) for x in pre.get("transiciones") or [] if x.get("tipo"))
        if hay_acc or hay_trans:
            checks.append(_check(
                "warning", "IIA_ALCANCE_MENORES",
                "Clase II-A tiene accesorios/transiciones configurados; recuerde que el método directo de Mott II-A desprecia pérdidas menores en su formulación principal.",
                sugerencia="Si el enunciado exige incluirlas, use II-B/II-C según corresponda.",
            ))

    errores = sum(c.get("nivel") == "error" for c in checks)
    advertencias = sum(c.get("nivel") == "warning" for c in checks)
    infos = sum(c.get("nivel") == "info" for c in checks)
    oks = sum(c.get("nivel") == "ok" for c in checks)
    estado = "ERROR" if errores else ("REVISAR" if advertencias else "OK")

    return {
        "version": VERSION_AUDITORIA_FISICA,
        "estado": estado,
        "clase": clase,
        "checks": checks,
        "errores": errores,
        "advertencias": advertencias,
        "informativos": infos,
        "ok": oks,
        "comprobaciones": len(checks),
        "criterios": {
            "velocidad_info_m_s": 5.0,
            "velocidad_revision_m_s": 8.0,
            "velocidad_revision_fuerte_m_s": 15.0,
            "re_transicion": [2000.0, 4000.0],
            "rugosidad_relativa_revision": 0.05,
            "gradiente_hf_info_m_m": 0.20,
            "gradiente_hf_revision_m_m": 1.0,
            "presion_absoluta_atm_referencia_kpa": P_ATM_KPA,
            "nota": "Umbrales de plausibilidad/revisión; no sustituyen un código de diseño ni los criterios específicos del problema.",
        },
    }


def reporte_texto(auditoria: dict, titulo: str = "Auditoría física V14.16") -> str:
    a = auditoria or {}
    lineas = [
        titulo, "=" * len(titulo),
        f"Versión: {a.get('version','—')}", f"Estado: {a.get('estado','—')}",
        f"Errores: {a.get('errores',0)}", f"Advertencias: {a.get('advertencias',0)}",
        f"Informativos: {a.get('informativos',0)}", "", "COMPROBACIONES",
    ]
    for i, c in enumerate(a.get("checks") or [], 1):
        lineas.append(f"{i:02d}. [{str(c.get('nivel','')).upper()}] {c.get('codigo','')}: {c.get('mensaje','')}")
        if c.get("valor") is not None:
            lineas.append(f"    valor={c.get('valor')} {c.get('unidad') or ''}".rstrip())
        if c.get("criterio"):
            lineas.append(f"    criterio={c.get('criterio')}")
        if c.get("sugerencia"):
            lineas.append(f"    sugerencia={c.get('sugerencia')}")
    return "\n".join(lineas) + "\n"


def reporte_json(auditoria: dict) -> str:
    return json.dumps({"version": VERSION_AUDITORIA_FISICA, "auditoria": auditoria or {}}, ensure_ascii=False, indent=2, default=str)
