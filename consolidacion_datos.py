"""Consolidación estructurada de datos para problemas de tuberías en serie — V14.5.

Esta capa trabaja *después* del clasificador V14.x y de la fusión opcional de
figura/geometría. No resuelve el problema hidráulico ni modifica los solvers.
Su misión es construir un expediente único del problema y separar claramente:

- datos ya disponibles;
- inferencias físicamente seguras y trazables;
- incógnitas deliberadas del enunciado;
- datos realmente faltantes que el usuario debe completar;
- conflictos que deben bloquear una automatización ciega.

Principios de seguridad:
- nunca inventa L, D, material, Q, cotas o presiones;
- puede fijar P=0 kPa manométricos cuando un extremo está inequívocamente
  abierto a la atmósfera y no existe contradicción;
- puede asumir hA=0 / hR=0 únicamente cuando no hay evidencia textual de
  bomba/turbina y esas cargas no son la incógnita de Clase I;
- Q en Clase II y D en Clase III-A se registran como incógnitas, no faltantes.
"""

from __future__ import annotations

import copy
import re
import unicodedata

from auditoria_datos import construir_auditoria_datos, hay_conflictos_bloqueantes
from vfisicas import detectar_atmosfera_y_conflictos, hay_bloqueantes


VERSION_EXPEDIENTE = "V14.5"


_MAPA_INCOGNITA_I = {
    "Presión P2": "P2_kpa",
    "Presión P1": "P1_kpa",
    "Carga agregada por bomba hA": "hA_m",
    "Carga retirada hR": "hR_m",
    "Elevación z2": "z2_m",
    "Elevación z1": "z1_m",
}


_ETIQUETAS = {
    "Q_m3s": ("Caudal Q", "m³/s"),
    "P1_kpa": ("Presión P1", "kPa"),
    "P2_kpa": ("Presión P2", "kPa"),
    "z1_m": ("Elevación z1", "m"),
    "z2_m": ("Elevación z2", "m"),
    "hA_m": ("Carga agregada por bomba hA", "m"),
    "hR_m": ("Carga retirada por turbina hR", "m"),
}


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFD", str(texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip()


def _valor_presente(v) -> bool:
    return v is not None and not (isinstance(v, str) and not v.strip())


def _pregunta(clave, etiqueta, motivo, *, tipo="numero", unidad=None, tramo=None, opciones=None):
    d = {
        "clave": clave,
        "etiqueta": etiqueta,
        "pregunta": f"Indique {etiqueta}.",
        "motivo": motivo,
        "tipo": tipo,
        "unidad": unidad,
        "bloqueante": True,
    }
    if tramo is not None:
        d["tramo"] = int(tramo)
    if opciones:
        d["opciones"] = list(opciones)
    return d


def _agregar_faltante(faltantes, item):
    identidad = (item.get("clave"), item.get("tramo"), item.get("etiqueta"))
    existentes = {
        (x.get("clave"), x.get("tramo"), x.get("etiqueta"))
        for x in faltantes
    }
    if identidad not in existentes:
        faltantes.append(item)


