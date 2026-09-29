"""Confianza heurística individual por dato — V14.11.

Esta capa no modifica los valores hidráulicos ni los solvers. Evalúa la
procedencia de cada dato consolidado y asigna una confianza heurística
individual (0–100) para priorizar la revisión humana.

Reglas generales:
- respuestas explícitas V14.6: 100 %;
- inferencias físicamente seguras V14.5: 99 %;
- texto escrito/pegado por el usuario: 98 %;
- TXT/DOCX/PDF con extracción directa: 97 %;
- OCR sin edición posterior: 86 % (requiere confirmación V14.11);
- OCR editado/revisado por el usuario: 94 %;
- valor completado únicamente desde figura confirmada: usa la confianza del
  hallazgo visual, limitada de forma conservadora;
- discrepancias explícitas texto/figura reducen la confianza y obligan a revisar.

Los porcentajes son indicadores heurísticos de revisión, no probabilidades
estadísticas calibradas.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any

from clasificar_problema import extraer_datos_estructurados
from consolidacion_datos import consolidar_resultado

VERSION_CONFIANZA = "V14.11"
UMBRAL_ALTA = 90.0
UMBRAL_MEDIA = 75.0


_ETIQUETAS = {
    "Q_m3s": ("Caudal Q", "m³/s"),
    "P1_kpa": ("Presión P1", "kPa"),
    "P2_kpa": ("Presión P2", "kPa"),
    "z1_m": ("Elevación z1", "m"),
    "z2_m": ("Elevación z2", "m"),
    "hA_m": ("Carga de bomba hA", "m"),
    "hR_m": ("Carga de turbina hR", "m"),
    "temperatura_c": ("Temperatura del fluido", "°C"),
}

_FIGURA_TIPO = {
    "P1_kpa": "P1",
    "P2_kpa": "P2",
    "z1_m": "z1",
    "z2_m": "z2",
    "hA_m": "hA",
    "hR_m": "hR",
    "Q_m3s": "caudal",
}


def _finito(v: Any) -> bool:
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def _igual(a: Any, b: Any, tol: float = 1e-9) -> bool:
    if a is None and b is None:
        return True
    if _finito(a) and _finito(b):
        aa, bb = float(a), float(b)
        ref = max(1.0, abs(aa), abs(bb))
        return abs(aa - bb) <= tol * ref
    return str(a) == str(b)


def _fmt(v: Any, unidad: str = "") -> str:
    if v is None:
        return "—"
    if isinstance(v, str):
        return v
    if _finito(v):
        s = f"{float(v):.8g}"
        return f"{s} {unidad}".strip()
    return str(v)


def _nivel(conf: float) -> str:
    if conf >= UMBRAL_ALTA:
        return "Alta"
    if conf >= UMBRAL_MEDIA:
        return "Media"
    return "Baja"


def _estado(conf: float, confirmado: bool = False, incognita: bool = False) -> str:
    if incognita:
        return "🎯 Incógnita"
    if conf >= UMBRAL_ALTA:
        return "✅ Aceptable"
    if confirmado:
        return "✅ Confirmado por usuario"
    return "⚠️ Confirmar"


def _firma(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _mapa_respuestas(resultado: dict) -> dict:
    out = {}
    for r in (resultado or {}).get("respuestas_v146") or []:
        out[(str(r.get("clave") or ""), r.get("tramo"))] = r
    return out


def _mapa_inferencias(expediente: dict) -> dict:
    return {str(x.get("clave") or ""): x for x in expediente.get("inferencias") or []}


def _hallazgo_mejor(figura: dict | None, tipo: str) -> dict | None:
    hall = [x for x in (figura or {}).get("hallazgos") or [] if str(x.get("tipo")) == tipo]
    if not hall:
        return None
    return max(hall, key=lambda x: float(x.get("confianza", 0) or 0))


def _contexto_base(contexto_lectura: dict | None, enunciado: str) -> tuple[float, str, str]:
    ctx = contexto_lectura or {}
    modo = str(ctx.get("modo_entrada") or "").lower()
    if modo and "subir" not in modo:
        return 98.0, "texto escrito/pegado", "El dato procede del texto revisado en el editor de la aplicación."

    info = ctx.get("archivo_info") or {}
    if not info:
        return 98.0, "texto escrito/pegado", "El dato procede del texto revisado en el editor de la aplicación."

    ocr = bool(info.get("ocr_aplicado"))
    original = str(ctx.get("texto_extraido_original") or "")
    editado = bool(original and str(enunciado or "").strip() != original.strip())
    revisado_explicito = bool(ctx.get("ocr_revisado_explicito"))
    if ocr and revisado_explicito:
        return 94.0, "OCR revisado explícitamente por usuario", "El usuario confirmó que revisó números, unidades y símbolos del texto obtenido por OCR."
    if ocr and editado:
        return 88.0, "OCR editado parcialmente", "El texto OCR fue modificado, pero no se confirmó una revisión completa; V14.11 mantiene la verificación dirigida."
    if ocr:
        return 86.0, "OCR sin revisión explícita", "El valor procede de OCR; V14.11 exige confirmación explícita antes de V14.7."
    return 97.0, "archivo con texto extraído directamente", "El contenido se extrajo sin OCR desde TXT/DOCX/PDF seleccionable."


def _advertencia_conflicto(resultado: dict, clave: str, etiqueta: str) -> str | None:
    tokens = [clave.replace("_kpa", "").replace("_m3s", "").replace("_m", ""), etiqueta]
    for adv in (resultado or {}).get("advertencias") or []:
        t = str(adv).lower()
        if "difier" not in t and "conflict" not in t and "incompat" not in t:
            continue
        if any(str(tok).lower() in t for tok in tokens if tok):
            return str(adv)
    return None


def _entrada(*, ident: str, clave: str, dato: str, valor: Any, unidad: str, conf: float,
             fuente: str, motivo: str, tramo: int | None = None, confirmado: bool = False,
             incognita: bool = False, categoria: str = "general") -> dict:
    conf = max(0.0, min(100.0, float(conf)))
    d = {
        "id": ident,
        "clave": clave,
        "dato": dato,
        "valor": valor,
        "valor_mostrado": "INCÓGNITA" if incognita else _fmt(valor, unidad),
        "unidad": unidad,
        "confianza_pct": round(conf, 1),
        "nivel": "Método" if incognita else _nivel(conf),
        "fuente": fuente,
        "motivo": motivo,
        "requiere_confirmacion": bool((not incognita) and conf < UMBRAL_ALTA),
        "confirmado": bool(confirmado),
        "estado": _estado(conf, confirmado, incognita),
        "categoria": categoria,
    }
    if tramo is not None:
        d["tramo"] = int(tramo)
    return d


def _fuente_para(clave: str, tramo: int | None, valor: Any, *, resultado: dict, expediente: dict,
                  texto_base: dict, figura: dict | None, base_conf: float, base_fuente: str,
                  base_motivo: str) -> tuple[float, str, str]:
    respuestas = _mapa_respuestas(resultado)
    inferencias = _mapa_inferencias(expediente)

    if (clave, tramo) in respuestas:
        return 100.0, "usuario V14.6", "Valor aportado explícitamente por el usuario para resolver un faltante identificado."
    if tramo is None and clave in inferencias:
        inf = inferencias[clave]
        return 99.0, "inferencia segura V14.5", str(inf.get("detalle") or "Inferencia física inequívoca y trazable.")

    # Determina si el parser textual ya tenía el valor. Si no, pero V14.3 lo completó,
    # usa la confianza del hallazgo visual confirmado.
    if tramo is None and clave in _FIGURA_TIPO:
        textual = texto_base.get(clave)
        if textual is None and valor is not None:
            h = _hallazgo_mejor(figura, _FIGURA_TIPO[clave])
            if h:
                conf = min(94.0, max(55.0, float(h.get("confianza", 0) or 0) + 3.0))
                return conf, "figura confirmada V14.3/V14.4", f"Valor completado desde una etiqueta visual confirmada (hallazgo {float(h.get('confianza',0) or 0):.1f} %)."

    if tramo is not None and clave in {"L_m", "D_m"}:
        ttxt = (texto_base.get("tramos") or [])
        cur_txt = next((x for x in ttxt if int(x.get("numero", 0) or 0) == int(tramo)), None)
        textual = cur_txt.get(clave) if cur_txt else None
        if textual is None and valor is not None and int(tramo) == 1:
            h = _hallazgo_mejor(figura, "longitud" if clave == "L_m" else "diametro")
            if h:
                conf = min(94.0, max(55.0, float(h.get("confianza", 0) or 0) + 3.0))
                return conf, "figura confirmada V14.3/V14.4", f"Dato del tramo completado desde figura confirmada (hallazgo {float(h.get('confianza',0) or 0):.1f} %)."

    return base_conf, base_fuente, base_motivo


def construir_confianza_datos(resultado: dict, enunciado: str = "", contexto_lectura: dict | None = None,
                               figura: dict | None = None, confirmados: set[str] | list[str] | None = None) -> dict:
    """Construye el reporte V14.11 sin alterar los valores del expediente."""
    base = consolidar_resultado(copy.deepcopy(resultado or {}), enunciado)
    expediente = base.get("expediente_v145") or {}
    prefill = base.get("prefill") or {}
    inc = {str(x.get("clave") or "") for x in expediente.get("incognitas") or []}
    confirmados = set(confirmados or [])

    try:
        texto_base = extraer_datos_estructurados(enunciado) if str(enunciado or "").strip() else {}
    except Exception:
        texto_base = {}

    base_conf, base_fuente, base_motivo = _contexto_base(contexto_lectura, enunciado)
    entradas = []

    # Fluido. V14.17.7.1 acepta propiedades explícitas ρ/ν aunque OCR no
    # haya reconocido un nombre de fluido del catálogo.
    fluido = prefill.get("fluido_app") or prefill.get("fluido_detectado")
    props_explicitas_ok = False
    try:
        props_explicitas_ok = (
            bool(prefill.get("propiedades_explicitas_v1412"))
            and float(prefill.get("rho_usuario")) > 0
            and float(prefill.get("nu_usuario_m2s")) > 0
        )
    except (TypeError, ValueError):
        props_explicitas_ok = False
    if not fluido and props_explicitas_ok:
        fluido = "Propiedades explícitas (ρ/ν)"

    if fluido:
        conf, fuente, motivo = _fuente_para(
            "fluido_app", None, fluido, resultado=base, expediente=expediente,
            texto_base=texto_base, figura=figura, base_conf=base_conf,
            base_fuente=base_fuente, base_motivo=base_motivo,
        )
        if props_explicitas_ok and not (prefill.get("fluido_app") or prefill.get("fluido_detectado")):
            fuente = "propiedades físicas explícitas"
            motivo = "ρ y ν quedaron definidos por el enunciado (directamente o mediante SG + μ)."
        ident = "general:fluido_app"
        entradas.append(_entrada(ident=ident, clave="fluido_app", dato="Fluido", valor=fluido, unidad="",
                                  conf=conf, fuente=fuente, motivo=motivo, confirmado=ident in confirmados))

    # Escalares generales e incógnitas
    for clave, (etiqueta, unidad) in _ETIQUETAS.items():
        valor = prefill.get(clave)
        if clave in inc:
            entradas.append(_entrada(ident=f"general:{clave}", clave=clave, dato=etiqueta, valor=None,
                                      unidad=unidad, conf=100.0, fuente="incógnita del método",
                                      motivo="El dato se calculará y no debe transferirse como entrada conocida.", incognita=True))
            continue
        if valor is None:
            continue
        conf, fuente, motivo = _fuente_para(
            clave, None, valor, resultado=base, expediente=expediente, texto_base=texto_base,
            figura=figura, base_conf=base_conf, base_fuente=base_fuente, base_motivo=base_motivo,
        )
        conflicto = _advertencia_conflicto(base, clave, etiqueta)
        if conflicto:
            conf = min(conf, 68.0)
            fuente = f"{fuente} · discrepancia detectada"
            motivo = conflicto
        ident = f"general:{clave}"
        entradas.append(_entrada(ident=ident, clave=clave, dato=etiqueta, valor=valor, unidad=unidad,
                                  conf=conf, fuente=fuente, motivo=motivo, confirmado=ident in confirmados))

    # Tramos
    respuestas = _mapa_respuestas(base)
    for i, t in enumerate(prefill.get("tramos") or [], 1):
        n = int(t.get("numero", i) or i)
        for clave, etiqueta, unidad in (("L_m", "Longitud L", "m"), ("D_m", "Diámetro D", "m")):
            if clave == "D_m" and clave in inc:
                entradas.append(_entrada(ident=f"tramo:{n}:{clave}", clave=clave,
                                          dato=f"Tramo {n} — {etiqueta}", valor=None, unidad=unidad,
                                          conf=100.0, fuente="incógnita del método",
                                          motivo="El diámetro es la incógnita propia de Clase III-A.", tramo=n,
                                          incognita=True, categoria="tramo"))
                continue
            valor = t.get(clave)
            if valor is None:
                continue
            conf, fuente, motivo = _fuente_para(
                clave, n, valor, resultado=base, expediente=expediente, texto_base=texto_base,
                figura=figura, base_conf=base_conf, base_fuente=base_fuente, base_motivo=base_motivo,
            )
            ident = f"tramo:{n}:{clave}"
            entradas.append(_entrada(ident=ident, clave=clave, dato=f"Tramo {n} — {etiqueta}",
                                      valor=valor, unidad=unidad, conf=conf, fuente=fuente, motivo=motivo,
                                      tramo=n, confirmado=ident in confirmados, categoria="tramo"))

        mat = t.get("material")
        if mat:
            if ("material", n) in respuestas:
                conf, fuente, motivo = 100.0, "usuario V14.6", "Material seleccionado explícitamente por el usuario."
            else:
                conf, fuente, motivo = base_conf, base_fuente, base_motivo
            ident = f"tramo:{n}:material"
            entradas.append(_entrada(ident=ident, clave="material", dato=f"Tramo {n} — material",
                                      valor=mat, unidad="", conf=conf, fuente=fuente, motivo=motivo,
                                      tramo=n, confirmado=ident in confirmados, categoria="tramo"))

        # Accesorios: una fila por tipo reconocido. Los resueltos desde símbolos V14.6 quedan al 100 %.
        for j, acc in enumerate(t.get("accesorios") or [], 1):
            nombre = str(acc.get("nombre") or "Accesorio")
            cant = int(acc.get("cantidad", 1) or 1)
            fue_usuario = any(
                str(r.get("clave") or "").startswith("componente_grafico_")
                and int(r.get("tramo") or 0) == n
                and isinstance(r.get("respuesta"), dict)
                and r.get("respuesta", {}).get("modo") == "accesorio"
                and r.get("respuesta", {}).get("nombre") == nombre
                for r in (base.get("respuestas_v146") or [])
            )
            if fue_usuario:
                conf, fuente, motivo = 100.0, "usuario V14.6", "Símbolo/componente confirmado explícitamente como accesorio del catálogo Mott."
            else:
                conf = max(75.0, base_conf - (4.0 if "ocr" in base_fuente.lower() else 2.0))
                fuente = base_fuente
                motivo = "Accesorio reconocido por el parser del enunciado."
            ident = f"tramo:{n}:accesorio:{j}:{nombre}"
            entradas.append(_entrada(ident=ident, clave="accesorio", dato=f"Tramo {n} — accesorio",
                                      valor=f"{cant}× {nombre}", unidad="", conf=conf, fuente=fuente,
                                      motivo=motivo, tramo=n, confirmado=ident in confirmados, categoria="accesorio"))

        if t.get("K_extra") is not None:
            fue_usuario = any(
                str(r.get("clave") or "").startswith("componente_grafico_")
                and int(r.get("tramo") or 0) == n
                and isinstance(r.get("respuesta"), dict)
                and r.get("respuesta", {}).get("modo") == "k_manual"
                for r in (base.get("respuestas_v146") or [])
            )
            conf, fuente, motivo = (
                (100.0, "usuario V14.6", "K adicional introducido explícitamente por el usuario.")
                if fue_usuario else (base_conf, base_fuente, "K adicional reconocido en el enunciado.")
            )
            ident = f"tramo:{n}:K_extra"
            entradas.append(_entrada(ident=ident, clave="K_extra", dato=f"Tramo {n} — K adicional",
                                      valor=t.get("K_extra"), unidad="", conf=conf, fuente=fuente,
                                      motivo=motivo, tramo=n, confirmado=ident in confirmados, categoria="accesorio"))

    # Transiciones
    for j, tr in enumerate(prefill.get("transiciones") or [], 1):
        if not tr.get("tipo"):
            continue
        entre = int(tr.get("entre", j) or j)
        key_resp = f"transicion_{j}"
        if (key_resp, None) in respuestas:
            conf, fuente, motivo = 100.0, "usuario V14.6", "Tipo de transición confirmado explícitamente por el usuario."
        else:
            conf = max(75.0, base_conf - (4.0 if "ocr" in base_fuente.lower() else 2.0))
            fuente = base_fuente
            motivo = "Cambio de sección reconocido por el parser del enunciado."
        ident = f"transicion:{j}"
        entradas.append(_entrada(ident=ident, clave=key_resp,
                                  dato=f"Transición {entre} → {entre + 1}", valor=tr.get("tipo"), unidad="",
                                  conf=conf, fuente=fuente, motivo=motivo, confirmado=ident in confirmados,
                                  categoria="transicion"))

    # Firma basada solo en datos/confianzas, no en confirmaciones actuales.
    firma_payload = [
        {k: x.get(k) for k in ("id", "clave", "tramo", "valor", "unidad", "confianza_pct", "fuente", "requiere_confirmacion")}
        for x in entradas
    ]
    firma = _firma(firma_payload)

    pendientes = [x for x in entradas if x.get("requiere_confirmacion") and not x.get("confirmado")]
    altas = sum(1 for x in entradas if x.get("nivel") == "Alta")
    medias = sum(1 for x in entradas if x.get("nivel") == "Media")
    bajas = sum(1 for x in entradas if x.get("nivel") == "Baja")
    evaluables = [float(x.get("confianza_pct", 0)) for x in entradas if x.get("nivel") != "Método"]

    reporte = {
        "version": VERSION_CONFIANZA,
        "firma": firma,
        "firma_corta": firma[:12],
        "entradas": entradas,
        "cantidad_datos": len(entradas),
        "altas": altas,
        "medias": medias,
        "bajas": bajas,
        "pendientes_confirmacion": len(pendientes),
        "ids_pendientes": [x["id"] for x in pendientes],
        "confianza_min_pct": round(min(evaluables), 1) if evaluables else None,
        "confianza_media_pct": round(sum(evaluables) / len(evaluables), 1) if evaluables else None,
        "listo_para_v147": len(pendientes) == 0,
        "nota": "Confianza heurística para priorizar revisión humana; no es una probabilidad estadística calibrada.",
    }
    return reporte


def aplicar_confirmaciones(reporte: dict, ids_confirmados: set[str] | list[str]) -> dict:
    """Marca confirmaciones explícitas sin cambiar la firma del conjunto de datos."""
    out = copy.deepcopy(reporte or {})
    ids = set(ids_confirmados or [])
    for x in out.get("entradas") or []:
        if x.get("requiere_confirmacion"):
            x["confirmado"] = x.get("id") in ids
            x["estado"] = _estado(float(x.get("confianza_pct", 0)), bool(x["confirmado"]), False)
    pendientes = [x for x in out.get("entradas") or [] if x.get("requiere_confirmacion") and not x.get("confirmado")]
    out["pendientes_confirmacion"] = len(pendientes)
    out["ids_pendientes"] = [x.get("id") for x in pendientes]
    out["listo_para_v147"] = len(pendientes) == 0
    out["confirmados"] = sorted(ids)
    return out


def confirmar_todos_pendientes(reporte: dict) -> dict:
    ids = [x.get("id") for x in (reporte or {}).get("entradas") or [] if x.get("requiere_confirmacion")]
    return aplicar_confirmaciones(reporte, ids)
