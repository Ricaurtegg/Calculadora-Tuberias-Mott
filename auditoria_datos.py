import re
import unicodedata


def _norm(texto):
    texto = unicodedata.normalize("NFD", str(texto or ""))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto.lower().replace(",", ".")


def _estado(etiqueta, valor, estado, detalle):
    return {"Dato": etiqueta, "Valor interpretado": valor, "Estado": estado, "Detalle": detalle}


def construir_auditoria_datos(prefill, enunciado=""):
    """Crea una auditoría de procedencia/confianza sin modificar el parser hidráulico."""
    prefill = prefill or {}
    filas = []

    directos = [
        ("Caudal Q", "Q_m3s", "m³/s"),
        ("P1", "P1_kpa", "kPa"),
        ("P2", "P2_kpa", "kPa"),
        ("hA", "hA_m", "m"),
        ("hR", "hR_m", "m"),
    ]
    for etiqueta, clave, unidad in directos:
        valor = prefill.get(clave)
        if valor is not None:
            filas.append(_estado(etiqueta, f"{float(valor):.8g} {unidad}", "✅ Alta", "Valor explícito reconocido y convertido a SI."))

    eventos = prefill.get("geometria_vertical_eventos") or []
    z1 = prefill.get("z1_m")
    z2 = prefill.get("z2_m")
    for etiqueta, valor, idx in (("z1", z1, 0), ("z2", z2, 2)):
        if valor is None:
            continue
        inferido = any("interpolada" in e.lower() for e in eventos)
        datum = any("datum" in a.lower() for a in (prefill.get("advertencias") or [])) and etiqueta == "z1"
        if datum:
            filas.append(_estado(etiqueta, f"{float(valor):.8g} m", "🟡 Inferido", "Se adoptó como datum de referencia por falta de cota absoluta."))
        elif inferido and etiqueta in ("z1", "z2"):
            filas.append(_estado(etiqueta, f"{float(valor):.8g} m", "✅ Alta", "Extremo reconocido; las uniones internas pueden haber sido interpoladas."))
        else:
            filas.append(_estado(etiqueta, f"{float(valor):.8g} m", "✅ Alta", "Cota absoluta o relación geométrica resuelta de forma consistente."))

    fluido = prefill.get("fluido_detectado")
    if fluido:
        temp = prefill.get("temperatura_c")
        val = fluido + (f" a {float(temp):g} °C" if temp is not None else "")
        filas.append(_estado("Fluido", val, "✅ Alta" if temp is not None else "🟡 Inferido", "Fluido reconocido en el enunciado." + (" Temperatura explícita." if temp is not None else " Temperatura no explícita; revise la selección final.")))

    for i, tramo in enumerate(prefill.get("tramos") or [], 1):
        L = tramo.get("L_m")
        D = tramo.get("D_m")
        mat = tramo.get("material")
        if L is not None:
            filas.append(_estado(f"Tramo {i} — L", f"{float(L):.8g} m", "✅ Alta", "Longitud explícita convertida a SI."))
        else:
            filas.append(_estado(f"Tramo {i} — L", "—", "⚠️ Confirmar", "No se reconoció longitud para este tramo."))
        if D is not None:
            filas.append(_estado(f"Tramo {i} — D", f"{float(D):.8g} m", "✅ Alta", "Diámetro explícito convertido a SI."))
        else:
            filas.append(_estado(f"Tramo {i} — D", "—", "⚠️ Confirmar", "No se reconoció diámetro para este tramo."))
        if mat:
            filas.append(_estado(f"Tramo {i} — material", str(mat), "✅ Alta", "Material reconocido por nombre/sinónimo del catálogo."))
        else:
            filas.append(_estado(f"Tramo {i} — material", "—", "⚠️ Confirmar", "No se reconoció material/rugosidad."))

        for acc in tramo.get("accesorios") or []:
            nombre = acc.get("nombre", "Accesorio")
            pos = acc.get("posiciones_fraccion") or []
            detalle = f"Cantidad detectada: {int(acc.get('cantidad', 1) or 1)}."
            if pos:
                detalle += " Posición(es) reconocida(s)."
            filas.append(_estado(f"Tramo {i} — {nombre}", detalle, "✅ Alta", "Tipo de accesorio reconocido; K se obtiene del catálogo correspondiente."))

        for comp in tramo.get("componentes_graficos") or []:
            filas.append(_estado(f"Tramo {i} — {comp.get('nombre', 'Válvula genérica')}", "Tipo/K no definido", "⚠️ Confirmar", "Se reconoció la posición, pero no hay información suficiente para asignar K sin inventarlo."))

    for j, trans in enumerate(prefill.get("transiciones") or [], 1):
        tipo = trans.get("tipo")
        if tipo:
            filas.append(_estado(f"Transición {j}", str(tipo), "✅ Alta", "Tipo de transición reconocido explícitamente en el enunciado."))
        else:
            filas.append(_estado(f"Transición {j}", "Cambio de diámetro", "⚠️ Confirmar", "Existe cambio geométrico, pero falta confirmar si es súbito, gradual o sin pérdida adicional."))

    # Conflictos numéricos explícitos sencillos: P1/P2/z1/z2 con dos valores distintos.
    t = _norm(enunciado)
    patrones = {
        "P1": r"\bp\s*1\s*(?:=|:)?\s*(-?\d+(?:\.\d+)?)\s*(kpa|mpa|pa|psi)\b",
        "P2": r"\bp\s*2\s*(?:=|:)?\s*(-?\d+(?:\.\d+)?)\s*(kpa|mpa|pa|psi)\b",
        "z1": r"\bz\s*1\s*(?:=|:)?\s*(-?\d+(?:\.\d+)?)\s*(m|ft|pie|pies|cm|mm)\b",
        "z2": r"\bz\s*2\s*(?:=|:)?\s*(-?\d+(?:\.\d+)?)\s*(m|ft|pie|pies|cm|mm)\b",
    }
    for nombre, patron in patrones.items():
        vals = re.findall(patron, t)
        unicos = {(v, u) for v, u in vals}
        if len(unicos) > 1:
            filas.append(_estado(nombre, "; ".join(f"{v} {u}" for v, u in sorted(unicos)), "❌ Conflicto", "Se encontraron varios valores explícitos distintos para la misma variable. Confirme el correcto antes de resolver."))

    return filas


def hay_conflictos_bloqueantes(filas):
    return any(str(f.get("Estado", "")).startswith("❌") for f in filas or [])
