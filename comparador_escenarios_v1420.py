"""Comparador de escenarios hidráulicos — V14.20.

V14.20 parte de un flujo V14.10 ya resuelto y confirmado. El escenario base
permanece inmutable. Cada variante aplica cambios explícitos del usuario sobre
una copia del snapshot V14.7 y vuelve a ejecutar exactamente el mismo pipeline:
solver -> V14.8.3 -> V14.16 -> V14.15 -> V14.19 -> V14.9.

No cambia automáticamente la clase hidráulica. Si un cambio contradice la clase
(p. ej. fijar Q en Clase II o D en III-A), se bloquea en vez de reinterpretar el
problema silenciosamente.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import math
from typing import Any

from catalogos_mott import MATERIALES, ACCESORIOS
from transferencia_v147 import construir_previsualizacion_transferencia
from reporte_final_v149 import construir_manifiesto_ejecucion
from flujo_automatico_v1410 import resolver_flujo_confirmado

VERSION_COMPARADOR = "V14.20"
REVISION_COMPARADOR = "V14.20.1"


class ErrorComparadorV1420(ValueError):
    pass


def _finito(v) -> bool:
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def _positivo(v) -> bool:
    return _finito(v) and float(v) > 0.0


def _no_negativo(v) -> bool:
    return _finito(v) and float(v) >= 0.0


def _json_estable(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _firma(obj: Any) -> str:
    return hashlib.sha256(_json_estable(obj).encode("utf-8")).hexdigest()


def _manifiesto_base(flujo_base: dict) -> dict:
    m = copy.deepcopy((flujo_base or {}).get("manifiesto_v149") or {})
    if not m:
        raise ErrorComparadorV1420("El flujo base no contiene el manifiesto trazable V14.9.")
    snap = m.get("snapshot_v147") or {}
    if not snap.get("prefill"):
        raise ErrorComparadorV1420("El manifiesto base no conserva el prefill del snapshot V14.7.")
    return m


def extraer_prefill_base(flujo_base: dict) -> dict:
    """Devuelve una COPIA del prefill confirmado. Nunca retorna el objeto original."""
    m = _manifiesto_base(flujo_base)
    return copy.deepcopy((m.get("snapshot_v147") or {}).get("prefill") or {})


def firma_base(flujo_base: dict) -> str:
    m = _manifiesto_base(flujo_base)
    return str(m.get("firma_transferencia_v147") or (m.get("snapshot_v147") or {}).get("firma") or _firma(m.get("snapshot_v147") or {}))


def _tramo(prefill: dict, numero: int) -> dict:
    for i, t in enumerate(prefill.get("tramos") or [], 1):
        n = int(t.get("numero", i) or i)
        if n == int(numero):
            return t
    raise ErrorComparadorV1420(f"No existe el tramo {numero} en el escenario base.")


def _indice_accesorio(t: dict, indice: int) -> int:
    accs = list(t.get("accesorios") or [])
    i = int(indice)
    if i < 0 or i >= len(accs):
        raise ErrorComparadorV1420(f"Índice de accesorio fuera de rango: {i}.")
    return i


def _incognita_clase_i(prefill: dict) -> str | None:
    etiqueta = prefill.get("incognita_clase_i")
    mapa = {
        "Presión P2": "P2_kpa", "Presión P1": "P1_kpa",
        "Carga agregada por bomba hA": "hA_m", "Carga retirada hR": "hR_m",
        "Elevación z2": "z2_m", "Elevación z1": "z1_m",
        "P2": "P2_kpa", "P1": "P1_kpa", "hA": "hA_m", "hR": "hR_m",
        "z2": "z2_m", "z1": "z1_m",
    }
    return mapa.get(etiqueta)


def validar_cambio(clase: str, prefill: dict, cambio: dict) -> None:
    campo = str(cambio.get("campo") or "").strip()
    if not campo:
        raise ErrorComparadorV1420("Cada cambio requiere un campo.")

    if clase in ("Clase II-A", "Clase II-B", "Clase II-C") and campo == "Q_m3s":
        raise ErrorComparadorV1420("En Clase II el caudal Q es la incógnita; V14.20 no permite fijarlo como dato.")
    if clase == "Clase III-A" and campo == "D_m":
        raise ErrorComparadorV1420("En Clase III-A el diámetro D es la incógnita; V14.20 no permite fijarlo como dato.")
    if clase == "Clase III-A" and campo in {"K_extra", "accesorio_reemplazar", "accesorio_agregar", "accesorio_eliminar", "transicion_tipo"}:
        raise ErrorComparadorV1420("La implementación III-A de Mott Ec. (11-8) no incorpora pérdidas menores; este cambio no sería físicamente comparativo.")
    if clase == "Clase II-A" and campo in {"K_extra", "accesorio_reemplazar", "accesorio_agregar", "accesorio_eliminar", "transicion_tipo"}:
        raise ErrorComparadorV1420("Clase II-A desprecia pérdidas menores; cambie geometría/material/condiciones o compare con una clase que las incluya.")
    if clase == "Clase I" and campo == _incognita_clase_i(prefill):
        raise ErrorComparadorV1420("No puede fijar directamente la incógnita que Clase I debe calcular.")

    valor = cambio.get("valor")
    if campo in {"D_m", "L_m", "Q_m3s"} and not _positivo(valor):
        raise ErrorComparadorV1420(f"{campo} debe ser mayor que cero.")
    if campo in {"hA_m", "hR_m", "K_extra"} and not _no_negativo(valor):
        raise ErrorComparadorV1420(f"{campo} debe ser mayor o igual que cero.")
    if campo in {"P1_kpa", "P2_kpa", "z1_m", "z2_m"} and not _finito(valor):
        raise ErrorComparadorV1420(f"{campo} debe ser numérico y finito.")
    if campo == "material" and valor not in MATERIALES:
        raise ErrorComparadorV1420(f"Material no reconocido: {valor}")
    if campo in {"accesorio_reemplazar", "accesorio_agregar"} and valor not in ACCESORIOS:
        raise ErrorComparadorV1420(f"Accesorio no reconocido: {valor}")


def aplicar_cambios(prefill_base: dict, clase: str, cambios: list[dict]) -> tuple[dict, list[dict]]:
    """Aplica cambios explícitos a una copia del prefill base.

    Retorna ``(prefill_nuevo, cambios_normalizados)``.
    """
    prefill = copy.deepcopy(prefill_base or {})
    normalizados: list[dict] = []

    for raw in cambios or []:
        cambio = copy.deepcopy(raw or {})
        validar_cambio(clase, prefill, cambio)
        campo = str(cambio["campo"])
        valor = cambio.get("valor")
        registro = {"campo": campo, "valor": copy.deepcopy(valor)}

        if campo in {"P1_kpa", "P2_kpa", "z1_m", "z2_m", "hA_m", "hR_m", "Q_m3s"}:
            anterior = prefill.get(campo)
            prefill[campo] = float(valor)
            registro.update({"anterior": anterior, "unidad": {
                "P1_kpa": "kPa", "P2_kpa": "kPa", "z1_m": "m", "z2_m": "m",
                "hA_m": "m", "hR_m": "m", "Q_m3s": "m³/s",
            }[campo]})

        elif campo in {"D_m", "L_m", "material", "K_extra"}:
            numero = int(cambio.get("tramo") or 0)
            if numero <= 0:
                raise ErrorComparadorV1420(f"{campo} requiere indicar un tramo.")
            t = _tramo(prefill, numero)
            clave = {"D_m": "D_m", "L_m": "L_m", "material": "material", "K_extra": "K_extra"}[campo]
            anterior = t.get(clave)
            t[clave] = str(valor) if campo == "material" else float(valor)
            if campo == "material":
                if valor == "Personalizada":
                    eps = cambio.get("epsilon_m")
                    if not _no_negativo(eps):
                        raise ErrorComparadorV1420("Material Personalizada requiere epsilon_m >= 0.")
                    t["epsilon_m"] = float(eps)
                    registro["epsilon_m"] = float(eps)
                else:
                    t.pop("epsilon_m", None)
            registro.update({"tramo": numero, "anterior": anterior})

        elif campo == "accesorio_reemplazar":
            numero = int(cambio.get("tramo") or 0)
            t = _tramo(prefill, numero)
            idx = _indice_accesorio(t, int(cambio.get("indice_accesorio", -1)))
            accs = t.setdefault("accesorios", [])
            anterior = copy.deepcopy(accs[idx])
            cantidad = max(1, int(cambio.get("cantidad", anterior.get("cantidad", 1)) or 1))
            nuevo = {"nombre": str(valor), "cantidad": cantidad}
            # Conserva posiciones explícitas si existían.
            for k in ("posicion_fraccion", "posiciones_fraccion"):
                if k in anterior:
                    nuevo[k] = copy.deepcopy(anterior[k])
            accs[idx] = nuevo
            registro.update({"tramo": numero, "indice_accesorio": idx, "anterior": anterior, "cantidad": cantidad})

        elif campo == "accesorio_agregar":
            numero = int(cambio.get("tramo") or 0)
            t = _tramo(prefill, numero)
            cantidad = max(1, int(cambio.get("cantidad", 1) or 1))
            nuevo = {"nombre": str(valor), "cantidad": cantidad}
            if _finito(cambio.get("posicion_fraccion")):
                nuevo["posicion_fraccion"] = min(max(float(cambio["posicion_fraccion"]), 0.0), 1.0)
            t.setdefault("accesorios", []).append(nuevo)
            registro.update({"tramo": numero, "cantidad": cantidad, "anterior": None})

        elif campo == "accesorio_eliminar":
            numero = int(cambio.get("tramo") or 0)
            t = _tramo(prefill, numero)
            idx = _indice_accesorio(t, int(cambio.get("indice_accesorio", -1)))
            anterior = t.setdefault("accesorios", []).pop(idx)
            registro.update({"tramo": numero, "indice_accesorio": idx, "anterior": copy.deepcopy(anterior), "valor": None})

        elif campo == "transicion_tipo":
            entre = int(cambio.get("entre") or 0)
            trans = None
            for i, tr in enumerate(prefill.get("transiciones") or [], 1):
                if int(tr.get("entre", i) or i) == entre:
                    trans = tr
                    break
            if trans is None:
                raise ErrorComparadorV1420(f"No existe transición {entre}→{entre+1}.")
            anterior = {"tipo": trans.get("tipo"), "angulo_grados": trans.get("angulo_grados")}
            trans["tipo"] = str(valor)
            if cambio.get("angulo_grados") is not None:
                ang = cambio.get("angulo_grados")
                if not _positivo(ang):
                    raise ErrorComparadorV1420("El ángulo de transición debe ser mayor que cero.")
                trans["angulo_grados"] = float(ang)
            registro.update({"entre": entre, "anterior": anterior, "angulo_grados": trans.get("angulo_grados")})

        else:
            raise ErrorComparadorV1420(f"Cambio no soportado por V14.20: {campo}")

        normalizados.append(registro)

    return prefill, normalizados


def _filas_hidraulicas(flujo: dict) -> list[dict]:
    r = (flujo or {}).get("resultado_solver") or {}
    clase = str((flujo or {}).get("clase") or "")
    if clase in {"Clase I", "Clase II-A", "Clase II-B", "Clase II-C"}:
        return list((r.get("sistema") or {}).get("resultados") or [])
    if clase in {"Clase III-A", "Clase III-B"}:
        return [{
            "V (m/s)": r.get("V"), "Re": r.get("Re"), "f Darcy": r.get("f"),
            "hf (m)": r.get("hf"), "hm (m)": r.get("hm", 0.0),
        }]
    return []


def _q_flujo(flujo: dict) -> float | None:
    ctx = (flujo or {}).get("contexto_diagramas_v1415") or {}
    if _finito(ctx.get("Q_m3s")):
        return float(ctx["Q_m3s"])
    r = (flujo or {}).get("resultado_solver") or {}
    for k in ("Q_final", "Q_m3s", "Q"):
        if _finito(r.get(k)):
            return float(r[k])
    return None


def _hL_flujo(flujo: dict) -> float | None:
    r = (flujo or {}).get("resultado_solver") or {}
    clase = str((flujo or {}).get("clase") or "")
    if clase in {"Clase I", "Clase II-A", "Clase II-B", "Clase II-C"}:
        s = r.get("sistema") or {}
        return float(s["hL_total"]) if _finito(s.get("hL_total")) else None
    if clase == "Clase III-A":
        return float(r["hf"]) if _finito(r.get("hf")) else None
    if clase == "Clase III-B":
        return float(r["hL"]) if _finito(r.get("hL")) else None
    return None


def _principal(flujo: dict) -> tuple[str, float | None, str]:
    clase = str((flujo or {}).get("clase") or "")
    r = (flujo or {}).get("resultado_solver") or {}
    if clase in {"Clase II-A", "Clase II-B", "Clase II-C"}:
        return "Q", _q_flujo(flujo), "m³/s"
    if clase == "Clase I":
        inc = str(r.get("incognita") or "Resultado")
        valor = r.get("valor")
        unidad = str(r.get("unidad") or "")
        if unidad == "Pa" and _finito(valor):
            return inc, float(valor) / 1000.0, "kPa"
        return inc, float(valor) if _finito(valor) else None, unidad
    if clase == "Clase III-A":
        return "D mínimo", float(r["D_mott"]) if _finito(r.get("D_mott")) else None, "m"
    if clase == "Clase III-B":
        p2 = r.get("P2_calculada")
        return "P2 calculada", float(p2) / 1000.0 if _finito(p2) else None, "kPa"
    return "Resultado", None, ""


def resumen_flujo(flujo: dict, nombre: str, *, es_base=False, cambios=None) -> dict:
    filas = _filas_hidraulicas(flujo)
    velocidades = [float(x.get("V (m/s)")) for x in filas if _finito(x.get("V (m/s)"))]
    reynolds = [float(x.get("Re")) for x in filas if _finito(x.get("Re"))]
    fs = [float(x.get("f Darcy")) for x in filas if _finito(x.get("f Darcy"))]
    principal_nombre, principal_valor, principal_unidad = _principal(flujo)
    ctx = (flujo or {}).get("contexto_diagramas_v1415") or {}
    prop = (flujo or {}).get("propiedades_fluido") or {}
    q = _q_flujo(flujo)
    hA = ctx.get("hA_m")
    hR = ctx.get("hR_m")
    rho = prop.get("rho")
    potencia_bomba_kw = None
    potencia_turbina_kw = None
    if _positivo(q) and _positivo(rho):
        if _positivo(hA):
            potencia_bomba_kw = float(rho) * 9.81 * float(q) * float(hA) / 1000.0
        if _positivo(hR):
            potencia_turbina_kw = float(rho) * 9.81 * float(q) * float(hR) / 1000.0
    r = (flujo or {}).get("resultado_solver") or {}
    margen_kpa = None
    if _finito(r.get("margen_presion")):
        margen_kpa = float(r["margen_presion"]) / 1000.0

    return {
        "nombre": str(nombre),
        "es_base": bool(es_base),
        "clase": str((flujo or {}).get("clase") or ""),
        "estado_matematico": str((flujo or {}).get("estado") or "—"),
        "estado_fisico": str((flujo or {}).get("estado_fisico") or "—"),
        "estado_integral": str((flujo or {}).get("estado_integral") or "—"),
        "principal": principal_nombre,
        "principal_valor": principal_valor,
        "principal_unidad": principal_unidad,
        "Q_m3s": q,
        "hL_total_m": _hL_flujo(flujo),
        "V_max_ms": max(velocidades) if velocidades else None,
        "Re_min": min(reynolds) if reynolds else None,
        "Re_max": max(reynolds) if reynolds else None,
        "f_min": min(fs) if fs else None,
        "f_max": max(fs) if fs else None,
        "potencia_bomba_hidraulica_kW": potencia_bomba_kw,
        "potencia_turbina_hidraulica_kW": potencia_turbina_kw,
        "margen_presion_kPa": margen_kpa,
        "cambios": copy.deepcopy(cambios or []),
    }


def _delta_pct(valor, base):
    if not (_finito(valor) and _finito(base)) or abs(float(base)) < 1e-15:
        return None
    delta = (float(valor) - float(base)) / abs(float(base)) * 100.0
    # Evita mostrar ruido de punto flotante como 1e-9 % cuando físicamente es 0.
    return 0.0 if abs(delta) < 1e-7 else delta


def resolver_escenario(flujo_base: dict, cambios: list[dict], nombre: str = "Escenario") -> dict:
    """Resuelve una variante desde el snapshot V14.7 del flujo base."""
    mbase = _manifiesto_base(flujo_base)
    clase = str((flujo_base or {}).get("clase") or mbase.get("clase") or "")
    if not clase:
        raise ErrorComparadorV1420("El escenario base no conserva la clase hidráulica.")
    prefill0 = extraer_prefill_base(flujo_base)
    prefill, cambios_norm = aplicar_cambios(prefill0, clase, cambios)

    resultado_escenario = {
        "clase": clase,
        "confianza": 100,
        "prefill": prefill,
        "escenario_v1420": {
            "version": VERSION_COMPARADOR,
            "nombre": str(nombre),
            "firma_base": firma_base(flujo_base),
            "cambios": copy.deepcopy(cambios_norm),
            "origen": "variante explícita del usuario",
        },
    }
    enunciado_base = str(mbase.get("enunciado") or "")
    enunciado = f"[V14.20 · {nombre}] Variante explícita del escenario base.\n{enunciado_base}"
    preview = construir_previsualizacion_transferencia(resultado_escenario, enunciado)
    if not preview.get("listo_para_transferir"):
        raise ErrorComparadorV1420("El escenario modificado no es resoluble: " + "; ".join(preview.get("bloqueos") or []))
    manifiesto = construir_manifiesto_ejecucion(resultado_escenario, enunciado, preview)
    flujo = resolver_flujo_confirmado(resultado_escenario, enunciado, preview, preview["firma"], manifiesto)

    ident = _firma({"base": firma_base(flujo_base), "nombre": nombre, "cambios": cambios_norm})
    resumen = resumen_flujo(flujo, nombre, es_base=False, cambios=cambios_norm)
    resumen["firma_escenario"] = ident
    return {
        "version": VERSION_COMPARADOR,
        "nombre": str(nombre),
        "firma_escenario": ident,
        "firma_base": firma_base(flujo_base),
        "cambios": cambios_norm,
        "resumen": resumen,
        "flujo": flujo,
    }


def construir_comparacion(flujo_base: dict, escenarios: list[dict]) -> dict:
    """Construye tabla comparativa a partir de escenarios ya resueltos."""
    base = resumen_flujo(flujo_base, "Base", es_base=True)
    filas = [base]
    detalles = []
    for esc in escenarios or []:
        if "resumen" in esc:
            fila = copy.deepcopy(esc["resumen"])
            detalles.append({k: copy.deepcopy(v) for k, v in esc.items() if k != "flujo"})
        else:
            resuelto = resolver_escenario(flujo_base, esc.get("cambios") or [], esc.get("nombre") or "Escenario")
            fila = copy.deepcopy(resuelto["resumen"])
            detalles.append({k: copy.deepcopy(v) for k, v in resuelto.items() if k != "flujo"})
        fila["delta_principal_pct"] = _delta_pct(fila.get("principal_valor"), base.get("principal_valor"))
        fila["delta_Q_pct"] = _delta_pct(fila.get("Q_m3s"), base.get("Q_m3s"))
        fila["delta_hL_pct"] = _delta_pct(fila.get("hL_total_m"), base.get("hL_total_m"))
        fila["delta_Vmax_pct"] = _delta_pct(fila.get("V_max_ms"), base.get("V_max_ms"))
        filas.append(fila)

    base["delta_principal_pct"] = 0.0
    base["delta_Q_pct"] = 0.0
    base["delta_hL_pct"] = 0.0
    base["delta_Vmax_pct"] = 0.0
    return {
        "version": VERSION_COMPARADOR,
        "firma_base": firma_base(flujo_base),
        "clase": str((flujo_base or {}).get("clase") or ""),
        "filas": filas,
        "escenarios": detalles,
        "cantidad_escenarios": len(filas) - 1,
        "nota": "Las diferencias porcentuales se calculan contra el escenario base confirmado V14.7.",
    }


def filas_para_tabla(comparacion: dict) -> list[dict]:
    out = []
    for f in (comparacion or {}).get("filas") or []:
        out.append({
            "Escenario": f.get("nombre"),
            "Estado": f.get("estado_integral"),
            "Resultado": f.get("principal_valor"),
            "Unidad": f.get("principal_unidad"),
            "Δ resultado (%)": f.get("delta_principal_pct"),
            "Q (m³/s)": f.get("Q_m3s"),
            "Δ Q (%)": f.get("delta_Q_pct"),
            "hL (m)": f.get("hL_total_m"),
            "Δ hL (%)": f.get("delta_hL_pct"),
            "V máx (m/s)": f.get("V_max_ms"),
            "Δ Vmáx (%)": f.get("delta_Vmax_pct"),
            "Re mín": f.get("Re_min"),
            "Re máx": f.get("Re_max"),
            "P bomba hid. (kW)": f.get("potencia_bomba_hidraulica_kW"),
            "Margen P (kPa)": f.get("margen_presion_kPa"),
        })
    return out


def reporte_json(comparacion: dict) -> str:
    return json.dumps(comparacion, ensure_ascii=False, indent=2, default=str)


def reporte_csv(comparacion: dict) -> str:
    filas = filas_para_tabla(comparacion)
    if not filas:
        return ""
    s = io.StringIO()
    w = csv.DictWriter(s, fieldnames=list(filas[0].keys()))
    w.writeheader(); w.writerows(filas)
    return s.getvalue()


def _fmt(v, n=6):
    if v is None:
        return "—"
    if _finito(v):
        return f"{float(v):.{n}g}"
    return str(v)


def reporte_markdown(comparacion: dict) -> str:
    filas = filas_para_tabla(comparacion)
    lines = [
        "# Comparador de escenarios hidráulicos — V14.20",
        "",
        f"- Clase: **{comparacion.get('clase','—')}**",
        f"- Escenarios alternativos: **{comparacion.get('cantidad_escenarios',0)}**",
        f"- Firma base: `{str(comparacion.get('firma_base',''))[:12]}`",
        "",
        "| Escenario | Estado | Resultado | Δ resultado | Q (m³/s) | hL (m) | V máx (m/s) |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for f in (comparacion.get("filas") or []):
        pv = _fmt(f.get("principal_valor"))
        pu = f.get("principal_unidad") or ""
        delta = _fmt(f.get("delta_principal_pct"), 5)
        if delta != "—": delta += " %"
        lines.append(
            f"| {f.get('nombre','—')} | {f.get('estado_integral','—')} | {pv} {pu} | {delta} | "
            f"{_fmt(f.get('Q_m3s'))} | {_fmt(f.get('hL_total_m'))} | {_fmt(f.get('V_max_ms'))} |"
        )
    lines += ["", "## Cambios por escenario", ""]
    for esc in comparacion.get("escenarios") or []:
        lines.append(f"### {esc.get('nombre','Escenario')}")
        for c in esc.get("cambios") or []:
            tramo = f" · tramo {c.get('tramo')}" if c.get("tramo") else ""
            lines.append(f"- `{c.get('campo')}`{tramo}: `{c.get('anterior')}` → `{c.get('valor')}`")
        lines.append("")
    lines.append("> V14.20 compara variantes explícitas. No modifica el escenario base ni cambia silenciosamente la clase hidráulica.")
    return "\n".join(lines)