def _inferir_atmosfera(prefill: dict, enunciado: str, inferencias: list[dict]):
    diags = detectar_atmosfera_y_conflictos(enunciado, prefill)
    if hay_bloqueantes(diags):
        return diags

    codigos = {str(d.get("codigo", "")) for d in diags}
    t = _norm(enunciado)

    # V14.5 añade la notación A/B muy usada en problemas de libro. Se exige que
    # la misma cláusula contenga el identificador del depósito y la condición
    # atmosférica, evitando inferencias globales ambiguas.
    abiertos_ab = set()
    for punto, letra in ((1, "a"), (2, "b")):
        ref = rf"(?:deposito|reservorio|tanque)\s*(?:{letra}|{punto})"
        ref_inv = rf"(?:deposito|reservorio|tanque)\s+(?:{letra}|{punto})"
        abierto = r"(?:abiert[oa](?:\s+a\s+la\s+atmosfera)?|a\s+la\s+atmosfera|atmosferic[oa])"
        if re.search(rf"{ref}[^.;\n]{{0,55}}{abierto}", t) or re.search(
            rf"{abierto}[^.;\n]{{0,55}}{ref_inv}", t
        ) or re.search(
            rf"(?:deposito|reservorio|tanque)\s+{abierto}\s*(?:{letra}|{punto})", t
        ):
            abiertos_ab.add(punto)

    for punto in (1, 2):
        clave = f"P{punto}_kpa"
        codigo = f"P{punto}_ATMOSFERA"
        if (codigo in codigos or punto in abiertos_ab) and prefill.get(clave) is None:
            prefill[clave] = 0.0
            inferencias.append({
                "clave": clave,
                "valor": 0.0,
                "unidad": "kPa",
                "fuente": "condición atmosférica",
                "detalle": (
                    f"El extremo {punto} fue identificado inequívocamente como abierto a la "
                    "atmósfera; se adopta P manométrica = 0 kPa."
                ),
                "confianza": "alta",
            })
    return diags


def _inferir_maquinas(prefill: dict, enunciado: str, clase: str | None, inferencias: list[dict]):
    t = _norm(enunciado)
    inc = prefill.get("incognita_clase_i") if clase == "Clase I" else None
    clave_inc = _MAPA_INCOGNITA_I.get(inc)

    evidencia_bomba = bool(re.search(r"\b(bomba|pump)\b", t))
    evidencia_turbina = bool(re.search(r"\b(turbina|turbine)\b", t))

    if prefill.get("hA_m") is None and clave_inc != "hA_m" and not evidencia_bomba:
        prefill["hA_m"] = 0.0
        inferencias.append({
            "clave": "hA_m", "valor": 0.0, "unidad": "m",
            "fuente": "ausencia de equipo",
            "detalle": "No se detectó bomba ni carga agregada en el enunciado; se toma hA=0 m.",
            "confianza": "alta",
        })

    if prefill.get("hR_m") is None and clave_inc != "hR_m" and not evidencia_turbina:
        prefill["hR_m"] = 0.0
        inferencias.append({
            "clave": "hR_m", "valor": 0.0, "unidad": "m",
            "fuente": "ausencia de equipo",
            "detalle": "No se detectó turbina ni carga retirada en el enunciado; se toma hR=0 m.",
            "confianza": "alta",
        })


def _incognitas_del_problema(clase: str | None, prefill: dict) -> list[dict]:
    out = []
    if clase in {"Clase II-A", "Clase II-B", "Clase II-C"}:
        out.append({"clave": "Q_m3s", "etiqueta": "Caudal Q", "detalle": "Incógnita propia de Clase II."})
    elif clase == "Clase III-A":
        out.append({"clave": "D_m", "etiqueta": "Diámetro requerido", "detalle": "Incógnita propia de Clase III-A."})
    elif clase == "Clase I":
        inc = prefill.get("incognita_clase_i")
        clave = _MAPA_INCOGNITA_I.get(inc)
        if clave:
            out.append({"clave": clave, "etiqueta": inc, "detalle": "Incógnita seleccionada para Clase I."})
    return out


