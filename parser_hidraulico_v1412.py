"""Parser hidráulico robusto de notación y unidades — V14.12.

Objetivo
--------
Complementa el parser histórico sin sustituirlo. Reconoce formas frecuentes en
problemas reales y normaliza a SI antes de transferir al solver. Cada conversión
conserva el fragmento original y la interpretación aplicada para auditoría.

V14.12 NO adivina magnitudes ambiguas. En particular:
- NPS/DN solo se convierte a diámetro interior si también se conoce Schedule 40/80;
- una medida explícita de diámetro (p. ej. D=4\") se interpreta literalmente;
- propiedades de fluido explícitas se conservan, pero no se inventan las que falten.
"""
from __future__ import annotations

import copy
import math
import re
import unicodedata
from typing import Any

from catalogo_tuberias_mott import obtener_catalogo

VERSION_PARSER = "V14.12"
REVISION_PARSER = "V14.12.5"

# Mantiene el patrón relativamente conservador. La interpretación final se hace
# con _numero_ingenieril, que admite coma decimal, punto decimal, separadores de
# miles mezclados y notación científica.
_NUM = r"[+-]?(?:\d+(?:[\.,]\d+)?(?:[eE][+-]?\d+)?|\d+(?:[\.,]\d+)?\s*[x×*]\s*10\s*(?:\^|\*\*)?\s*[+-]?\d+)"


def _sin_acentos(texto: str) -> str:
    t = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _texto_busqueda(texto: str) -> str:
    t = _sin_acentos(texto).lower()
    t = t.replace("−", "-").replace("–", "-").replace("—", "-")
    t = t.replace("′", "'").replace("″", '"')
    return t


def _numero_ingenieril(raw: str) -> float:
    """Convierte números técnicos sin confundir coma decimal y notación ×10^n."""
    s = str(raw or "").strip().replace(" ", "")
    s = s.replace("−", "-").replace("–", "-").replace("—", "-")

    m = re.fullmatch(
        r"([+-]?(?:\d+(?:[\.,]\d+)?))\s*[x×*]\s*10\s*(?:\^|\*\*)?\s*([+-]?\d+)",
        s,
        flags=re.I,
    )
    if m:
        return _numero_ingenieril(m.group(1)) * (10.0 ** int(m.group(2)))

    # Separadores mezclados: el último separador actúa como decimal; los
    # anteriores se interpretan como agrupadores de miles.
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        # Una sola coma es decimal. Varias comas con grupos de tres son miles.
        if s.count(",") > 1 and re.fullmatch(r"[+-]?\d{1,3}(?:,\d{3})+", s):
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    elif s.count(".") > 1 and re.fullmatch(r"[+-]?\d{1,3}(?:\.\d{3})+", s):
        s = s.replace(".", "")

    return float(s)


def _finito(v: Any) -> bool:
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def _evento(tipo: str, original: str, valor_si: Any, unidad_si: str, detalle: str,
            posicion: int | None = None, **extra) -> dict:
    out = {
        "tipo": tipo,
        "original": str(original).strip(),
        "valor_si": valor_si,
        "unidad_si": unidad_si,
        "detalle": detalle,
    }
    if posicion is not None:
        out["posicion"] = int(posicion)
    out.update(extra)
    return out


# ---------------------------------------------------------------------------
# Conversiones
# ---------------------------------------------------------------------------

_LONG_FACT = {
    "m": 1.0, "metro": 1.0, "metros": 1.0,
    "cm": 0.01, "centimetro": 0.01, "centimetros": 0.01,
    "mm": 0.001, "milimetro": 0.001, "milimetros": 0.001,
    "ft": 0.3048, "foot": 0.3048, "feet": 0.3048, "pie": 0.3048, "pies": 0.3048, "'": 0.3048,
    "in": 0.0254, "inch": 0.0254, "inches": 0.0254,
    "pulg": 0.0254, "pulgada": 0.0254, "pulgadas": 0.0254, '"': 0.0254,
}


def _canon_unidad(u: str) -> str:
    u = _texto_busqueda(u).strip()
    u = re.sub(r"\s+", " ", u)
    return u


def convertir_longitud_v1412(valor: float, unidad: str) -> float:
    u = _canon_unidad(unidad)
    if u not in _LONG_FACT:
        raise ValueError(f"Unidad de longitud no reconocida por V14.12: {unidad}")
    return float(valor) * _LONG_FACT[u]


def convertir_caudal_v1412(valor: float, unidad: str) -> float:
    u = _canon_unidad(unidad)
    u = u.replace("³", "3").replace("^", "").replace(" ", "")
    mapa = {
        "m3/s": 1.0,
        "m3/min": 1.0 / 60.0,
        "m3/h": 1.0 / 3600.0,
        "l/s": 1e-3, "lps": 1e-3,
        "l/min": 1.0 / 60000.0,
        "l/h": 1.0 / 3_600_000.0,
        "gpm": 6.30901964e-5, "gal/min": 6.30901964e-5,
        "ft3/s": 0.028316846592, "cfs": 0.028316846592,
        "ft3/min": 0.028316846592 / 60.0,
        "pie3/s": 0.028316846592, "pies3/s": 0.028316846592,
        "pie3/min": 0.028316846592 / 60.0, "pies3/min": 0.028316846592 / 60.0,
    }
    if u not in mapa:
        raise ValueError(f"Unidad de caudal no reconocida por V14.12: {unidad}")
    return float(valor) * mapa[u]


