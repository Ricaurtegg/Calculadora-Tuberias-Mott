"""Previsualización y validación de transferencia al solucionador — V14.7.

Esta capa NO resuelve la hidráulica. Su función es construir una fotografía
inmutable de los datos que ``app.py`` transferirá a los controles del solver,
validar que no existan faltantes/conflictos y exigir una confirmación explícita
antes del autollenado.

Principios:
- no inventa valores ni corrige silenciosamente el expediente;
- distingue datos transferibles de incógnitas del método;
- incluye tramos, accesorios, K adicionales, curvas y transiciones;
- genera una firma determinista: si cambia cualquier dato, la confirmación
  anterior deja de ser válida automáticamente.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math

from catalogos_mott import FLUIDOS, MATERIALES
from consolidacion_datos import consolidar_resultado


VERSION_TRANSFERENCIA = "V14.7"


def _finito(v) -> bool:
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def _positivo(v) -> bool:
    return _finito(v) and float(v) > 0.0


def _no_negativo(v) -> bool:
    return _finito(v) and float(v) >= 0.0


def _fmt(v, unidad="") -> str:
    if v is None:
        return "—"
    if isinstance(v, str):
        return v
    if _finito(v):
        suf = f" {unidad}" if unidad else ""
        return f"{float(v):.8g}{suf}"
    return str(v)


def _serializable(obj):
    if isinstance(obj, dict):
        return {str(k): _serializable(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (list, tuple)):
        return [_serializable(v) for v in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return str(obj)
        return round(obj, 14)
    return obj


def firma_snapshot(snapshot: dict) -> str:
    bruto = json.dumps(_serializable(snapshot), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


def _resumen_accesorios(tramo: dict) -> str:
    partes = []
    for item in tramo.get("accesorios") or []:
        nombre = str(item.get("nombre") or "Accesorio")
        cantidad = max(1, int(item.get("cantidad", 1) or 1))
        partes.append(f"{cantidad}× {nombre}" if cantidad > 1 else nombre)
    k = tramo.get("K_extra")
    if k is not None and _finito(k) and float(k) > 0:
        partes.append(f"K adicional={float(k):.6g}")
    curvas = tramo.get("curvas") or []
    if curvas:
        partes.append(f"{len(curvas)} curva(s)")
    return "; ".join(partes) if partes else "Ninguno"


def _snapshot_transferible(base: dict) -> dict:
    prefill = copy.deepcopy(base.get("prefill") or {})
    exp = base.get("expediente_v145") or {}
    snap = {
        "version": VERSION_TRANSFERENCIA,
        "clase": base.get("clase"),
        "confianza": base.get("confianza"),
        "prefill": prefill,
        "incognitas": copy.deepcopy(exp.get("incognitas") or []),
    }
    conf = base.get("confianza_datos_v1411") or {}
    if conf:
        # La procedencia/confianza forma parte de lo revisado. Si cambia aunque
        # el valor numérico sea igual, V14.7 exige una confirmación nueva.
        snap["firma_confianza_v1411"] = conf.get("firma")
    return snap


def construir_previsualizacion_transferencia(resultado: dict, enunciado: str = "") -> dict:
    """Construye y valida exactamente lo que se transferirá al solucionador."""
    base = consolidar_resultado(copy.deepcopy(resultado or {}), enunciado)
    exp = base.get("expediente_v145") or {}
    prefill = base.get("prefill") or {}
    clase = base.get("clase")

    bloqueos: list[str] = []
    advertencias: list[str] = []

    if not clase:
        bloqueos.append("No hay una clase hidráulica confirmada para transferir.")

    faltantes = list(exp.get("faltantes") or [])
    conflictos = list(exp.get("conflictos") or [])
    confianza_v1411 = base.get("confianza_datos_v1411") or {}
    if confianza_v1411 and not confianza_v1411.get("listo_para_v147"):
        bloqueos.append(
            f"V14.11 conserva {int(confianza_v1411.get('pendientes_confirmacion', 0) or 0)} dato(s) de confianza media/baja sin confirmar."
        )
    if faltantes:
        bloqueos.append(f"El expediente conserva {len(faltantes)} dato(s) faltante(s).")
    if conflictos:
        bloqueos.append(f"El expediente conserva {len(conflictos)} conflicto(s) bloqueante(s).")

    fluido = prefill.get("fluido_app") or prefill.get("fluido_detectado")
    props_explicitas_ok = (
        bool(prefill.get("propiedades_explicitas_v1412"))
        and _positivo(prefill.get("rho_usuario"))
        and _positivo(prefill.get("nu_usuario_m2s"))
    )
    if not fluido and props_explicitas_ok:
        fluido = "Propiedades explícitas"
    if not fluido:
        bloqueos.append("No existe un fluido definido ni propiedades ρ/ν suficientes para el solucionador.")
    elif fluido == "Personalizado":
        if not _positivo(prefill.get("rho_usuario")):
            bloqueos.append("El fluido personalizado requiere densidad ρ > 0.")
        if not _positivo(prefill.get("nu_usuario_m2s")):
            bloqueos.append("El fluido personalizado requiere viscosidad cinemática ν > 0.")
    elif fluido in FLUIDOS:
        datos_f = FLUIDOS[fluido]
        if datos_f.get("nu") is None and datos_f.get("tipo") != "agua_interpolar":
            if not _positivo(prefill.get("nu_usuario_m2s")):
                bloqueos.append(f"{fluido} requiere una ν definida por el usuario.")

    tramos = list(prefill.get("tramos") or [])
    if not tramos:
        bloqueos.append("No existen tramos de tubería para transferir.")

    inc_keys = {str(x.get("clave")) for x in exp.get("incognitas") or []}
    filas_tramos = []
    for i, tramo in enumerate(tramos, 1):
        numero = int(tramo.get("numero", i) or i)
        L = tramo.get("L_m")
        D = tramo.get("D_m")
        material = tramo.get("material")

        if not _positivo(L):
            bloqueos.append(f"Tramo {numero}: L debe estar definida y ser mayor que cero.")
        if clase != "Clase III-A" and not _positivo(D):
            bloqueos.append(f"Tramo {numero}: D debe estar definido y ser mayor que cero.")
        if not material:
            bloqueos.append(f"Tramo {numero}: falta material/rugosidad.")
        elif material == "Personalizada":
            eps = tramo.get("epsilon_m")
            if not _no_negativo(eps):
                bloqueos.append(f"Tramo {numero}: el material personalizado requiere ε ≥ 0.")

        componentes = tramo.get("componentes_graficos") or []
        if componentes:
            if clase == "Clase II-A":
                advertencias.append(
                    f"Tramo {numero}: quedan {len(componentes)} componente(s) gráfico(s) sin K; "
                    "Clase II-A no incorpora pérdidas menores."
                )
            else:
                bloqueos.append(
                    f"Tramo {numero}: quedan {len(componentes)} componente(s) gráfico(s) sin tipo/K confirmado."
                )

        filas_tramos.append({
            "Tramo": numero,
            "L": _fmt(L, "m"),
            "D": "INCÓGNITA" if clase == "Clase III-A" else _fmt(D, "m"),
            "Material": material or "—",
            "ε": _fmt(tramo.get("epsilon_m"), "m") if material == "Personalizada" else "catálogo",
            "Accesorios / pérdidas menores": _resumen_accesorios(tramo),
        })

    transiciones = []
    for i, trans in enumerate(prefill.get("transiciones") or [], 1):
        entre = int(trans.get("entre", i) or i)
        tipo = trans.get("tipo")
        if not tipo:
            bloqueos.append(f"Transición {entre}→{entre + 1}: falta confirmar el tipo.")
        transiciones.append({
            "Entre tramos": f"{entre} → {entre + 1}",
            "Tipo": tipo or "—",
            "Ángulo": _fmt(trans.get("angulo_grados"), "°") if trans.get("angulo_grados") is not None else "—",
        })

    campos = [
        ("Q_m3s", "Caudal Q", "m³/s"),
        ("P1_kpa", "Presión P1", "kPa"),
        ("P2_kpa", "Presión P2", "kPa"),
        ("z1_m", "Elevación z1", "m"),
        ("z2_m", "Elevación z2", "m"),
        ("hA_m", "Carga de bomba hA", "m"),
        ("hR_m", "Carga de turbina hR", "m"),
    ]
    filas_generales = []
    for clave, etiqueta, unidad in campos:
        if clave in inc_keys:
            valor = "INCÓGNITA"
            estado = "🎯 Se calculará"
        elif prefill.get(clave) is not None:
            valor = _fmt(prefill.get(clave), unidad)
            estado = "✅ Se transferirá"
        else:
            valor = "—"
            estado = "⚠️ No definido"
        filas_generales.append({"Dato": etiqueta, "Valor": valor, "Estado": estado})

    filas_generales.insert(0, {
        "Dato": "Fluido",
        "Valor": str(fluido or "—"),
        "Estado": "✅ Se transferirá" if fluido else "⚠️ No definido",
    })
    if prefill.get("temperatura_c") is not None:
        filas_generales.insert(1, {
            "Dato": "Temperatura",
            "Valor": _fmt(prefill.get("temperatura_c"), "°C"),
            "Estado": "✅ Se transferirá",
        })

    if clase == "Clase I":
        inc_i = prefill.get("incognita_clase_i")
        if not inc_i:
            bloqueos.append("Clase I requiere una incógnita explícita antes de transferir.")
        else:
            filas_generales.append({
                "Dato": "Incógnita Clase I", "Valor": str(inc_i), "Estado": "🎯 Se calculará"
            })

    snapshot = _snapshot_transferible(base)
    firma = firma_snapshot(snapshot)

    # Deduplicación conservando orden.
    bloqueos = list(dict.fromkeys(str(x) for x in bloqueos if str(x).strip()))
    advertencias = list(dict.fromkeys(str(x) for x in advertencias if str(x).strip()))
    listo = bool(clase) and not bloqueos and bool(exp.get("listo_para_resolver"))

    return {
        "version": VERSION_TRANSFERENCIA,
        "clase": clase,
        "confianza_clase": base.get("confianza", 0),
        "listo_para_transferir": listo,
        "bloqueos": bloqueos,
        "advertencias": advertencias,
        "incognitas": copy.deepcopy(exp.get("incognitas") or []),
        "filas_generales": filas_generales,
        "filas_tramos": filas_tramos,
        "filas_transiciones": transiciones,
        "cantidad_tramos": len(tramos),
        "firma": firma,
        "firma_corta": firma[:12],
        "snapshot": snapshot,
        "resultado_consolidado": base,
    }


def confirmacion_corresponde(previsualizacion: dict, firma_confirmada: str | None) -> bool:
    """Valida que una confirmación pertenezca exactamente al snapshot actual."""
    return bool(
        previsualizacion
        and previsualizacion.get("listo_para_transferir")
        and firma_confirmada
        and str(firma_confirmada) == str(previsualizacion.get("firma"))
    )