def _agregar_requisitos_escalares(clase, prefill, faltantes):
    if clase == "Clase I":
        inc = prefill.get("incognita_clase_i")
        if not inc:
            _agregar_faltante(faltantes, _pregunta(
                "incognita_clase_i",
                "qué variable desea calcular en Clase I",
                "La Clase I necesita una incógnita explícita para no tratarla como dato faltante.",
                tipo="seleccion",
                opciones=list(_MAPA_INCOGNITA_I),
            ))
            clave_inc = None
        else:
            clave_inc = _MAPA_INCOGNITA_I.get(inc)

        if prefill.get("Q_m3s") is None:
            _agregar_faltante(faltantes, _pregunta(
                "Q_m3s", "el caudal conocido Q", "En Clase I el caudal debe conocerse para calcular las pérdidas.", unidad="m³/s"
            ))

        for clave in ("P1_kpa", "P2_kpa", "z1_m", "z2_m", "hA_m", "hR_m"):
            if clave == clave_inc:
                continue
            if prefill.get(clave) is None:
                etiqueta, unidad = _ETIQUETAS[clave]
                _agregar_faltante(faltantes, _pregunta(
                    clave, etiqueta, "Este término de la ecuación general de energía no está definido ni es la incógnita.", unidad=unidad
                ))

    elif clase in {"Clase II-A", "Clase II-B", "Clase II-C"}:
        for clave in ("P1_kpa", "P2_kpa", "z1_m", "z2_m", "hA_m", "hR_m"):
            if prefill.get(clave) is None:
                etiqueta, unidad = _ETIQUETAS[clave]
                _agregar_faltante(faltantes, _pregunta(
                    clave, etiqueta, "Se necesita para obtener la carga disponible antes de resolver Q.", unidad=unidad
                ))

    elif clase in {"Clase III-A", "Clase III-B"}:
        if prefill.get("Q_m3s") is None:
            _agregar_faltante(faltantes, _pregunta(
                "Q_m3s", "el caudal de diseño Q", "La Clase III parte de un caudal conocido.", unidad="m³/s"
            ))
        for clave in ("P1_kpa", "P2_kpa", "z1_m", "z2_m", "hA_m", "hR_m"):
            if prefill.get(clave) is None:
                etiqueta, unidad = _ETIQUETAS[clave]
                _agregar_faltante(faltantes, _pregunta(
                    clave, etiqueta, "Se necesita para definir la energía disponible del sistema.", unidad=unidad
                ))


def _agregar_requisitos_fluido(prefill, faltantes):
    fluido_app = prefill.get("fluido_app")
    fluido_detectado = prefill.get("fluido_detectado")
    rho_exp = prefill.get("rho_usuario")
    nu_exp = prefill.get("nu_usuario_m2s")
    mu_exp = prefill.get("mu_usuario_pa_s")
    mu_ambigua = prefill.get("mu_ocr_ambigua_v1412")

    def _positivo(v):
        try:
            return float(v) > 0
        except (TypeError, ValueError):
            return False

    # Un fluido de catálogo ya definido no necesita propiedades explícitas extra.
    if fluido_app and fluido_app != "Personalizado":
        if fluido_app == "Agua — interpolar temperatura" and prefill.get("temperatura_c") is None:
            _agregar_faltante(faltantes, _pregunta(
                "temperatura_c", "la temperatura del agua", "La viscosidad y el peso específico dependen de la temperatura.", unidad="°C"
            ))
        return

    # Personalizado o fluido genérico con ρ y ν suficientes: problema definido.
    if _positivo(rho_exp) and _positivo(nu_exp):
        if not fluido_app:
            prefill["fluido_app"] = "Personalizado"
        return

    # Si el texto ya identificó el fluido o al menos una propiedad física,
    # no se vuelve a pedir el nombre del fluido. Se solicita solo lo que falta.
    hay_contexto_fisico = bool(fluido_detectado) or any(
        x is not None for x in (rho_exp, nu_exp, mu_exp, prefill.get("sg_usuario"), mu_ambigua)
    )
    if hay_contexto_fisico:
        if not _positivo(rho_exp):
            _agregar_faltante(faltantes, _pregunta(
                "rho_usuario", "la densidad ρ del fluido", "Se necesita ρ para obtener ν=μ/ρ y el peso específico.", unidad="kg/m³"
            ))
        if not _positivo(nu_exp):
            if mu_ambigua:
                original = str(mu_ambigua.get("original") or "la viscosidad leída por OCR")
                _agregar_faltante(faltantes, _pregunta(
                    "mu_usuario_pa_s", "la viscosidad dinámica μ", 
                    f"El OCR leyó '{original}' y no recuperó de forma fiable el exponente. Confirme μ en Pa·s; V14.6 calculará ν=μ/ρ.",
                    unidad="Pa·s"
                ))
            elif not _positivo(mu_exp):
                _agregar_faltante(faltantes, _pregunta(
                    "nu_usuario_m2s", "la viscosidad cinemática ν", "El fluido fue identificado, pero falta una viscosidad utilizable para Reynolds y pérdidas.", unidad="m²/s"
                ))
        return

    _agregar_faltante(faltantes, _pregunta(
        "fluido_app", "el fluido de trabajo", "No se detectó un fluido ni propiedades físicas suficientes para Reynolds y pérdidas.", tipo="seleccion"
    ))