def convertir_presion_v1412(valor: float, unidad: str) -> float:
    u = _canon_unidad(unidad).replace(" ", "")
    u = u.replace("²", "2").replace("^", "")
    factores = {
        "pa": 0.001,
        "kpa": 1.0, "kpag": 1.0,
        "mpa": 1000.0,
        "bar": 100.0, "mbar": 0.1,
        "psi": 6.894757293, "psig": 6.894757293, "psi(g)": 6.894757293,
        "lb/in2": 6.894757293, "lbf/in2": 6.894757293,
        "lb/pulg2": 6.894757293, "lbf/pulg2": 6.894757293,
        "lb/pulgada2": 6.894757293, "lbf/pulgada2": 6.894757293,
        "lb/pulgadas2": 6.894757293, "lbf/pulgadas2": 6.894757293,
        "kgf/cm2": 98.0665,
        "at": 98.0665,
    }
    if u not in factores:
        raise ValueError(f"Unidad de presión no reconocida por V14.12: {unidad}")
    return float(valor) * factores[u]


def convertir_carga_agua_a_kpa(valor: float, unidad: str) -> float:
    u = _canon_unidad(unidad).replace(" ", "")
    if u in {"fth2o", "ftdeagua", "ftagua", "piesdeagua", "piedeagua"}:
        return float(valor) * 0.3048 * 9.80665
    if u in {"inh2o", "indeagua", "pulgdeagua", "pulgadasdeagua"}:
        return float(valor) * 0.0254 * 9.80665
    if u in {"mh2o", "mdeagua", "mca", "m.c.a."}:
        return float(valor) * 9.80665
    raise ValueError(f"Unidad de columna de agua no reconocida: {unidad}")


def convertir_temperatura_c(valor: float, unidad: str) -> float:
    u = _canon_unidad(unidad).replace("°", "")
    if u in {"c", "degc"}:
        return float(valor)
    if u in {"f", "degf"}:
        return (float(valor) - 32.0) * 5.0 / 9.0
    if u in {"k", "kelvin"}:
        return float(valor) - 273.15
    raise ValueError(f"Unidad de temperatura no reconocida: {unidad}")


def convertir_nu_m2s(valor: float, unidad: str) -> float:
    u = _canon_unidad(unidad).replace("²", "2").replace("^", "").replace(" ", "")
    mapa = {
        "m2/s": 1.0,
        "ft2/s": 0.09290304,
        "cst": 1e-6, "centistoke": 1e-6, "centistokes": 1e-6,
        "st": 1e-4, "stoke": 1e-4, "stokes": 1e-4,
    }
    if u not in mapa:
        raise ValueError(f"Unidad de viscosidad cinemática no reconocida: {unidad}")
    return float(valor) * mapa[u]


def convertir_mu_pas(valor: float, unidad: str) -> float:
    u = _canon_unidad(unidad).replace("·", "*").replace(".", "*").replace(" ", "")
    mapa = {
        "pa*s": 1.0, "pas": 1.0,
        "mpa*s": 1e-3, "mpas": 1e-3,
        "cp": 1e-3, "centipoise": 1e-3, "centipoises": 1e-3,
        "p": 0.1, "poise": 0.1,
        "lbm/(ft*s)": 1.48816394357,
        "lbm/ft/s": 1.48816394357,
    }
    if u not in mapa:
        raise ValueError(f"Unidad de viscosidad dinámica no reconocida: {unidad}")
    return float(valor) * mapa[u]


def convertir_rho_kgm3(valor: float, unidad: str) -> float:
    u = _canon_unidad(unidad).replace("³", "3").replace("^", "").replace(" ", "")
    mapa = {
        "kg/m3": 1.0,
        "g/cm3": 1000.0,
        "lbm/ft3": 16.01846337396,
    }
    if u not in mapa:
        raise ValueError(f"Unidad de densidad no reconocida: {unidad}")
    return float(valor) * mapa[u]


# ---------------------------------------------------------------------------
# Extractores de magnitudes generales
# ---------------------------------------------------------------------------

_FLOW_UNIT = r"(?:m(?:\^?3|3|³)\s*/\s*(?:s|min|h)|l\s*/\s*(?:s|min|h)|lps|gpm|gal\s*/\s*min|ft(?:\^?3|3|³)\s*/\s*(?:s|min)|(?:pies|pie)(?:\^?3|3|³)\s*/\s*(?:s|min)|cfs)"
_PRESS_UNIT = r"(?:pa|kpa(?:g)?|mpa|bar|mbar|psi(?:g|\(g\))?|(?:lb|lbf)\s*/\s*(?:in|pulg(?:ada|adas)?)(?:\^?2|2|²)|kgf\s*/\s*cm(?:\^?2|2|²)|at)"
_HEAD_WATER_UNIT = r"(?:ft\s*(?:h2o|de\s+agua|agua)|(?:pie|pies)\s+de\s+agua|in\s*(?:h2o|de\s+agua)|pulg(?:ada|adas)?\s+de\s+agua|m\s*(?:h2o|de\s+agua)|m\.?\s*c\.?\s*a\.?)"
_LEN_UNIT = r"(?:mm|milimetros?|cm|centimetros?|m|metros?|ft|feet|foot|pies?|in|inches?|pulg(?:ada|adas)?|[\"'])"
_NU_UNIT = r"(?:m(?:\^?2|2|²)\s*/\s*s|ft(?:\^?2|2|²)\s*/\s*s|cst|centistokes?|stokes?|st)"
_MU_UNIT = r"(?:pa\s*[·.*]?\s*s|mpa\s*[·.*]?\s*s|cp|centipoise?s?|poise|p|lbm\s*/\s*\(\s*ft\s*[·.*]?\s*s\s*\)|lbm\s*/\s*ft\s*/\s*s)"
_RHO_UNIT = r"(?:kg\s*/\s*m(?:\^?3|3|³)|g\s*/\s*cm(?:\^?3|3|³)|lbm\s*/\s*ft(?:\^?3|3|³))"


