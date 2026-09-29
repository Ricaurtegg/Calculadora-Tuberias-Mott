"""V14.13 — interpretación avanzada de accesorios y transiciones.

Esta capa complementa el parser histórico sin reemplazar el solver hidráulico.
Objetivos:
- reconocer redacciones naturales adicionales de accesorios de Mott;
- asociar accesorios al tramo correcto cuando el texto lo indica;
- documentar si K se obtiene de K fijo o de K=fT(Le/D);
- crear una transición pendiente siempre que D cambie entre tramos;
- distinguir súbita/gradual cuando el enunciado lo soporta y NO inventar el ángulo.
"""
from __future__ import annotations

import copy
import re
import unicodedata
from typing import Any

from catalogos_mott import ACCESORIOS
from transiciones_mott import (
    TIPO_SIN,
    TIPO_EXP_SUD,
    TIPO_EXP_GRAD,
    TIPO_CON_SUD,
    TIPO_CON_GRAD,
)

VERSION_COMPONENTES = "V14.13"


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFD", str(texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = t.replace("º", "°")
    return re.sub(r"\s+", " ", t).strip()


def _numero(txt: str) -> float:
    return float(str(txt).replace(",", "."))


def _cantidad(prefijo: str) -> int:
    m = re.search(r"(?:^|\s)(\d+|un|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|one|two|three|four|five|six|seven|eight|nine|ten)\s*$", prefijo[-36:])
    if not m:
        return 1
    v = m.group(1)
    if v.isdigit():
        return max(1, int(v))
    mapa = {"un":1,"una":1,"uno":1,"dos":2,"tres":3,"cuatro":4,"cinco":5,"seis":6,"siete":7,"ocho":8,"nueve":9,"diez":10,
            "one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10}
    return mapa.get(v, 1)


def _metodo_catalogo(nombre: str) -> dict[str, Any]:
    info = ACCESORIOS.get(nombre) or {}
    modelo = info.get("modelo")
    if modelo == "k_fijo":
        return {
            "modelo_k": "K fijo",
            "metodo_k": "K directo de Mott",
            "fuente_k": info.get("fuente"),
            "k_catalogo": info.get("k"),
        }
    if modelo == "mott_le_d":
        return {
            "modelo_k": "Le/D × fT",
            "metodo_k": "K = fT(Le/D)",
            "fuente_k": info.get("fuente"),
            "le_d": info.get("le_d"),
        }
    if modelo == "mott_butterfly":
        return {
            "modelo_k": "Le/D × fT por rango de DN",
            "metodo_k": "K = fT(Le/D), mariposa según tamaño",
            "fuente_k": info.get("fuente"),
        }
    return {"modelo_k": modelo or "desconocido", "metodo_k": "Confirmar", "fuente_k": info.get("fuente")}


# Patrones adicionales/específicos. Se evalúan de arriba a abajo.
_PATRONES_ACCESORIOS = [
    # Compuerta con apertura expresada de formas naturales.
    (r"valvul[ae]s?\s+(?:de\s+)?compuerta[^.\n]{0,35}(?:25\s*%|un\s+cuarto|1\s*/\s*4)[^.\n]{0,15}(?:abiert[ao]s?)?", "Válvula de compuerta — 1/4 abierta"),
    (r"valvul[ae]s?\s+(?:de\s+)?compuerta[^.\n]{0,35}(?:50\s*%|a\s+la\s+mitad|media|1\s*/\s*2)[^.\n]{0,15}(?:abiert[ao]s?)?", "Válvula de compuerta — 1/2 abierta"),
    (r"valvul[ae]s?\s+(?:de\s+)?compuerta[^.\n]{0,35}(?:75\s*%|tres\s+cuartos|3\s*/\s*4)[^.\n]{0,15}(?:abiert[ao]s?)?", "Válvula de compuerta — 3/4 abierta"),
    (r"valvul[ae]s?\s+(?:de\s+)?compuerta[^.\n]{0,35}(?:totalmente|completamente|100\s*%)\s+abiert[ao]s?", "Válvula de compuerta — totalmente abierta"),
    # Mariposa: solo se asigna el valor Mott si el estado totalmente abierto es explícito.
    (r"valvul[ae]s?\s+(?:de\s+)?mariposa[^.\n]{0,35}(?:totalmente|completamente|100\s*%)\s+abiert[ao]s?", "Válvula mariposa — totalmente abierta"),
    (r"(?:fully|completely)\s+open(?:ed)?\s+butterfly\s+valve", "Válvula mariposa — totalmente abierta"),
    (r"butterfly\s+valve[^.\n]{0,30}(?:fully|completely|100\s*%)\s+open(?:ed)?", "Válvula mariposa — totalmente abierta"),
    # Codos y retornos.
    (r"codos?[^.\n]{0,18}(?:90\s*°?|90\s*grados?)[^.\n]{0,30}(?:radio\s+largo|long\s+radius|r\s*/\s*d\s*(?:>=|>|=)?\s*1(?:\.5)?)", "Codo 90° radio largo"),
    (r"codos?[^.\n]{0,18}(?:90\s*°?|90\s*grados?)[^.\n]{0,25}(?:street|calle|rosca\s+hembra\s*-?\s*macho)", "Codo 90° tipo street"),
    (r"codos?[^.\n]{0,18}(?:45\s*°?|45\s*grados?)[^.\n]{0,25}(?:street|calle)", "Codo 45° tipo street"),
    (r"(?:codos?\s+(?:estandar|standard)|standard\s+elbows?)", "Codo 90° estándar"),
    (r"(?:retorno|curva\s+en\s+u|u\s*-?\s*bend)[^.\n]{0,25}(?:180\s*°?|cerrad[oa])", "Retorno cerrado 180°"),
    # Tee con vocabulario alternativo.
    (r"tees?[^.\n]{0,30}(?:paso\s+recto|linea\s+principal|flujo\s+recto|through\s+run|run)", "Tee estándar — paso recto"),
    (r"tees?[^.\n]{0,30}(?:ramal|derivacion|salida\s+lateral|branch)", "Tee estándar — flujo por ramal"),
    # Entradas/salidas con sinónimos.
    (r"entrada[^.\n]{0,35}(?:arista\s+viva|borde\s+vivo|borde\s+agudo|borde\s+cuadrado)", "Entrada — borde cuadrado/agudo"),
    (r"entrada[^.\n]{0,35}(?:chaflan|achaflanad|biselad)", "Entrada — achaflanada"),
    (r"(?:descarga|salida)[^.\n]{0,35}(?:deposito\s+grande|reservorio\s+grande|tanque\s+grande)", "Salida hacia depósito grande"),
]


def _tramo_explicito(ctx: str) -> int | None:
    patrones = [
        r"(?:en|del|dentro\s+del)\s+tramo\s*(\d+)",
        r"tramo\s*(\d+)[^.\n]{0,45}(?:contiene|incluye|tiene|posee|hay)",
    ]
    for p in patrones:
        m = re.search(p, ctx)
        if m:
            return int(m.group(1))
    return None


def _tramo_relacional(texto: str, a: int, b: int) -> int | None:
    # Mira alrededor del accesorio. "antes del tramo 3" se asigna al final del 2;
    # "después del tramo 1" al inicio del 2, salvo que solo exista un tramo.
    ctx = texto[max(0, a-80):min(len(texto), b+100)]
    n = _tramo_explicito(ctx)
    if n is not None:
        return n
    m = re.search(r"antes\s+(?:de|del)\s+tramo\s*(\d+)", ctx)
    if m:
        return max(1, int(m.group(1)) - 1)
    m = re.search(r"despues\s+(?:de|del)\s+tramo\s*(\d+)", ctx)
    if m:
        return int(m.group(1)) + 1
    return None


def detectar_accesorios_avanzados(texto_original: str, tramos: list[dict] | None = None) -> list[dict]:
    texto = _norm(texto_original)
    tramos = list(tramos or [])
    out: list[dict] = []
    usados: list[tuple[int,int]] = []

    for patron, nombre in _PATRONES_ACCESORIOS:
        for m in re.finditer(patron, texto):
            a,b = m.span()
            if any(not (b <= x1 or a >= x2) for x1,x2 in usados):
                continue
            cant = _cantidad(texto[:a])
            # OCR/diagramas suelen escribir "Standard elbows (2)"; el número
            # pospuesto debe prevalecer sobre la cantidad por defecto.
            msuf = re.match(r"\s*\(\s*(\d+)\s*\)", texto[b:b+16])
            if msuf:
                cant = max(1, int(msuf.group(1)))
            tramo = _tramo_relacional(texto, a, b)
            if tramo is None and len(tramos) == 1:
                tramo = int(tramos[0].get("numero", 1) or 1)
            reg = {
                "nombre": nombre,
                "cantidad": cant,
                "tramo": tramo,
                "original": m.group(0),
                "confianza": 97.0 if tramo is not None else 92.0,
                "estado": "Alta" if tramo is not None else "Confirmar tramo",
                **_metodo_catalogo(nombre),
            }
            out.append(reg)
            usados.append((a,b))

    # Mariposa sin apertura explícita: no asumir totalmente abierta.
    for m in re.finditer(r"valvul[ae]s?\s+(?:de\s+)?mariposa", texto):
        a,b = m.span()
        if any(x1 <= a < x2 for x1,x2 in usados):
            continue
        ctx = texto[max(0,a-20):min(len(texto),b+60)]
        if re.search(r"(?:totalmente|completamente|100\s*%)\s+abiert", ctx):
            continue
        tramo = _tramo_relacional(texto, a, b)
        if tramo is None and len(tramos) == 1:
            tramo = int(tramos[0].get("numero", 1) or 1)
        out.append({
            "nombre": "Válvula mariposa (apertura por definir)",
            "cantidad": _cantidad(texto[:a]),
            "tramo": tramo,
            "original": m.group(0),
            "confianza": 70.0,
            "estado": "Confirmar",
            "modelo_k": "pendiente",
            "metodo_k": "No se asigna K sin conocer apertura/condición",
            "requiere_confirmacion": True,
        })
    return out


def _extraer_angulo(ctx: str) -> float | None:
    pats = [
        r"(?:angulo(?:\s+incluido|\s+del\s+cono)?|cono)\s*(?:de|=|:)?\s*(\d+(?:[\.,]\d+)?)\s*(?:°|grados?)",
        r"(\d+(?:[\.,]\d+)?)\s*(?:°|grados?)[^.\n]{0,20}(?:incluido|de\s+cono|del\s+cono)",
    ]
    for p in pats:
        m = re.search(p, ctx)
        if m:
            return _numero(m.group(1))
    return None


def _tipo_transicion(ctx: str, d1: float, d2: float) -> tuple[str | None, str]:
    crece = d2 > d1
    # V15.0: un enunciado patrón puede declarar explícitamente que el cambio
    # de diámetro se modela sin pérdida adicional. No debe volver a preguntarse.
    if re.search(r"(?:sin\s+perdida(?:s)?\s+adicional(?:es)?|union\s+ideal|conexi[oó]n\s+ideal)", ctx):
        return TIPO_SIN, "explícita sin pérdida adicional / unión ideal"
    if re.search(r"(?:subit|brusc|abrupt|repentin|escalon)", ctx):
        return (TIPO_EXP_SUD if crece else TIPO_CON_SUD), "explícita súbita/brusca"
    if re.search(r"(?:gradual|conic|difusor|reductor\s+conic|cono)", ctx):
        return (TIPO_EXP_GRAD if crece else TIPO_CON_GRAD), "explícita gradual/cónica"
    # Palabras de geometría sin especificar cómo ocurre: no inventar K.
    if re.search(r"(?:reduccion|reductor|contraccion|expansion|ensanchamiento|cambio\s+de\s+diametro|pasa\s+de|cambia\s+de)", ctx):
        return None, "cambio de sección detectado; tipo no especificado"
    return None, "D1≠D2; tipo de transición no especificado"


def _contexto_frontera(texto: str, n1: int, n2: int) -> str:
    # Busca fragmentos con ambos tramos; si no, usa ventanas alrededor de la marca del tramo siguiente.
    m2 = re.search(rf"\btramo\s*{n2}\b", texto)
    if m2:
        return texto[max(0,m2.start()-180):min(len(texto),m2.end()+180)]
    return texto


def detectar_transiciones_avanzadas(texto_original: str, tramos: list[dict]) -> list[dict]:
    texto = _norm(texto_original)
    out = []
    if len(tramos or []) < 2:
        return out
    for idx in range(1, len(tramos)):
        t1, t2 = tramos[idx-1], tramos[idx]
        d1 = t1.get("D_m") if t1.get("D_m") is not None else t1.get("D")
        d2 = t2.get("D_m") if t2.get("D_m") is not None else t2.get("D")
        if d1 is None or d2 is None:
            continue
        d1,d2 = float(d1),float(d2)
        if abs(d1-d2) < 1e-12:
            continue
        n1 = int(t1.get("numero", idx) or idx)
        n2 = int(t2.get("numero", idx+1) or idx+1)
        ctx = _contexto_frontera(texto, n1, n2)
        tipo, razon = _tipo_transicion(ctx, d1, d2)
        ang = _extraer_angulo(ctx) if tipo in {TIPO_EXP_GRAD, TIPO_CON_GRAD} else None
        estado = "Alta"
        confianza = 96.0
        requiere = False
        if tipo is None:
            estado, confianza, requiere = "Confirmar", 75.0, True
        elif tipo in {TIPO_EXP_GRAD, TIPO_CON_GRAD} and ang is None:
            estado, confianza, requiere = "Confirmar ángulo", 85.0, True
        out.append({
            "entre": idx,
            "tipo": tipo,
            "angulo_grados": ang,
            "D1_m": d1,
            "D2_m": d2,
            "direccion": "expansión" if d2>d1 else "contracción",
            "estado": estado,
            "confianza": confianza,
            "requiere_confirmacion": requiere,
            "detalle_v1413": razon,
            "fuente_v1413": "Mott 7e — Cap. 10 / geometría D1→D2",
        })
    return out


def analizar_componentes_v1413(texto_original: str, tramos: list[dict] | None = None) -> dict:
    tramos = copy.deepcopy(list(tramos or []))
    acc = detectar_accesorios_avanzados(texto_original, tramos)
    trans = detectar_transiciones_avanzadas(texto_original, tramos)
    advertencias = []
    if any(a.get("requiere_confirmacion") for a in acc):
        advertencias.append("V14.13 detectó accesorios cuya condición no permite asignar K sin confirmación.")
    if any(t.get("requiere_confirmacion") for t in trans):
        advertencias.append("V14.13 detectó cambios de diámetro que requieren confirmar tipo y/o ángulo de transición.")
    return {
        "version": VERSION_COMPONENTES,
        "accesorios": acc,
        "transiciones": trans,
        "advertencias": advertencias,
    }


def _tramo_por_numero(tramos: list[dict], numero: int | None):
    if numero is None:
        return None
    return next((t for t in tramos if int(t.get("numero", 0) or 0) == int(numero)), None)


def fusionar_prefill_v1413(prefill: dict, analisis: dict) -> dict:
    out = copy.deepcopy(prefill or {})
    analisis = copy.deepcopy(analisis or {})
    tramos = out.setdefault("tramos", [])
    eventos = []
    pendientes = out.setdefault("componentes_pendientes_v1413", [])

    for a in analisis.get("accesorios") or []:
        if a.get("requiere_confirmacion"):
            # No convertir una mariposa sin estado de apertura en totalmente abierta.
            # El parser histórico podía haberla interpretado así; V14.13 retira esa
            # suposición antes de mandar el caso a confirmación.
            if "mariposa" in str(a.get("nombre", "")).lower():
                for tr in tramos:
                    accs = list(tr.get("accesorios") or [])
                    tr["accesorios"] = [x for x in accs if x.get("nombre") != "Válvula mariposa — totalmente abierta"]
            registro = copy.deepcopy(a)
            if not any(p.get("original") == registro.get("original") and p.get("tramo") == registro.get("tramo") for p in pendientes):
                pendientes.append(registro)
            eventos.append({"tipo":"accesorio_pendiente","original":a.get("original"),"detalle":a.get("metodo_k"),"tramo":a.get("tramo")})
            continue
        tramo = _tramo_por_numero(tramos, a.get("tramo"))
        if tramo is None:
            # Si solo hay un tramo, es inequívoco. En múltiples tramos sin pista no se mueve.
            if len(tramos) == 1:
                tramo = tramos[0]
            else:
                continue
        accesorios = tramo.setdefault("accesorios", [])
        # Si V14.13 encontró una apertura parcial explícita de compuerta, elimina
        # la interpretación genérica "totalmente abierta" que podía haber creado
        # la capa histórica y conserva, si existían, sus posiciones gráficas.
        posiciones_heredadas = []
        if str(a.get("nombre", "")).startswith("Válvula de compuerta —") and a.get("nombre") != "Válvula de compuerta — totalmente abierta":
            nuevos = []
            for viejo in accesorios:
                if viejo.get("nombre") == "Válvula de compuerta — totalmente abierta":
                    posiciones_heredadas.extend(viejo.get("posiciones_fraccion") or [])
                    if viejo.get("posicion_fraccion") is not None:
                        posiciones_heredadas.append(viejo.get("posicion_fraccion"))
                    continue
                nuevos.append(viejo)
            tramo["accesorios"] = accesorios = nuevos
        ex = next((x for x in accesorios if x.get("nombre") == a.get("nombre")), None)
        if ex is None:
            ex = {"nombre":a.get("nombre"),"cantidad":int(a.get("cantidad",1) or 1)}
            accesorios.append(ex)
        if posiciones_heredadas and not ex.get("posiciones_fraccion"):
            ex["posiciones_fraccion"] = sorted({float(x) for x in posiciones_heredadas if x is not None})
            if ex["posiciones_fraccion"]:
                ex["posicion_fraccion"] = ex["posiciones_fraccion"][0]
        else:
            ex["cantidad"] = max(int(ex.get("cantidad",1) or 1), int(a.get("cantidad",1) or 1))
        ex["metodo_k_v1413"] = a.get("metodo_k")
        ex["modelo_k_v1413"] = a.get("modelo_k")
        ex["fuente_k_v1413"] = a.get("fuente_k")
        ex["confianza_v1413"] = a.get("confianza")
        eventos.append({"tipo":"accesorio","original":a.get("original"),"detalle":a.get("metodo_k"),"tramo":tramo.get("numero")})

    # Las transiciones avanzadas reemplazan/completean las históricas por frontera.
    trans_out = list(out.get("transiciones") or [])
    for t in analisis.get("transiciones") or []:
        entre = int(t.get("entre"))
        ex = next((x for x in trans_out if int(x.get("entre",-1)) == entre), None)
        if ex is None:
            ex = {"entre":entre,"tipo":None,"angulo_grados":None}
            trans_out.append(ex)
        # Solo completa; no pisa una detección histórica explícita distinta.
        if ex.get("tipo") is None and t.get("tipo") is not None:
            ex["tipo"] = t.get("tipo")
        if ex.get("angulo_grados") is None and t.get("angulo_grados") is not None:
            ex["angulo_grados"] = t.get("angulo_grados")
        ex["estado_v1413"] = t.get("estado")
        ex["confianza_v1413"] = t.get("confianza")
        ex["detalle_v1413"] = t.get("detalle_v1413")
        ex["fuente_v1413"] = t.get("fuente_v1413")
        eventos.append({"tipo":"transicion","entre":entre,"detalle":t.get("detalle_v1413"),"estado":t.get("estado")})
    trans_out.sort(key=lambda x:int(x.get("entre",0) or 0))
    out["transiciones"] = trans_out

    out["interpretacion_componentes_v1413"] = {
        "version": VERSION_COMPONENTES,
        "eventos": eventos,
        "advertencias": list(analisis.get("advertencias") or []),
    }
    adv = list(out.get("advertencias") or [])
    adv.extend(analisis.get("advertencias") or [])
    out["advertencias"] = list(dict.fromkeys(adv))
    return out