def _agregar_requisitos_tramos(clase, prefill, faltantes):
    tramos = list(prefill.get("tramos") or [])
    if not tramos:
        detalle = "Se necesita al menos un tramo para definir la tubería en serie."
        if clase == "Clase III-A":
            detalle += " En III-A el diámetro es la incógnita, pero L y material siguen siendo necesarios."
        _agregar_faltante(faltantes, _pregunta(
            "tramos", "al menos un tramo de tubería", detalle, tipo="estructura"
        ))
        return

    requiere_D = clase != "Clase III-A"
    for i, tramo in enumerate(tramos, 1):
        numero = int(tramo.get("numero", i) or i)
        if tramo.get("L_m") is None:
            _agregar_faltante(faltantes, _pregunta(
                "L_m", f"la longitud L del tramo {numero}", "La pérdida por fricción necesita L/D.", unidad="m", tramo=numero
            ))
        if requiere_D and tramo.get("D_m") is None:
            _agregar_faltante(faltantes, _pregunta(
                "D_m", f"el diámetro interior D del tramo {numero}", "La velocidad, Reynolds y pérdida por fricción dependen de D.", unidad="m", tramo=numero
            ))
        if not tramo.get("material"):
            _agregar_faltante(faltantes, _pregunta(
                "material", f"el material/rugosidad del tramo {numero}", "Se requiere la rugosidad absoluta para calcular el factor de fricción.", tipo="seleccion", tramo=numero
            ))


def _agregar_requisitos_elementos(clase, prefill, faltantes):
    # II-A desprecia pérdidas menores por definición del método.
    considerar = clase in {"Clase I", "Clase II-B", "Clase II-C", "Clase III-B"}
    if not considerar:
        return

    for i, tramo in enumerate(prefill.get("tramos") or [], 1):
        numero = int(tramo.get("numero", i) or i)
        for j, comp in enumerate(tramo.get("componentes_graficos") or [], 1):
            nombre = comp.get("nombre") or "componente detectado en figura"
            _agregar_faltante(faltantes, _pregunta(
                f"componente_grafico_{numero}_{j}",
                f"el tipo/K de {nombre} en el tramo {numero}",
                "La figura confirmó la posición del componente, pero no existe información suficiente para asignar K sin inventarlo.",
                tipo="confirmacion", tramo=numero,
            ))

    # V14.13: componentes detectados en texto cuya condición no permite asignar K
    # sin inventar información (por ejemplo, válvula mariposa sin apertura).
    for j, comp in enumerate(prefill.get("componentes_pendientes_v1413") or [], 1):
        tramo = comp.get("tramo")
        nombre = comp.get("nombre") or "componente hidráulico"
        etiqueta_tramo = f" en el tramo {tramo}" if tramo is not None else ""
        _agregar_faltante(faltantes, _pregunta(
            f"componente_texto_v1413_{j}",
            f"el tipo/condición de {nombre}{etiqueta_tramo}",
            "V14.13 reconoció el componente, pero no existe información suficiente para asignar K sin inventarlo.",
            tipo="confirmacion", tramo=tramo,
        ))

    for j, trans in enumerate(prefill.get("transiciones") or [], 1):
        entre = trans.get("entre", j)
        tipo_trans = trans.get("tipo")
        falta_angulo = (
            tipo_trans in {"Ensanchamiento gradual", "Contracción gradual"}
            and trans.get("angulo_grados") is None
        )
        if not tipo_trans or falta_angulo:
            detalle = (
                "El cambio de diámetro fue detectado, pero falta saber si es súbito, gradual o sin pérdida adicional."
                if not tipo_trans else
                f"V14.13 identificó {tipo_trans.lower()}, pero falta el ángulo incluido θ necesario para aplicar Mott."
            )
            _agregar_faltante(faltantes, _pregunta(
                f"transicion_{j}",
                f"la transición entre los tramos {entre} y {int(entre)+1}",
                detalle,
                tipo="seleccion",
            ))