def _buscar_variable(texto: str, nombres: list[str], unidad_patron: str, conversor, tipo: str,
                     unidad_si: str) -> tuple[float | None, dict | None]:
    tb = _texto_busqueda(texto)
    nregex = "|".join(nombres)
    patron = re.compile(
        rf"(?:{nregex})\s*(?:=|:|de|es)?\s*({_NUM})\s*({unidad_patron})",
        flags=re.I,
    )
    m = patron.search(tb)
    if not m:
        return None, None
    try:
        v = _numero_ingenieril(m.group(1))
        vsi = conversor(v, m.group(2))
    except Exception:
        return None, None
    return vsi, _evento(tipo, m.group(0), vsi, unidad_si, f"V14.12 normalizó {m.group(2).strip()} a {unidad_si}.", m.start())


def _buscar_caudal(texto: str):
    tb = _texto_busqueda(texto)
    patrones = [
        re.compile(rf"(?:\bq\b|caudal|flujo\s+volumetrico)\s*(?:=|:|de|es)?\s*({_NUM})\s*({_FLOW_UNIT})", re.I),
        re.compile(rf"({_NUM})\s*({_FLOW_UNIT})\b", re.I),
    ]
    for p in patrones:
        m = p.search(tb)
        if m:
            try:
                v = convertir_caudal_v1412(_numero_ingenieril(m.group(1)), m.group(2))
            except Exception:
                continue
            return v, _evento("caudal", m.group(0), v, "m³/s", "Caudal normalizado a SI por V14.12.", m.start())
    return None, None


def _buscar_presion(texto: str, numero: int):
    tb = _texto_busqueda(texto)
    letra = "a" if int(numero) == 1 else "b"
    nombres = [
        rf"p\s*{numero}\b", rf"p\s*{letra}\b",
        rf"presion\s+(?:en\s+)?(?:el\s+)?punto\s+{numero}\b",
        rf"presion\s+(?:en\s+)?(?:el\s+)?punto\s+{letra}\b",
        rf"presion\s+(?:en\s+)?{letra}\b",
    ]
    nregex = "|".join(nombres)
    p = re.compile(rf"(?:{nregex})\s*(?:(?:debe\s+ser\s+)?(?:de\s+)?(?:al\s+menos\s+)?|=|:|es\s+)?\s*({_NUM})\s*({_PRESS_UNIT})", re.I)
    m = p.search(tb)
    if m:
        try:
            v = convertir_presion_v1412(_numero_ingenieril(m.group(1)), m.group(2))
        except Exception:
            v = None
        if v is not None:
            return v, _evento(f"P{numero}", m.group(0), v, "kPa", "Presión normalizada a kPa por V14.12.", m.start())

    # También permite presión expresada como columna de agua.
    p2 = re.compile(rf"(?:{nregex})\s*(?:=|:|de|es)?\s*({_NUM})\s*({_HEAD_WATER_UNIT})", re.I)
    m = p2.search(tb)
    if m:
        try:
            v = convertir_carga_agua_a_kpa(_numero_ingenieril(m.group(1)), m.group(2))
        except Exception:
            return None, None
        return v, _evento(f"P{numero}", m.group(0), v, "kPa", "Columna de agua convertida a presión equivalente en kPa.", m.start())
    return None, None


def _buscar_longitud_variable(texto: str, nombres: list[str], tipo: str):
    return _buscar_variable(texto, nombres, _LEN_UNIT, convertir_longitud_v1412, tipo, "m")


def _buscar_temperatura(texto: str):
    tb = _texto_busqueda(texto)
    p = re.compile(rf"(?:temperatura|\bt\b)\s*(?:=|:|de|es)?\s*({_NUM})\s*(°?\s*(?:c|f|k|kelvin))\b", re.I)
    m = p.search(tb)
    if not m:
        # Compatibilidad con frases "agua a 68 °F".
        p = re.compile(rf"(?:agua|fluido)[^\.\n]{{0,35}}?\ba\s*({_NUM})\s*(°?\s*(?:c|f|k|kelvin))\b", re.I)
        m = p.search(tb)
    if not m:
        return None, None
    u = m.group(2).replace(" ", "")
    try:
        v = convertir_temperatura_c(_numero_ingenieril(m.group(1)), u)
    except Exception:
        return None, None
    return v, _evento("temperatura", m.group(0), v, "°C", "Temperatura normalizada a °C por V14.12.", m.start())


def _buscar_gravedad_especifica(texto: str):
    tb = _texto_busqueda(texto)
    p = re.compile(rf"(?:gravedad\s+especifica|densidad\s+relativa|specific\s+gravity|\bsg\b)\s*(?:=|:|de|es)?\s*({_NUM})", re.I)
    m = p.search(tb)
    if not m:
        return None, None
    try:
        sg = _numero_ingenieril(m.group(1))
    except Exception:
        return None, None
    if not (0.05 <= sg <= 30.0):
        return None, None
    return sg, _evento("gravedad_especifica", m.group(0), sg, "adimensional", "Gravedad específica explícita detectada por V14.12.3.", m.start())


def _buscar_caida_presion(texto: str):
    tb = _texto_busqueda(texto)
    patrones = [
        re.compile(rf"caida\s+de\s+presion\s+(?:maxima\s+)?(?:de|=|:)?\s*({_NUM})\s*({_PRESS_UNIT})", re.I),
        re.compile(rf"caida\s+(?:maxima\s+)?de\s+presion\s*(?:de|=|:)?\s*({_NUM})\s*({_PRESS_UNIT})", re.I),
        re.compile(rf"caida\s+(?:maxima\s+)?de\s+presion\s+de\s*({_NUM})\s*({_PRESS_UNIT})", re.I),
        re.compile(rf"p\s*1\s*-\s*p\s*2\s*(?:=|:)?\s*({_NUM})\s*({_PRESS_UNIT})", re.I),
        re.compile(rf"(?:diferencia|descenso)\s+de\s+presion\s*(?:=|:|de)?\s*({_NUM})\s*({_PRESS_UNIT})", re.I),
    ]
    for p in patrones:
        m = p.search(tb)
        if not m:
            continue
        try:
            val = convertir_presion_v1412(_numero_ingenieril(m.group(1)), m.group(2))
        except Exception:
            continue
        return val, _evento("deltaP_kpa", m.group(0), val, "kPa", "Caída/diferencia de presión normalizada a kPa por V14.12.3.", m.start())
    return None, None


def _buscar_relacion_elevacion_ab(texto: str):
    tb = _texto_busqueda(texto)
    # B está X por encima/abajo de A; A está X por encima/abajo de B.
    patrones = [
        (re.compile(rf"(?:punto\s+)?b\s+(?:esta|se\s+encuentra)?\s*({_NUM})\s*({_LEN_UNIT})\s+por\s+encima\s+de\s+(?:punto\s+)?a", re.I), 1),
        (re.compile(rf"(?:punto\s+)?b\s+(?:esta|se\s+encuentra)?\s*({_NUM})\s*({_LEN_UNIT})\s+por\s+debajo\s+de\s+(?:punto\s+)?a", re.I), -1),
    ]
    for p, signo in patrones:
        m=p.search(tb)
        if m:
            try: dz=convertir_longitud_v1412(_numero_ingenieril(m.group(1)),m.group(2))*signo
            except Exception: continue
            return (0.0,dz), _evento("delta_z_ab",m.group(0),dz,"m","Se adoptó zA=0 como referencia relativa y zB=zA+Δz.",m.start())
    return None, None


def _buscar_longitud_total_contextual(texto: str):
    tb=_texto_busqueda(texto)
    # Formas explícitas: "por cada 100 m de tubería", "tubería de 600 ft de longitud".
    pats=[
        re.compile(rf"por\s+cada\s*({_NUM})\s*({_LEN_UNIT})\s+de\s+(?:tuberia|tubo)",re.I),
        re.compile(rf"(?:tuberia|tubo)[^.\n]{{0,80}}?({_NUM})\s*({_LEN_UNIT})\s+de\s+longitud",re.I),
        re.compile(rf"({_NUM})\s*({_LEN_UNIT})\s+de\s+longitud",re.I),
    ]
    for p in pats:
        m=p.search(tb)
        if m:
            try: L=convertir_longitud_v1412(_numero_ingenieril(m.group(1)),m.group(2))
            except Exception: continue
            return L,_evento("longitud_total",m.group(0),L,"m","Longitud hidráulica total normalizada a metros.",m.start())

    # V14.12.5: una línea uniforme dibujada puede traer las longitudes solo como
    # cotas del croquis (p. ej. 30 m + 40 m + 30 m en Mott 11.3). No exigimos
    # literalmente "all pipes" si existe evidencia equivalente de un único
    # sistema/tamaño nominal y varias cotas de longitud.
    contexto_uniforme = bool(re.search(
        r"(?:todas\s+las\s+tuberias|all\s+pipes|sistema\s+de\s+tuberias\s+mostrado|"
        r"system\s+of\s+pipes\s+shown|piping\s+system|dn\s*\d+[^\n.]{0,40}(?:schedule|sch|cedula|calibre))",
        tb, re.I,
    ))
    if contexto_uniforme:
        vals=[]
        for m in re.finditer(rf"({_NUM})\s*({_LEN_UNIT})(?!\s*(?:\^?3|3|³)\s*/)",tb,re.I):
            entorno=tb[max(0,m.start()-12):min(len(tb),m.end()+12)]
            if re.search(r"(?:dn|diametro|presion|kpa|psi|elevacion|por\s+encima|por\s+debajo|z\s*[12ab]|"
                         r"gravedad\s+especifica|viscosidad|pa\.?s)", entorno):
                continue
            try: v=convertir_longitud_v1412(_numero_ingenieril(m.group(1)),m.group(2))
            except Exception: continue
            if v>1.0:
                vals.append((v,m.group(0),m.start()))
        # Para inferir una suma del croquis pedimos al menos dos cotas físicas.
        # Si el OCR solo recuperó una, se mantiene como dato faltante y V14.6 pregunta.
        if len(vals)>=2:
            total=sum(v for v,_,_ in vals)
            return total,_evento("longitud_total_segmentos"," + ".join(x[1] for x in vals),total,"m","Se sumaron longitudes consecutivas del mismo diámetro nominal a partir de las cotas del croquis.",vals[0][2])
    return None,None