def _filas_expediente(prefill, inferencias, incognitas, faltantes):
    inc_keys = {x.get("clave") for x in incognitas}
    falt_keys = {(x.get("clave"), x.get("tramo")) for x in faltantes}
    inf_keys = {x.get("clave") for x in inferencias}
    filas = []

    for clave, (etiqueta, unidad) in _ETIQUETAS.items():
        if clave in inc_keys:
            filas.append({"Dato": etiqueta, "Valor": "INCÓGNITA", "Estado": "🎯 Incógnita", "Fuente": "enunciado/clase"})
        elif prefill.get(clave) is not None:
            valor = float(prefill[clave])
            fuente = "inferencia segura V14.5" if clave in inf_keys else "texto/OCR/figura confirmada"
            filas.append({"Dato": etiqueta, "Valor": f"{valor:.8g} {unidad}", "Estado": "✅ Disponible", "Fuente": fuente})
        elif (clave, None) in falt_keys:
            filas.append({"Dato": etiqueta, "Valor": "—", "Estado": "⚠️ Falta", "Fuente": "usuario"})

    fluido_app = prefill.get("fluido_app")
    fluido_detectado = prefill.get("fluido_detectado")
    fluido = fluido_detectado or fluido_app
    rho_exp = prefill.get("rho_usuario")
    nu_exp = prefill.get("nu_usuario_m2s")
    mu_exp = prefill.get("mu_usuario_pa_s")
    mu_ambigua = prefill.get("mu_ocr_ambigua_v1412")

    def _pos(v):
        try:
            return float(v) > 0
        except (TypeError, ValueError):
            return False

    props_ok = _pos(rho_exp) and _pos(nu_exp)
    if fluido and props_ok:
        fluido_valor = f"{fluido} — Propiedades explícitas"
        fluido_estado = "✅ Disponible"
        fluido_fuente = "texto/OCR + SG/ρ + μ/ν"
    elif fluido:
        fluido_valor = str(fluido)
        fluido_estado = "⚠️ Propiedades incompletas" if fluido_app in (None, "Personalizado") else "✅ Disponible"
        fluido_fuente = "texto/OCR"
    elif props_ok:
        fluido_valor = f"Propiedades explícitas: ρ={float(rho_exp):.6g} kg/m³; ν={float(nu_exp):.6g} m²/s"
        fluido_estado = "✅ Disponible"
        fluido_fuente = "SG/ρ + μ/ν explícitas"
    elif any(x is not None for x in (rho_exp, nu_exp, mu_exp, mu_ambigua)):
        fluido_valor = "Propiedades parciales detectadas"
        fluido_estado = "⚠️ Propiedades incompletas"
        fluido_fuente = "texto/OCR"
    else:
        fluido_valor = "—"
        fluido_estado = "⚠️ Falta"
        fluido_fuente = "usuario"

    filas.append({
        "Dato": "Fluido",
        "Valor": fluido_valor,
        "Estado": fluido_estado,
        "Fuente": fluido_fuente,
    })

    if rho_exp is not None:
        filas.append({"Dato": "Densidad ρ", "Valor": f"{float(rho_exp):.8g} kg/m³", "Estado": "✅ Disponible", "Fuente": "SG/ρ explícita"})
    if mu_exp is not None:
        filas.append({"Dato": "Viscosidad dinámica μ", "Valor": f"{float(mu_exp):.8g} Pa·s", "Estado": "✅ Disponible", "Fuente": "texto/OCR"})
    elif mu_ambigua:
        filas.append({"Dato": "Viscosidad dinámica μ", "Valor": str(mu_ambigua.get("original") or "OCR ambiguo"), "Estado": "⚠️ Confirmar exponente", "Fuente": "OCR"})
    if nu_exp is not None:
        filas.append({"Dato": "Viscosidad cinemática ν", "Valor": f"{float(nu_exp):.8g} m²/s", "Estado": "✅ Disponible", "Fuente": "texto/OCR o μ/ρ"})

    for i, tramo in enumerate(prefill.get("tramos") or [], 1):
        numero = int(tramo.get("numero", i) or i)
        for clave, etiqueta, unidad in (("L_m", "L", "m"), ("D_m", "D", "m")):
            v = tramo.get(clave)
            if clave == "D_m" and "D_m" in inc_keys:
                estado, valor = "🎯 Incógnita", "INCÓGNITA"
            elif v is not None:
                estado, valor = "✅ Disponible", f"{float(v):.8g} {unidad}"
            else:
                estado, valor = "⚠️ Falta", "—"
            filas.append({"Dato": f"Tramo {numero} — {etiqueta}", "Valor": valor, "Estado": estado, "Fuente": "texto/OCR/figura confirmada" if v is not None else "usuario"})
        mat = tramo.get("material")
        filas.append({"Dato": f"Tramo {numero} — material", "Valor": mat or "—", "Estado": "✅ Disponible" if mat else "⚠️ Falta", "Fuente": "texto/OCR" if mat else "usuario"})

    return filas