def _buscar_propiedades(texto: str) -> tuple[dict, list[dict]]:
    tb = _texto_busqueda(texto)
    eventos = []
    props = {"sg": None, "rho_kg_m3": None, "nu_m2s": None, "mu_pa_s": None, "mu_ocr_ambigua": None}

    sg, ev_sg = _buscar_gravedad_especifica(texto)
    if sg is not None:
        props["sg"] = float(sg)
        props["rho_kg_m3"] = float(sg) * 1000.0
        if ev_sg: eventos.append(ev_sg)
        eventos.append(_evento("rho_kg_m3", "rho = SG×1000", props["rho_kg_m3"], "kg/m³", "V14.12.3 obtuvo ρ a partir de la gravedad específica explícita."))

    patrones = [
        ("rho_kg_m3", "densidad", [r"rho", r"ρ", r"densidad"], _RHO_UNIT, convertir_rho_kgm3, "kg/m³"),
        ("nu_m2s", "viscosidad cinemática", [r"nu", r"ν", r"viscosidad\s+cinematica"], _NU_UNIT, convertir_nu_m2s, "m²/s"),
        ("mu_pa_s", "viscosidad dinámica", [r"mu", r"μ", r"viscosidad\s+dinamica"], _MU_UNIT, convertir_mu_pas, "Pa·s"),
    ]
    for clave, tipo, nombres, up, conv, usi in patrones:
        nregex = "|".join(nombres)
        p = re.compile(rf"(?:{nregex})\s*(?:=|:|de|es)?\s*({_NUM})\s*({up})", re.I)
        m = p.search(tb)
        if not m:
            continue
        try:
            val = conv(_numero_ingenieril(m.group(1)), m.group(2))
        except Exception:
            continue
        props[clave] = val
        eventos.append(_evento(clave, m.group(0), val, usi, f"{tipo.title()} normalizada a SI por V14.12.", m.start()))

    # V14.12.4: Tesseract puede confundir el exponente superscrito de una
    # viscosidad, por ejemplo 9.5×10^-3 Pa·s -> 9.5 x 10° Pa.s. No se inventa
    # el exponente: se conserva como dato ambiguo para pedir únicamente μ.
    if props["mu_pa_s"] is None:
        p_amb = re.compile(
            rf"(?:mu|μ|viscosidad\s+dinamica)\s*(?:=|:|de|es)?\s*"
            rf"([+-]?\d+(?:[\.,]\d+)?)\s*[x×*]\s*10\s*[°ºo]\s*({_MU_UNIT})",
            re.I,
        )
        m_amb = p_amb.search(tb)
        if m_amb:
            props["mu_ocr_ambigua"] = {
                "original": m_amb.group(0),
                "coeficiente": _numero_ingenieril(m_amb.group(1)),
                "unidad": m_amb.group(2),
                "motivo": "El OCR no recuperó de forma fiable el exponente de la notación científica.",
            }
            eventos.append(_evento(
                "mu_ocr_ambigua", m_amb.group(0), None, "Pa·s",
                "V14.12.4 detectó una viscosidad dinámica con exponente OCR ambiguo; requiere confirmación y no se adivina el exponente.",
                m_amb.start(),
            ))

    # Si el enunciado entrega μ y ρ pero no ν, la relación ν=μ/ρ no es una
    # suposición: es la definición física de viscosidad cinemática.
    if props["nu_m2s"] is None and _finito(props["mu_pa_s"]) and _finito(props["rho_kg_m3"]) and float(props["rho_kg_m3"]) > 0:
        props["nu_m2s"] = float(props["mu_pa_s"]) / float(props["rho_kg_m3"])
        eventos.append(_evento(
            "nu_m2s", "ν = μ/ρ", props["nu_m2s"], "m²/s",
            "V14.12 calculó ν a partir de μ y ρ explícitamente proporcionadas.",
        ))
    return props, eventos


# ---------------------------------------------------------------------------
# Tramos, diámetros explícitos y tubería comercial NPS/DN
# ---------------------------------------------------------------------------


def _segmentos_tramos(texto: str) -> list[tuple[int, str, int]]:
    tb = _texto_busqueda(texto)
    marcas = list(re.finditer(r"\btramo\s*(\d+)\b", tb))
    if not marcas:
        return [(1, tb, 0)]
    out = []
    usados = set()
    for i, m in enumerate(marcas):
        n = int(m.group(1))
        if n in usados:
            continue
        fin = len(tb)
        for nxt in marcas[i+1:]:
            if int(nxt.group(1)) != n:
                fin = nxt.start(); break
        out.append((n, tb[m.start():fin], m.start()))
        usados.add(n)
    return out


def _buscar_medida_segmento(segmento: str, tipo: str):
    if tipo == "L":
        nombres = r"(?:longitud|largo|\bl\b)"
    else:
        nombres = r"(?:diametro(?:\s+(?:interno|interior))?|\bd\b)"
    p = re.compile(rf"{nombres}\s*(?:=|:|de|es)?\s*({_NUM})\s*({_LEN_UNIT})", re.I)
    m = p.search(segmento)
    if not m:
        # "100 mm de diámetro" / "68.5 m de longitud"
        suf = r"(?:diametro(?:\s+(?:interno|interior))?)" if tipo == "D" else r"(?:longitud|largo)"
        p = re.compile(rf"({_NUM})\s*({_LEN_UNIT})\s+de\s+{suf}", re.I)
        m = p.search(segmento)
    if not m:
        return None, None
    try:
        v = convertir_longitud_v1412(_numero_ingenieril(m.group(1)), m.group(2))
    except Exception:
        return None, None
    return v, m


def _schedule(segmento: str) -> int | None:
    m = re.search(r"\b(?:schedule|sch|cedula|calibre)\s*(40|80)\b", segmento, re.I)
    return int(m.group(1)) if m else None


def _normalizar_nps(raw: str) -> str:
    s = re.sub(r"\s+", " ", str(raw).strip())
    # 2-1/2 y 2 1/2 son equivalentes.
    s = re.sub(r"^(\d+)\s*[-]\s*(\d+/\d+)$", r"\1 \2", s)
    if re.fullmatch(r"\d+\.5", s):
        entero = int(float(s))
        s = f"{entero} 1/2"
    elif re.fullmatch(r"\d+\.25", s):
        entero = int(float(s)); s = f"{entero} 1/4"
    return s


def _buscar_fila_dn(schedule: int, dn: int) -> dict | None:
    cat = f"Acero Schedule {int(schedule)} — Mott Apéndice F"
    try:
        for fila in obtener_catalogo(cat):
            if int(fila["dn"]) == int(dn):
                return {**fila, "catalogo": cat, "schedule": int(schedule)}
    except Exception:
        return None
    return None


def _buscar_fila_nps(schedule: int, nps: str) -> dict | None:
    cat = f"Acero Schedule {int(schedule)} — Mott Apéndice F"
    nps = _normalizar_nps(nps)
    try:
        for fila in obtener_catalogo(cat):
            if str(fila["nps"]) == nps:
                return {**fila, "catalogo": cat, "schedule": int(schedule)}
    except Exception:
        return None
    return None


def _detectar_tuberia_nominal(segmento: str) -> tuple[dict | None, dict | None]:
    sch = _schedule(segmento)
    if sch is None:
        return None, None

    mdn = re.search(r"\bdn\s*[-:]?\s*(\d{1,3})\b", segmento, re.I)
    if mdn:
        fila = _buscar_fila_dn(sch, int(mdn.group(1)))
        if fila:
            ev = _evento(
                "diametro_comercial", mdn.group(0) + f" Schedule {sch}", fila["id_m"], "m",
                f"DN {fila['dn']} Schedule {sch} → diámetro interior real {fila['id_m']*1000:.1f} mm según catálogo Mott.",
                mdn.start(), nps=fila["nps"], dn=fila["dn"], schedule=sch, catalogo=fila["catalogo"],
            )
            return fila, ev

    mnps = re.search(r"\bnps\s*[-:]?\s*(\d+(?:\s+\d+/\d+|[-]\d+/\d+|/\d+|\.\d+)?)\s*(?:in|pulg(?:ada|adas)?|\")?", segmento, re.I)
    if mnps:
        fila = _buscar_fila_nps(sch, mnps.group(1))
        if fila:
            ev = _evento(
                "diametro_comercial", mnps.group(0) + f" Schedule {sch}", fila["id_m"], "m",
                f"NPS {fila['nps']} Schedule {sch} → diámetro interior real {fila['id_m']*1000:.1f} mm según catálogo Mott.",
                mnps.start(), nps=fila["nps"], dn=fila["dn"], schedule=sch, catalogo=fila["catalogo"],
            )
            return fila, ev

    # Forma común: "tubería de 4 pulgadas Schedule 40". Solo se interpreta
    # como NPS si aparece Schedule/Cédula en el mismo segmento.
    mpulg = re.search(r"(?:tuberia|tubo|pipe)[^\.\n]{0,35}?(" + _NUM + r")\s*(?:in|pulg(?:ada|adas)?|\")", segmento, re.I)
    if mpulg:
        try:
            raw = str(_numero_ingenieril(mpulg.group(1))).rstrip("0").rstrip(".")
            fila = _buscar_fila_nps(sch, raw)
        except Exception:
            fila = None
        if fila:
            ev = _evento(
                "diametro_comercial", mpulg.group(0) + f" Schedule {sch}", fila["id_m"], "m",
                f"Tamaño nominal {fila['nps']} in Schedule {sch} → diámetro interior real {fila['id_m']*1000:.1f} mm según catálogo Mott.",
                mpulg.start(), nps=fila["nps"], dn=fila["dn"], schedule=sch, catalogo=fila["catalogo"],
            )
            return fila, ev
    return None, None