def _preservar_inferencias_previas(resultado_original: dict, prefill_actual: dict, inferencias_nuevas: list[dict]) -> list[dict]:
    """Conserva procedencia V14.5 a través de reconsolidaciones si el valor no cambió.

    V14.6/V14.7/V14.11 vuelven a consolidar el mismo resultado. Sin esta
    protección, una inferencia aplicada en la primera pasada deja de aparecer
    como inferencia en las siguientes porque el valor ya está rellenado.
    """
    prev = list(((resultado_original or {}).get("expediente_v145") or {}).get("inferencias") or [])
    respuestas = {
        (str(x.get("clave") or ""), x.get("tramo"))
        for x in (resultado_original or {}).get("respuestas_v146") or []
    }
    mapa = {str(x.get("clave") or ""): copy.deepcopy(x) for x in inferencias_nuevas if x.get("clave")}
    for inf in prev:
        clave = str(inf.get("clave") or "")
        if not clave or (clave, None) in respuestas or clave in mapa:
            continue
        actual = prefill_actual.get(clave)
        previo = inf.get("valor")
        coincide = False
        try:
            ref = max(1.0, abs(float(actual)), abs(float(previo)))
            coincide = abs(float(actual) - float(previo)) <= 1e-10 * ref
        except (TypeError, ValueError):
            coincide = actual == previo
        if coincide:
            mapa[clave] = copy.deepcopy(inf)
    return list(mapa.values())


def _inferir_referencias_relativas_clase_ii(prefill: dict, enunciado: str, clase: str | None, inferencias: list[dict]):
    """Completa referencias relativas seguras para problemas Clase II de línea.

    Si el enunciado entrega solo ΔP, la energía depende de P1-P2, no del cero
    manométrico elegido. Se usa P2=0 y P1=ΔP como referencia relativa. Si el
    sistema se declara horizontal, z1=z2=0 como referencia relativa.
    """
    if clase not in {"Clase II-A", "Clase II-B", "Clase II-C"}:
        return
    t = _norm(enunciado)

    dp = prefill.get("deltaP_kpa")
    if dp is not None and prefill.get("P1_kpa") is None and prefill.get("P2_kpa") is None:
        try:
            dp = float(dp)
        except Exception:
            dp = None
        if dp is not None and dp >= 0:
            prefill["P1_kpa"] = dp
            prefill["P2_kpa"] = 0.0
            prefill["presiones_relativas_desde_deltaP"] = True
            inferencias.append({
                "clave": "P1_kpa/P2_kpa", "valor": f"{dp:g}/0", "unidad": "kPa",
                "fuente": "diferencia de presión explícita",
                "detalle": "El enunciado proporciona ΔP=P1-P2. Para la ecuación de energía se adopta P2=0 kPa como referencia manométrica relativa y P1=ΔP; no se interpreta como presión absoluta real.",
                "confianza": "alta",
            })

    horizontal = bool(re.search(r"\b(horizontal|plano\s+horizontal|tuberia\s+horizontal|linea\s+horizontal|horizontal\s+plane|piping\s+system[^.\n]{0,35}horizontal)\b", t))
    if horizontal and prefill.get("z1_m") is None and prefill.get("z2_m") is None:
        prefill["z1_m"] = 0.0
        prefill["z2_m"] = 0.0
        prefill["elevaciones_relativas_horizontales"] = True
        inferencias.append({
            "clave": "z1_m/z2_m", "valor": "0/0", "unidad": "m",
            "fuente": "sistema horizontal",
            "detalle": "El sistema se declara horizontal; se adopta z1=z2=0 m como referencia relativa.",
            "confianza": "alta",
        })