def _buscar_epsilon(segmento: str):
    p = re.compile(rf"(?:epsilon|rugosidad(?:\s+absoluta)?|ε)\s*(?:=|:|de|es)?\s*({_NUM})\s*({_LEN_UNIT})", re.I)
    m = p.search(segmento)
    if not m:
        return None, None
    try:
        v = convertir_longitud_v1412(_numero_ingenieril(m.group(1)), m.group(2))
    except Exception:
        return None, None
    return v, m


def _extraer_tramos_v1412(texto: str) -> tuple[list[dict], list[dict], list[str]]:
    tramos = []
    eventos = []
    advertencias = []
    for n, seg, offset in _segmentos_tramos(texto):
        L, mL = _buscar_medida_segmento(seg, "L")
        Dexp, mD = _buscar_medida_segmento(seg, "D")
        fila, ev_nom = _detectar_tuberia_nominal(seg)
        eps, meps = _buscar_epsilon(seg)

        # Un diámetro explícito prevalece sobre un tamaño nominal si ambos se
        # indican como magnitudes hidráulicas. El nominal sigue registrándose.
        D = Dexp if Dexp is not None else (fila.get("id_m") if fila else None)
        item = {"numero": n, "L_m": L, "D_m": D}
        if fila:
            item["tuberia_comercial_v1412"] = {
                "nps": fila["nps"], "dn": fila["dn"], "schedule": fila["schedule"],
                "catalogo": fila["catalogo"], "id_m": fila["id_m"],
            }
        if eps is not None:
            item["epsilon_m"] = eps
        if any(v is not None for v in (L, D, eps)) or fila:
            tramos.append(item)

        if mL:
            eventos.append(_evento("longitud_tramo", mL.group(0), L, "m", f"Longitud del tramo {n} normalizada a metros.", offset + mL.start(), tramo=n))
        if mD:
            eventos.append(_evento("diametro_tramo", mD.group(0), Dexp, "m", f"Diámetro explícito del tramo {n} normalizado a metros.", offset + mD.start(), tramo=n))
        if ev_nom:
            ev_nom["tramo"] = n; ev_nom["posicion"] = offset + int(ev_nom.get("posicion", 0)); eventos.append(ev_nom)
            if Dexp is not None and abs(float(Dexp) - float(fila["id_m"])) > 0.01 * max(abs(float(Dexp)), abs(float(fila["id_m"])), 1e-9):
                advertencias.append(
                    f"Tramo {n}: se detectó diámetro explícito {Dexp*1000:.3g} mm y también NPS/DN Schedule con ID {fila['id_m']*1000:.3g} mm. V14.12 conserva el diámetro explícito y deja el nominal como trazabilidad."
                )
        if meps:
            eventos.append(_evento("rugosidad", meps.group(0), eps, "m", f"Rugosidad absoluta del tramo {n} normalizada a metros.", offset + meps.start(), tramo=n))
    return tramos, eventos, advertencias


# ---------------------------------------------------------------------------
# API pública y fusión conservadora
# ---------------------------------------------------------------------------


def analizar_enunciado_v1412(enunciado: str) -> dict:
    eventos = []
    advertencias = []
    escalares = {}

    q, ev = _buscar_caudal(enunciado); escalares["Q_m3s"] = q
    if ev: eventos.append(ev)
    dp, ev = _buscar_caida_presion(enunciado); escalares["deltaP_kpa"] = dp
    if ev: eventos.append(ev)
    for n in (1, 2):
        v, ev = _buscar_presion(enunciado, n); escalares[f"P{n}_kpa"] = v
        if ev: eventos.append(ev)
    for clave, nombres, tipo in (
        ("z1_m", [r"z\s*1\b", r"elevacion\s+(?:en\s+)?(?:el\s+)?punto\s+1\b"], "z1"),
        ("z2_m", [r"z\s*2\b", r"elevacion\s+(?:en\s+)?(?:el\s+)?punto\s+2\b"], "z2"),
        ("hA_m", [r"h\s*_?\s*a\b", r"carga\s+de\s+la\s+bomba"], "hA"),
        ("hR_m", [r"h\s*_?\s*r\b", r"carga\s+de\s+la\s+turbina", r"carga\s+retirada"], "hR"),
    ):
        v, ev = _buscar_longitud_variable(enunciado, nombres, tipo); escalares[clave] = v
        if ev: eventos.append(ev)

    temp, ev = _buscar_temperatura(enunciado); escalares["temperatura_c"] = temp
    if ev: eventos.append(ev)

    relz, ev = _buscar_relacion_elevacion_ab(enunciado)
    if relz:
        if escalares.get("z1_m") is None: escalares["z1_m"] = relz[0]
        if escalares.get("z2_m") is None: escalares["z2_m"] = relz[1]
        if ev: eventos.append(ev)

    props, evprops = _buscar_propiedades(enunciado); eventos.extend(evprops)
    tramos, evtr, advtr = _extraer_tramos_v1412(enunciado); eventos.extend(evtr); advertencias.extend(advtr)
    Lctx, evL = _buscar_longitud_total_contextual(enunciado)
    if Lctx is not None:
        if not tramos:
            tramos=[{"numero":1,"L_m":Lctx,"D_m":None}]
        elif len(tramos)==1 and (tramos[0].get("L_m") is None or (evL and evL.get("tipo")=="longitud_total_segmentos")):
            tramos[0]["L_m"]=Lctx
        if evL: eventos.append(evL)

    return {
        "version": VERSION_PARSER,
        "revision": REVISION_PARSER,
        "escalares": escalares,
        "propiedades_fluido": props,
        "tramos": tramos,
        "eventos": sorted(eventos, key=lambda x: int(x.get("posicion", 10**12))),
        "advertencias": advertencias,
    }


def _cerca(a, b, tol=1e-8):
    if not (_finito(a) and _finito(b)):
        return a == b
    aa, bb = float(a), float(b)
    return abs(aa - bb) <= tol * max(1.0, abs(aa), abs(bb))


def fusionar_prefill_v1412(prefill: dict, analisis: dict) -> dict:
    """Completa solo datos faltantes; nunca sobreescribe silenciosamente conflictos."""
    out = copy.deepcopy(prefill or {})
    a = analisis or {}
    adv = list(out.get("advertencias") or [])

    for clave, nuevo in (a.get("escalares") or {}).items():
        if nuevo is None:
            continue
        anterior = out.get(clave)
        if anterior is None:
            out[clave] = nuevo
        elif not _cerca(anterior, nuevo, tol=2e-6):
            adv.append(
                f"V14.12 detectó {clave}={nuevo:.8g} SI, distinto del valor ya interpretado {anterior:.8g}. Se conserva el valor previo y se requiere revisión."
            )

    # Tramos por número. V14.12 rellena notaciones que el parser histórico no
    # entendía, pero no reemplaza datos ya estructurados salvo coincidencia.
    actuales = list(out.get("tramos") or [])
    mapa = {int(t.get("numero", i+1) or i+1): t for i, t in enumerate(actuales)}
    for nt in a.get("tramos") or []:
        n = int(nt.get("numero", len(mapa)+1) or len(mapa)+1)
        if n not in mapa:
            nuevo_t = {"numero": n, "L_m": None, "D_m": None, "material": None, "accesorios": [], "curvas": [], "K_extra": None}
            actuales.append(nuevo_t); mapa[n] = nuevo_t
        cur = mapa[n]
        for clave in ("L_m", "D_m", "epsilon_m"):
            nuevo = nt.get(clave)
            if nuevo is None:
                continue
            ant = cur.get(clave)
            if ant is None:
                cur[clave] = nuevo
            elif not _cerca(ant, nuevo, tol=2e-6):
                adv.append(
                    f"V14.12 detectó {clave}={nuevo:.8g} m en tramo {n}, distinto del valor previo {ant:.8g} m. Se conserva el valor previo."
                )
        if nt.get("tuberia_comercial_v1412"):
            cur["tuberia_comercial_v1412"] = copy.deepcopy(nt["tuberia_comercial_v1412"])
            if not cur.get("material") and "Acero Schedule" in str(nt["tuberia_comercial_v1412"].get("catalogo", "")):
                cur["material"] = "Acero comercial o soldado"
        if nt.get("epsilon_m") is not None and not cur.get("material"):
            cur["material"] = "Personalizada"
    actuales.sort(key=lambda x: int(x.get("numero", 0) or 0))
    out["tramos"] = actuales

    props = a.get("propiedades_fluido") or {}
    sg = props.get("sg")
    rho = props.get("rho_kg_m3")
    nu = props.get("nu_m2s")
    mu = props.get("mu_pa_s")
    if sg is not None:
        out["sg_usuario"] = float(sg)
    if rho is not None:
        out["rho_usuario"] = float(rho)
    if nu is not None:
        out["nu_usuario_m2s"] = float(nu)
    if mu is not None:
        out["mu_usuario_pa_s"] = float(mu)
    if props.get("mu_ocr_ambigua"):
        out["mu_ocr_ambigua_v1412"] = copy.deepcopy(props["mu_ocr_ambigua"])
    if any(v is not None for v in (sg, rho, nu, mu)) or props.get("mu_ocr_ambigua"):
        out["propiedades_explicitas_v1412"] = True
        # Si no se reconoció el nombre del fluido pero sí se entregaron ρ y ν,
        # el problema ya tiene suficientes propiedades para tratarlo como personalizado.
        if not out.get("fluido_app") and _finito(rho) and _finito(nu):
            out["fluido_app"] = "Personalizado"
            if not out.get("fluido_detectado"):
                out["fluido_detectado"] = "Personalizado"

    out["normalizaciones_v1412"] = copy.deepcopy(a.get("eventos") or [])
    out["parser_v1412"] = {
        "version": a.get("version", VERSION_PARSER),
        "revision": a.get("revision", REVISION_PARSER),
        "cantidad_normalizaciones": len(a.get("eventos") or []),
    }
    adv.extend(a.get("advertencias") or [])
    out["advertencias"] = list(dict.fromkeys(str(x) for x in adv if str(x).strip()))
    return out