def consolidar_resultado(resultado: dict, enunciado: str = "") -> dict:
    """Devuelve una copia del resultado con ``expediente_v145`` y prefill consolidado."""
    original = copy.deepcopy(resultado or {})
    salida = copy.deepcopy(resultado or {})
    prefill = salida.setdefault("prefill", {})
    clase = salida.get("clase")
    inferencias: list[dict] = []

    diags_atm = _inferir_atmosfera(prefill, enunciado, inferencias)
    _inferir_referencias_relativas_clase_ii(prefill, enunciado, clase, inferencias)
    _inferir_maquinas(prefill, enunciado, clase, inferencias)
    inferencias = _preservar_inferencias_previas(original, prefill, inferencias)

    faltantes: list[dict] = []
    if clase:
        _agregar_requisitos_fluido(prefill, faltantes)
        _agregar_requisitos_tramos(clase, prefill, faltantes)
        _agregar_requisitos_escalares(clase, prefill, faltantes)
        _agregar_requisitos_elementos(clase, prefill, faltantes)

    incognitas = _incognitas_del_problema(clase, prefill)
    auditoria = construir_auditoria_datos(prefill, enunciado)
    conflictos = [f for f in auditoria if str(f.get("Estado", "")).startswith("❌")]
    conflictos += [d for d in diags_atm if bool(d.get("bloqueante"))]

    # Métrica de completitud: requisitos satisfechos / (satisfechos + faltantes).
    satisfechos = 0
    requisitos_base = 0
    filas = _filas_expediente(prefill, inferencias, incognitas, faltantes)
    for f in filas:
        if str(f.get("Estado", "")).startswith("✅"):
            satisfechos += 1
        if not str(f.get("Estado", "")).startswith("🎯"):
            requisitos_base += 1
    total_eval = max(requisitos_base, satisfechos + len(faltantes), 1)
    completitud = round(100.0 * satisfechos / total_eval, 1)

    expediente = {
        "version": VERSION_EXPEDIENTE,
        "clase": clase,
        "confianza_clase": salida.get("confianza", 0),
        "filas": filas,
        "inferencias": inferencias,
        "incognitas": incognitas,
        "faltantes": faltantes,
        "conflictos": conflictos,
        "cantidad_faltantes": len(faltantes),
        "cantidad_conflictos": len(conflictos),
        "completitud_pct": completitud,
        "listo_para_autollenado": bool(clase) and not conflictos,
        "listo_para_resolver": bool(clase) and not conflictos and not faltantes,
    }

    salida["expediente_v145"] = expediente
    salida["consolidacion_v145"] = True

    # Refresca auditoría/datos implícitamente vía prefill; no se alteran razones de clasificación.
    if inferencias:
        adv = salida.setdefault("advertencias", [])
        msg = "V14.5 aplicó inferencias físicamente seguras y trazables antes del autollenado."
        if msg not in adv:
            adv.append(msg)

    return salida


def construir_expediente_problema(resultado: dict, enunciado: str = "") -> dict:
    """Atajo de solo lectura para consumidores que únicamente necesitan el expediente."""
    return consolidar_resultado(resultado, enunciado).get("expediente_v145", {})
