import re
import unicodedata

from transiciones_mott import detectar_transiciones_en_texto, detectar_curvas_tuberia

from catalogos_mott import clave_fluido_desde_texto, FLUIDOS
from parser_hidraulico_v1412 import analizar_enunciado_v1412, fusionar_prefill_v1412
from componentes_mott_v1413 import analizar_componentes_v1413, fusionar_prefill_v1413


# ============================================================
# NORMALIZACIÓN
# ============================================================

def normalizar_texto(texto):
    if not texto:
        return ""

    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)

    return "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )


def contiene_alguna(texto, expresiones):
    return any(expresion in texto for expresion in expresiones)


def _numero(texto):
    return float(texto.replace(",", "."))


# ============================================================
# CONVERSIÓN DE UNIDADES A SI
# ============================================================

FACTORES_LONGITUD = {
    "m": 1.0,
    "cm": 0.01,
    "mm": 0.001,
    "ft": 0.3048,
    "pie": 0.3048,
    "pies": 0.3048,
    "in": 0.0254,
    "pulg": 0.0254,
    "pulgada": 0.0254,
    "pulgadas": 0.0254,
}


def convertir_longitud(valor, unidad):
    unidad = unidad.lower()

    if unidad not in FACTORES_LONGITUD:
        raise ValueError(f"Unidad de longitud no reconocida: {unidad}")

    return valor * FACTORES_LONGITUD[unidad]


def convertir_caudal(valor, unidad):
    unidad = (
        unidad.lower()
        .replace(" ", "")
        .replace("³", "3")
        .replace("^", "")
    )

    if unidad == "m3/s":
        return valor

    if unidad in ("l/s", "lps"):
        return valor / 1000.0

    if unidad == "l/min":
        return valor / 60000.0

    if unidad in ("gpm", "gal/min"):
        return valor * 6.30901964e-5

    raise ValueError(f"Unidad de caudal no reconocida: {unidad}")


def convertir_presion_a_kpa(valor, unidad):
    unidad = unidad.lower()

    factores = {
        "pa": 0.001,
        "kpa": 1.0,
        "mpa": 1000.0,
        "psi": 6.894757293,
    }

    if unidad not in factores:
        raise ValueError(f"Unidad de presión no reconocida: {unidad}")

    return valor * factores[unidad]


# ============================================================
# EXTRACTORES GENÉRICOS
# ============================================================

def _buscar_con_patrones(texto, patrones, conversor):
    encontrados = []

    for patron in patrones:
        for coincidencia in re.finditer(patron, texto):
            valor = _numero(coincidencia.group(1))
            unidad = coincidencia.group(2)
            valor_si = conversor(valor, unidad)

            encontrados.append(
                {
                    "posicion": coincidencia.start(),
                    "valor": valor_si,
                    "texto": coincidencia.group(0),
                }
            )

    encontrados.sort(key=lambda x: x["posicion"])

    # Elimina duplicados producidos por patrones equivalentes.
    depurados = []

    for item in encontrados:
        repetido = any(
            abs(item["valor"] - previo["valor"]) < 1e-12
            and abs(item["posicion"] - previo["posicion"]) < 10
            for previo in depurados
        )

        if not repetido:
            depurados.append(item)

    return depurados


def extraer_longitudes(texto):
    patrones = [
        r"(?:longitud|largo)\s*(?:=|de|:)?\s*(\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies|in|pulg|pulgada|pulgadas)\b",
        r"(\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies|in|pulg|pulgada|pulgadas)\s+de\s+(?:longitud|largo)\b",
        r"\bl\s*=\s*(\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies|in|pulg|pulgada|pulgadas)\b",
        r"(?:tuberia|tubo)[^\.\n]{0,60}?\b(\d+(?:[\.,]\d+)?)\s*(m|ft|pie|pies)\b(?!\s*(?:\^?3|3|³)\s*/)(?!\s+de\s+diametro)",
    ]

    return _buscar_con_patrones(
        texto,
        patrones,
        convertir_longitud,
    )


def extraer_diametros(texto):
    patrones = [
        r"(?:diametro(?:\s+(?:interno|interior))?)\s*(?:=|de|:)?\s*(\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies|in|pulg|pulgada|pulgadas)\b",
        r"(\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies|in|pulg|pulgada|pulgadas)\s+de\s+diametro(?:\s+(?:interno|interior))?\b",
        r"\bd\s*=\s*(\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies|in|pulg|pulgada|pulgadas)\b",
    ]

    return _buscar_con_patrones(
        texto,
        patrones,
        convertir_longitud,
    )


def extraer_caudal(texto):
    patrones = [
        r"(\d+(?:[\.,]\d+)?)\s*(m(?:\^?3|3|³)\s*/\s*s|l\s*/\s*s|lps|l\s*/\s*min|gpm|gal\s*/\s*min)\b",
    ]

    encontrados = _buscar_con_patrones(
        texto,
        patrones,
        convertir_caudal,
    )

    if encontrados:
        return encontrados[0]["valor"]

    return None


def _extraer_variable_con_unidad(texto, nombres, unidades, conversor):
    nombres_regex = "|".join(nombres)
    unidades_regex = "|".join(unidades)

    patrones = [
        rf"(?:{nombres_regex})\s*(?:=|:|de)?\s*(-?\d+(?:[\.,]\d+)?)\s*({unidades_regex})\b",
    ]

    encontrados = _buscar_con_patrones(
        texto,
        patrones,
        conversor,
    )

    if encontrados:
        return encontrados[0]["valor"]

    return None


def extraer_presion_punto(texto, numero_punto):
    valor = _extraer_variable_con_unidad(
        texto,
        [
            rf"p{numero_punto}",
            rf"presion\s+(?:en\s+)?(?:el\s+)?punto\s+{numero_punto}",
        ],
        ["pa", "kpa", "mpa", "psi"],
        convertir_presion_a_kpa,
    )

    if valor is not None:
        return valor

    patron_inverso = (
        rf"presion[^\.\n]{{0,35}}punto\s+{numero_punto}"
        rf"[^0-9-]{{0,20}}(-?\d+(?:[\.,]\d+)?)\s*(pa|kpa|mpa|psi)\b"
    )

    coincidencia = re.search(patron_inverso, texto)

    if coincidencia:
        return convertir_presion_a_kpa(
            _numero(coincidencia.group(1)),
            coincidencia.group(2),
        )

    return None


def extraer_elevacion_punto(texto, numero_punto):
    nombres = [
        rf"z{numero_punto}",
        rf"elevacion\s+(?:en\s+)?(?:el\s+)?punto\s+{numero_punto}",
        rf"altura\s+(?:en\s+)?(?:el\s+)?punto\s+{numero_punto}",
    ]

    return _extraer_variable_con_unidad(
        texto,
        nombres,
        ["mm", "cm", "m", "ft", "pie", "pies"],
        convertir_longitud,
    )


def extraer_carga(texto, variable):
    if variable == "hA":
        nombres = [
            "ha",
            "h_a",
            r"carga\s+de\s+la\s+bomba",
            r"carga\s+agregada(?:\s+por\s+la\s+bomba)?",
        ]
    else:
        nombres = [
            "hr",
            "h_r",
            r"carga\s+retirada",
            r"carga\s+de\s+la\s+turbina",
        ]

    return _extraer_variable_con_unidad(
        texto,
        nombres,
        ["mm", "cm", "m", "ft", "pie", "pies"],
        convertir_longitud,
    )


def extraer_k_total(texto):
    patrones = [
        r"(?:sumatoria\s+de\s+k|sumatoria\s+k|k\s+total|suma\s+de\s+k|Σk)\s*(?:=|:)?\s*(\d+(?:[\.,]\d+)?)",
    ]

    for patron in patrones:
        coincidencia = re.search(patron, texto)

        if coincidencia:
            return _numero(coincidencia.group(1))

    return None


# ============================================================
# FLUIDOS, MATERIALES Y ACCESORIOS
# ============================================================

def detectar_material(texto):
    """
    Reconoce los materiales de la Tabla 8.2 de Mott 7a edición.
    Los términos más específicos se prueban primero.
    """
    catalogo = [
        (
            ["hierro ductil recubierto", "hierro ductil revestido", "ductile iron coated"],
            "Hierro dúctil recubierto",
        ),
        (
            ["hierro ductil sin recubrir", "hierro ductil no recubierto", "ductile iron uncoated"],
            "Hierro dúctil sin recubrir",
        ),
        (
            ["acero comercial", "acero soldado", "commercial steel", "welded steel"],
            "Acero comercial o soldado",
        ),
        (
            ["hierro galvanizado", "galvanized iron"],
            "Hierro galvanizado",
        ),
        (
            ["acero remachado", "riveted steel"],
            "Acero remachado",
        ),
        (
            ["concreto bien hecho", "concreto", "tuberia de concreto", "well-made concrete"],
            "Concreto bien hecho",
        ),
        (
            ["tuberia estirada", "tubo estirado", "drawn tubing", "cobre", "laton", "brass"],
            "Tubería estirada — cobre, latón o acero",
        ),
        (
            ["plastico", "pvc", "tuberia plastica", "plastic"],
            "Plástico",
        ),
        (
            ["vidrio", "glass"],
            "Vidrio — liso",
        ),
    ]

    for expresiones, nombre in catalogo:
        if contiene_alguna(texto, expresiones):
            return nombre

    return None


def detectar_fluido(texto):
    resultado = {
        "fluido_app": None,
        "fluido_detectado": None,
        "temperatura_c": None,
        "advertencia": None,
    }

    temperatura = None

    coincidencia_c = re.search(
        r"(-?\d+(?:[\.,]\d+)?)\s*°?\s*c\b",
        texto,
    )
    coincidencia_f = re.search(
        r"(-?\d+(?:[\.,]\d+)?)\s*°?\s*f\b",
        texto,
    )

    if coincidencia_c:
        temperatura = _numero(coincidencia_c.group(1))
    elif coincidencia_f:
        temperatura_f = _numero(coincidencia_f.group(1))
        temperatura = (temperatura_f - 32.0) * 5.0 / 9.0

    resultado["temperatura_c"] = temperatura

    clave = clave_fluido_desde_texto(texto, temperatura)
    resultado["fluido_app"] = clave

    if clave is None:
        # V14.17.7.3: reconocer el nombre genérico del fluido sin asignarle
        # propiedades de un aceite del catálogo que el enunciado no especificó.
        if re.search(r"\baceite\s+lubricante\b|\blubricating\s+oil\b", texto):
            resultado["fluido_detectado"] = "Aceite lubricante"
            resultado["advertencia"] = (
                "Se detectó un aceite lubricante genérico. Se usarán las propiedades "
                "explícitas del enunciado; no se selecciona automáticamente un aceite "
                "tabulado de Mott."
            )
        return resultado

    datos_catalogo = FLUIDOS.get(clave, {})
    tipo = datos_catalogo.get("tipo")
    temperatura_tabla = datos_catalogo.get("temperatura_c")
    advertencias = []

    if clave.startswith("Agua a ") or clave == "Agua — interpolar temperatura":
        resultado["fluido_detectado"] = "Agua"
        return resultado

    resultado["fluido_detectado"] = clave.split(" — ")[0]

    if (
        temperatura is not None
        and temperatura_tabla is not None
        and abs(float(temperatura) - float(temperatura_tabla)) > 0.6
    ):
        advertencias.append(
            f"El texto indica {temperatura:.2f} °C, pero la fila automática disponible "
            f"para {resultado['fluido_detectado']} corresponde a {float(temperatura_tabla):.2f} °C. "
            "Revise si el problema requiere obtener la viscosidad a otra temperatura."
        )

    if tipo == "liquido_mott_25c":
        if temperatura is not None and abs(float(temperatura) - 25.0) > 0.6:
            advertencias.append(
                "El Apéndice B de Mott tabula este líquido común a 25 °C."
            )

    if tipo == "aceite_mott_apendice_c":
        advertencias.append(
            "La selección usa los valores aproximados del Apéndice C de Mott para la temperatura tabulada."
        )

    if tipo == "liquido_mott_aprox_composicion":
        advertencias.append(
            "Mott advierte que este dato natural/biológico varía con la composición y puede no comportarse como fluido newtoniano."
        )

    if clave == "Amoniaco acuoso 25% — 25 °C":
        advertencias.append(
            "La fila de amoniaco acuoso 25% no reporta viscosidad; la app solicitará ν manualmente para calcular Reynolds."
        )

    if datos_catalogo.get("advertencia"):
        advertencias.append(datos_catalogo["advertencia"])

    if advertencias:
        # Elimina duplicados conservando orden.
        resultado["advertencia"] = " ".join(dict.fromkeys(advertencias))

    return resultado


NUMEROS_PALABRA = {
    "un": 1,
    "una": 1,
    "uno": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
}


def _cantidad_antes(texto, posicion):
    prefijo = texto[max(0, posicion - 28):posicion]

    coincidencia = re.search(
        r"(?:^|\s)(\d+|un|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s*$",
        prefijo,
    )

    if not coincidencia:
        return 1

    valor = coincidencia.group(1)

    if valor.isdigit():
        return int(valor)

    return NUMEROS_PALABRA.get(valor, 1)


def detectar_accesorios(texto):
    # Los patrones más específicos se evalúan primero y se evita contar
    # dos veces fragmentos que se superponen.
    patrones = [
        (r"valvulas?\s+de\s+compuerta[^\.\n]{0,20}(?:1/4|un cuarto)\s+abierta", "Válvula de compuerta — 1/4 abierta"),
        (r"valvulas?\s+de\s+compuerta[^\.\n]{0,20}(?:1/2|media)\s+abierta", "Válvula de compuerta — 1/2 abierta"),
        (r"valvulas?\s+de\s+compuerta[^\.\n]{0,20}(?:3/4|tres cuartos)\s+abierta", "Válvula de compuerta — 3/4 abierta"),
        (r"valvulas?\s+de\s+compuerta(?:[^\.\n]{0,25}(?:totalmente|completamente)\s+abierta)?", "Válvula de compuerta — totalmente abierta"),
        (r"valvulas?\s+de\s+globo", "Válvula de globo — totalmente abierta"),
        (r"valvulas?\s+angulares?", "Válvula angular — totalmente abierta"),
        (r"valvulas?\s+de\s+retencion[^\.\n]{0,25}(?:tipo\s+)?(?:columpio|oscilante|swing)", "Válvula de retención — tipo columpio"),
        (r"valvulas?\s+de\s+retencion[^\.\n]{0,25}(?:tipo\s+)?bola", "Válvula de retención — tipo bola"),
        (r"valvulas?\s+(?:de\s+)?mariposa", "Válvula mariposa — totalmente abierta"),
        (r"valvulas?\s+de\s+pie[^\.\n]{0,30}(?:disco\s+obturador|poppet)", "Válvula de pie con colador — disco obturador"),
        (r"valvulas?\s+de\s+pie[^\.\n]{0,30}(?:disco\s+articulado|hinged)", "Válvula de pie con colador — disco articulado"),
        (r"valvulas?\s+de\s+bola(?![^\.\n]{0,20}retencion)", "Válvula de bola — completamente abierta [auxiliar]"),
        (r"valvulas?\s+de\s+diafragma", "Válvula de diafragma — completamente abierta [auxiliar]"),
        (r"codos?(?:\s+estandar(?:es)?)?(?:\s+de)?\s*90\s*(?:°|grados?)?[^\.\n]{0,20}radio\s+largo", "Codo 90° radio largo"),
        (r"codos?(?:\s+estandar(?:es)?)?(?:\s+de)?\s*90\s*(?:°|grados?)?[^\.\n]{0,20}(?:street|calle)", "Codo 90° tipo street"),
        (r"codos?(?:\s+estandar(?:es)?)?(?:\s+de)?\s*90\s*(?:°|grados?)?", "Codo 90° estándar"),
        (r"codos?(?:\s+estandar(?:es)?)?(?:\s+de)?\s*45\s*(?:°|grados?)?[^\.\n]{0,20}(?:street|calle)", "Codo 45° tipo street"),
        (r"codos?(?:\s+estandar(?:es)?)?(?:\s+de)?\s*45\s*(?:°|grados?)?", "Codo 45° estándar"),
        (r"(?:retorno|curva)\s+cerrad[oa][^\.\n]{0,10}180\s*°?", "Retorno cerrado 180°"),
        (r"entrada(?:s)?[^\.\n]{0,35}(?:proyectad[ao]s?\s+hacia\s+(?:dentro|el\s+deposito)|tuberia\s+proyectada)", "Entrada — tubería proyectada hacia el depósito"),
        (r"entrada(?:s)?[^\.\n]{0,25}(?:borde\s+(?:cuadrado|agudo)|square[- ]?edged)", "Entrada — borde cuadrado/agudo"),
        (r"entrada(?:s)?[^\.\n]{0,25}(?:achaflanad[ao]|chamfered)", "Entrada — achaflanada"),
        (r"entrada(?:s)?\s+bien\s+redondeada", "Entrada bien redondeada — r/D > 0.15"),
        (r"salida(?:s)?\s+(?:hacia|a)\s+(?:un\s+)?deposito", "Salida hacia depósito grande"),
        (r"tee(?:s)?[^\.\n]{0,25}(?:paso\s+recto|flujo\s+por\s+la\s+linea|run)", "Tee estándar — paso recto"),
        (r"tee(?:s)?[^\.\n]{0,25}(?:ramal|branch)", "Tee estándar — flujo por ramal"),
    ]

    ocurrencias = []
    spans_ocupados = []

    for patron, nombre in patrones:
        for coincidencia in re.finditer(patron, texto):
            a, b = coincidencia.span()
            if any(not (b <= x1 or a >= x2) for x1, x2 in spans_ocupados):
                continue
            cantidad = _cantidad_antes(texto, a)
            ocurrencias.append((a, nombre, cantidad))
            spans_ocupados.append((a, b))

    acumulado = {}
    for _, nombre, cantidad in sorted(ocurrencias):
        acumulado[nombre] = acumulado.get(nombre, 0) + cantidad

    return [
        {"nombre": nombre, "cantidad": cantidad}
        for nombre, cantidad in acumulado.items()
    ]



# ============================================================
# UBICACIÓN AUTOMÁTICA DE COMPONENTES
# ============================================================

ORDINALES_TRAMO = {
    "primer": 1,
    "primero": 1,
    "primera": 1,
    "segundo": 2,
    "segunda": 2,
    "tercer": 3,
    "tercero": 3,
    "tercera": 3,
    "cuarto": 4,
    "cuarta": 4,
    "quinto": 5,
    "quinta": 5,
    "sexto": 6,
    "sexta": 6,
}


PATRONES_COMPONENTES_POSICION = [
    (r"valvulas?\s+de\s+compuerta[^\.\n]{0,20}(?:1/4|un cuarto)\s+abierta", "accesorio", "Válvula de compuerta — 1/4 abierta"),
    (r"valvulas?\s+de\s+compuerta[^\.\n]{0,20}(?:1/2|media)\s+abierta", "accesorio", "Válvula de compuerta — 1/2 abierta"),
    (r"valvulas?\s+de\s+compuerta[^\.\n]{0,20}(?:3/4|tres cuartos)\s+abierta", "accesorio", "Válvula de compuerta — 3/4 abierta"),
    (r"valvulas?\s+de\s+compuerta", "accesorio", "Válvula de compuerta — totalmente abierta"),
    (r"valvulas?\s+de\s+globo", "accesorio", "Válvula de globo — totalmente abierta"),
    (r"valvulas?\s+angulares?", "accesorio", "Válvula angular — totalmente abierta"),
    (r"valvulas?\s+de\s+retencion[^\.\n]{0,25}(?:columpio|oscilante|swing)", "accesorio", "Válvula de retención — tipo columpio"),
    (r"valvulas?\s+de\s+retencion[^\.\n]{0,25}bola", "accesorio", "Válvula de retención — tipo bola"),
    (r"valvulas?\s+(?:de\s+)?mariposa", "accesorio", "Válvula mariposa — totalmente abierta"),
    (r"valvulas?\s+de\s+pie[^\.\n]{0,30}(?:disco\s+obturador|poppet)", "accesorio", "Válvula de pie con colador — disco obturador"),
    (r"valvulas?\s+de\s+pie[^\.\n]{0,30}(?:disco\s+articulado|hinged)", "accesorio", "Válvula de pie con colador — disco articulado"),
    (r"valvulas?\s+de\s+bola", "accesorio", "Válvula de bola — completamente abierta [auxiliar]"),
    (r"valvulas?\s+de\s+diafragma", "accesorio", "Válvula de diafragma — completamente abierta [auxiliar]"),
    (r"codos?(?:\s+estandar(?:es)?)?(?:\s+de)?\s*90\s*(?:°|grados?)?[^\.\n]{0,20}radio\s+largo", "accesorio", "Codo 90° radio largo"),
    (r"codos?(?:\s+estandar(?:es)?)?(?:\s+de)?\s*90\s*(?:°|grados?)?[^\.\n]{0,20}(?:street|calle)", "accesorio", "Codo 90° tipo street"),
    (r"codos?(?:\s+estandar(?:es)?)?(?:\s+de)?\s*90\s*(?:°|grados?)?", "accesorio", "Codo 90° estándar"),
    (r"codos?(?:\s+estandar(?:es)?)?(?:\s+de)?\s*45\s*(?:°|grados?)?[^\.\n]{0,20}(?:street|calle)", "accesorio", "Codo 45° tipo street"),
    (r"codos?(?:\s+estandar(?:es)?)?(?:\s+de)?\s*45\s*(?:°|grados?)?", "accesorio", "Codo 45° estándar"),
    (r"(?:retorno|curva)\s+cerrad[oa][^\.\n]{0,10}180\s*°?", "accesorio", "Retorno cerrado 180°"),
    (r"entrada(?:s)?[^\.\n]{0,35}(?:proyectad[ao]s?\s+hacia\s+(?:dentro|el\s+deposito)|tuberia\s+proyectada)", "accesorio", "Entrada — tubería proyectada hacia el depósito"),
    (r"entrada(?:s)?[^\.\n]{0,25}(?:borde\s+(?:cuadrado|agudo)|square[- ]?edged)", "accesorio", "Entrada — borde cuadrado/agudo"),
    (r"entrada(?:s)?[^\.\n]{0,25}(?:achaflanad[ao]|chamfered)", "accesorio", "Entrada — achaflanada"),
    (r"entrada(?:s)?\s+bien\s+redondeada", "accesorio", "Entrada bien redondeada — r/D > 0.15"),
    (r"salida(?:s)?\s+(?:hacia|a)\s+(?:un\s+)?deposito", "accesorio", "Salida hacia depósito grande"),
    (r"tee(?:s)?[^\.\n]{0,25}(?:paso\s+recto|run)", "accesorio", "Tee estándar — paso recto"),
    (r"tee(?:s)?[^\.\n]{0,25}(?:ramal|branch)", "accesorio", "Tee estándar — flujo por ramal"),
    (r"\bbomba\b", "bomba", "Bomba"),
    (r"\bturbina\b", "turbina", "Turbina"),
]



def _segmentos_tramos_texto(texto):
    marcas = list(re.finditer(r"\btramo\s*(\d+)\b", texto))
    segmentos = []

    for i, marca in enumerate(marcas):
        fin = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        segmentos.append(
            {
                "numero": int(marca.group(1)),
                "inicio": marca.start(),
                "fin": fin,
            }
        )

    return segmentos


def _tramo_hint_por_posicion(posicion, segmentos):
    for segmento in segmentos:
        if segmento["inicio"] <= posicion < segmento["fin"]:
            return segmento["numero"]
    return None


def _metricas_tramos(tramos):
    metricas = []
    x = 0.0

    for tramo in tramos:
        L = tramo.get("L_m")
        if L is None:
            L = 0.0
        L = max(float(L), 0.0)
        metricas.append(
            {
                "numero": int(tramo.get("numero", len(metricas) + 1)),
                "inicio": x,
                "fin": x + L,
                "L": L,
                "D": tramo.get("D_m"),
            }
        )
        x += L

    return metricas


def _metrica_por_numero(metricas, numero):
    for metrica in metricas:
        if metrica["numero"] == numero:
            return metrica
    return None


def _numero_tramo_desde_texto(fragmento):
    coincidencia = re.search(r"tramo\s*(\d+)", fragmento)
    if coincidencia:
        return int(coincidencia.group(1))

    for palabra, numero in ORDINALES_TRAMO.items():
        if re.search(rf"\b{palabra}\s+tramo\b|\btramo\s+{palabra}\b", fragmento):
            return numero

    return None


def _tramo_por_diametro(metricas, diametro_m):
    candidatos = []

    for metrica in metricas:
        D = metrica.get("D")
        if D is None:
            continue

        diferencia = abs(float(D) - float(diametro_m))
        tolerancia = max(0.0005, abs(float(diametro_m)) * 0.015)
        if diferencia <= tolerancia:
            candidatos.append((diferencia, metrica))

    if not candidatos:
        return None

    candidatos.sort(key=lambda x: x[0])
    return candidatos[0][1]


def _ubicar_x_en_tramos(x_abs, metricas, preferir_numero=None):
    if not metricas:
        return None, None

    total = metricas[-1]["fin"]
    x_abs = min(max(float(x_abs), 0.0), total)

    if preferir_numero is not None:
        metrica = _metrica_por_numero(metricas, preferir_numero)
        if metrica is not None and metrica["L"] > 0:
            if metrica["inicio"] - 1e-9 <= x_abs <= metrica["fin"] + 1e-9:
                fraccion = (x_abs - metrica["inicio"]) / metrica["L"]
                return metrica["numero"], min(max(fraccion, 0.0), 1.0)

    for i, metrica in enumerate(metricas):
        if metrica["L"] <= 0:
            continue

        if metrica["inicio"] - 1e-9 <= x_abs <= metrica["fin"] + 1e-9:
            # En una unión se prefiere el tramo siguiente salvo que sea el final del sistema.
            if (
                abs(x_abs - metrica["fin"]) < 1e-9
                and i + 1 < len(metricas)
                and metricas[i + 1]["L"] > 0
            ):
                return metricas[i + 1]["numero"], 0.0

            fraccion = (x_abs - metrica["inicio"]) / metrica["L"]
            return metrica["numero"], min(max(fraccion, 0.0), 1.0)

    return metricas[-1]["numero"], 1.0


def _resolver_posicion_componente(
    texto,
    inicio_match,
    fin_match,
    metricas,
    tramo_hint=None,
):
    """
    Intenta convertir una descripción relativa en una distancia absoluta desde Punto 1.
    Solo devuelve una posición cuando la frase contiene suficiente información.
    """

    if not metricas:
        return None

    total = metricas[-1]["fin"]

    # Se trabaja primero con la oración que contiene al componente. Esto evita
    # que una ubicación de la bomba en la oración anterior sea atribuida, por
    # ejemplo, a una turbina mencionada después.
    patron_separador = re.compile(r"\.(?=\s|$)|;|\n")

    anteriores = list(patron_separador.finditer(texto, 0, inicio_match))
    inicio_oracion = anteriores[-1].end() if anteriores else 0

    siguiente = patron_separador.search(texto, fin_match)
    fin_oracion = siguiente.start() if siguiente else len(texto)
    inicio_contexto_abs = inicio_oracion
    fin_contexto_abs = fin_oracion

    # Si una misma oración contiene varios componentes, se restringe el texto
    # a la cláusula asociada al componente actual. Esto evita que, por ejemplo,
    # la posición de un codo posterior se asigne a una válvula anterior.
    otros = []
    for patron_comp, _, _ in PATRONES_COMPONENTES_POSICION:
        for otro in re.finditer(patron_comp, texto[inicio_oracion:fin_oracion]):
            a = inicio_oracion + otro.start()
            b = inicio_oracion + otro.end()
            if not (b <= inicio_match or a >= fin_match):
                continue
            otros.append((a, b))

    previos = [span for span in otros if span[1] <= inicio_match]
    siguientes = [span for span in otros if span[0] >= fin_match]

    if previos:
        prev_fin = max(span[1] for span in previos)
        puente = texto[prev_fin:inicio_match]
        separadores = list(re.finditer(r",(?=\s|$)|\s+y\s+|\s+ademas\b", puente))
        if separadores:
            inicio_contexto_abs = prev_fin + separadores[-1].end()

    if siguientes:
        next_ini = min(span[0] for span in siguientes)
        puente = texto[fin_match:next_ini]
        separador = re.search(r",(?=\s|$)|\s+y\s+|\s+ademas\b", puente)
        if separador:
            fin_contexto_abs = fin_match + separador.start()

    contexto = texto[inicio_contexto_abs:fin_contexto_abs]

    # Si la cláusula es demasiado corta se vuelve a la oración completa.
    if len(contexto.strip()) < 12:
        inicio_contexto_abs = inicio_oracion
        fin_contexto_abs = fin_oracion
        contexto = texto[inicio_contexto_abs:fin_contexto_abs]

    # --------------------------------------------------------
    # Selección por cercanía de la frase de posición.
    # Una misma oración puede contener más de un componente, por ejemplo
    # "válvula ... al 47 % ... y tee ... 4,65 m antes del final". En versiones
    # anteriores la primera posición encontrada podía asignarse al componente
    # equivocado. Aquí reunimos candidatos y escogemos el más cercano al nombre
    # del componente dentro de la oración.
    # --------------------------------------------------------
    inicio_componente_rel = inicio_match - inicio_contexto_abs
    fin_componente_rel = fin_match - inicio_contexto_abs
    candidatos = []

    def _distancia_match(mm):
        # Se favorece una descripción colocada inmediatamente DESPUÉS del
        # componente ("tee ... situada 4,65 m antes del final") frente a una
        # posición perteneciente al componente anterior de la misma oración.
        if mm.start() >= fin_componente_rel:
            return float(mm.start() - fin_componente_rel)
        if mm.end() <= inicio_componente_rel:
            return float(inicio_componente_rel - mm.end() + 12.0)
        return 0.0

    # Distancia absoluta desde el depósito/punto inicial.
    for patron in [
        r"(?:a|ubicad[oa]\s+a|situad[oa]\s+a|se\s+encuentra\s+a)\s*(\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies)\s*(?:del|desde\s+el|desde\s+la)\s*(?:deposito(?:\s+inicial|\s*1)?|reservorio(?:\s+inicial|\s*1)?|punto\s*1|inicio\s+del\s+sistema)",
        r"(?:deposito(?:\s+inicial|\s*1)?|reservorio(?:\s+inicial|\s*1)?|punto\s*1|inicio\s+del\s+sistema)[^\.\n]{0,45}?(\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies)[^\.\n]{0,25}?(?:despues|aguas\s+abajo)",
    ]:
        for mm in re.finditer(patron, contexto):
            x = convertir_longitud(_numero(mm.group(1)), mm.group(2))
            x = min(max(x, 0.0), total)
            numero, fraccion = _ubicar_x_en_tramos(x, metricas)
            candidatos.append((_distancia_match(mm), {
                "x_abs_m": x,
                "tramo_numero": numero,
                "posicion_fraccion": fraccion,
                "descripcion": mm.group(0).strip(),
                "confianza": 96,
            }))

    # Posiciones locales dentro de un tramo. Se aceptan formas como
    # "situada 8,65 m después del inicio del tramo 2" y
    # "4,65 m antes del final del tramo 2".
    patrones_locales = [
        ("inicio", r"(?:a|ubicad[oa](?:\s+a)?|situad[oa](?:\s+a)?|se\s+encuentra(?:\s+a)?|esta\s+situad[oa](?:\s+a)?)?\s*(\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies)\s*(?:del|desde\s+el|despues\s+del)\s+inicio(?:\s+del\s+tramo\s*(\d+))?"),
        ("final", r"(?:a|ubicad[oa](?:\s+a)?|situad[oa](?:\s+a)?|se\s+encuentra(?:\s+a)?|esta\s+situad[oa](?:\s+a)?)?\s*(\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies)\s*(?:del|antes\s+del)\s+final(?:\s+del\s+tramo\s*(\d+))?"),
    ]

    for modo_local, patron in patrones_locales:
        for mm in re.finditer(patron, contexto):
            numero_exp = int(mm.group(3)) if mm.group(3) else None
            numero = numero_exp or _numero_tramo_desde_texto(contexto) or tramo_hint
            metrica = _metrica_por_numero(metricas, numero) if numero else None
            if metrica is None or metrica["L"] <= 0:
                continue
            distancia = convertir_longitud(_numero(mm.group(1)), mm.group(2))
            distancia = max(distancia, 0.0)
            if modo_local == "inicio":
                local = min(distancia, metrica["L"])
            else:
                local = min(max(metrica["L"] - distancia, 0.0), metrica["L"])
            x = metrica["inicio"] + local
            candidatos.append((_distancia_match(mm), {
                "x_abs_m": x,
                "tramo_numero": metrica["numero"],
                "posicion_fraccion": local / metrica["L"],
                "descripcion": mm.group(0).strip(),
                "confianza": 98,
            }))

    # Porcentajes dentro de un tramo.
    for mm in re.finditer(
        r"(?:al|a\s+un|en\s+el|situad[oa](?:\s+al)?|esta\s+situad[oa](?:\s+al)?)?\s*(\d+(?:[\.,]\d+)?)\s*%\s*(?:del\s+tramo(?:\s*(\d+))?)?",
        contexto,
    ):
        numero_exp = int(mm.group(2)) if mm.group(2) else None
        numero = numero_exp or _numero_tramo_desde_texto(contexto) or tramo_hint
        metrica = _metrica_por_numero(metricas, numero) if numero else None
        if metrica is None or metrica["L"] <= 0:
            continue
        fraccion = min(max(_numero(mm.group(1)) / 100.0, 0.0), 1.0)
        x = metrica["inicio"] + fraccion * metrica["L"]
        candidatos.append((_distancia_match(mm), {
            "x_abs_m": x,
            "tramo_numero": metrica["numero"],
            "posicion_fraccion": fraccion,
            "descripcion": mm.group(0).strip(),
            "confianza": 98,
        }))

    # Mitad del tramo.
    for mm in re.finditer(r"(?:a|en)\s+la\s+mitad(?:\s+del\s+tramo(?:\s*(\d+))?)?", contexto):
        numero_exp = int(mm.group(1)) if mm.group(1) else None
        numero = numero_exp or _numero_tramo_desde_texto(contexto) or tramo_hint
        metrica = _metrica_por_numero(metricas, numero) if numero else None
        if metrica is None or metrica["L"] <= 0:
            continue
        x = metrica["inicio"] + 0.5 * metrica["L"]
        candidatos.append((_distancia_match(mm), {
            "x_abs_m": x,
            "tramo_numero": metrica["numero"],
            "posicion_fraccion": 0.5,
            "descripcion": mm.group(0).strip(),
            "confianza": 97,
        }))

    if candidatos:
        candidatos.sort(key=lambda item: item[0])
        return candidatos[0][1]

    # --------------------------------------------------------
    # 1) Distancia absoluta desde depósito inicial / Punto 1.
    # Ej.: "válvula a 20 m del depósito".
    # --------------------------------------------------------
    patrones_absolutos = [
        r"(?:a|ubicad[oa]\s+a|situad[oa]\s+a|se\s+encuentra\s+a)\s*(\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies)\s*(?:del|desde\s+el|desde\s+la)\s*(?:deposito(?:\s+inicial)?|reservorio(?:\s+inicial)?|punto\s*1|inicio\s+del\s+sistema)",
        r"(?:deposito(?:\s+inicial)?|reservorio(?:\s+inicial)?|punto\s*1|inicio\s+del\s+sistema)[^\.\n]{0,45}?(\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies)[^\.\n]{0,25}?(?:despues|aguas\s+abajo)",
    ]

    for patron in patrones_absolutos:
        coincidencia = re.search(patron, contexto)
        if coincidencia:
            x = convertir_longitud(_numero(coincidencia.group(1)), coincidencia.group(2))
            x = min(max(x, 0.0), total)
            numero, fraccion = _ubicar_x_en_tramos(x, metricas)
            return {
                "x_abs_m": x,
                "tramo_numero": numero,
                "posicion_fraccion": fraccion,
                "descripcion": coincidencia.group(0).strip(),
                "confianza": 94,
            }

    # --------------------------------------------------------
    # 2) Antes/después de un tramo identificado por diámetro.
    # Ej.: "codo antes del tramo de 75 mm".
    # --------------------------------------------------------
    patron_diametro = re.search(
        r"\b(antes|despues)\s+del\s+tramo\s+de\s+(\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies|in|pulg|pulgada|pulgadas)\b",
        contexto,
    )

    if patron_diametro:
        relacion = patron_diametro.group(1)
        D = convertir_longitud(
            _numero(patron_diametro.group(2)),
            patron_diametro.group(3),
        )
        metrica = _tramo_por_diametro(metricas, D)

        if metrica is not None:
            if relacion == "antes":
                x = metrica["inicio"]
                preferir = metrica["numero"]
            else:
                x = metrica["fin"]
                preferir = None

            numero, fraccion = _ubicar_x_en_tramos(x, metricas, preferir)
            return {
                "x_abs_m": x,
                "tramo_numero": numero,
                "posicion_fraccion": fraccion,
                "descripcion": patron_diametro.group(0).strip(),
                "confianza": 96,
            }

    # --------------------------------------------------------
    # 3) Después/antes de tramo N u ordinal.
    # --------------------------------------------------------
    patrones_relacion_tramo = [
        r"\b(antes|despues)\s+del\s+(?:(tramo\s*\d+)|((?:primer|primero|segundo|tercer|tercero|cuarto|quinto|sexto)\s+tramo))\b",
        r"\b(antes|despues)\s+de\s+(?:(tramo\s*\d+)|((?:primer|primero|segundo|tercer|tercero|cuarto|quinto|sexto)\s+tramo))\b",
    ]

    for patron in patrones_relacion_tramo:
        coincidencia = re.search(patron, contexto)
        if coincidencia:
            relacion = coincidencia.group(1)
            referencia = " ".join(x for x in coincidencia.groups()[1:] if x)
            numero_ref = _numero_tramo_desde_texto(referencia)
            metrica = _metrica_por_numero(metricas, numero_ref)

            if metrica is not None:
                if relacion == "antes":
                    x = metrica["inicio"]
                    preferir = metrica["numero"]
                else:
                    x = metrica["fin"]
                    preferir = None

                numero, fraccion = _ubicar_x_en_tramos(x, metricas, preferir)
                return {
                    "x_abs_m": x,
                    "tramo_numero": numero,
                    "posicion_fraccion": fraccion,
                    "descripcion": coincidencia.group(0).strip(),
                    "confianza": 97,
                }

    # Entre tramos consecutivos.
    entre = re.search(
        r"\bentre\s+(?:el\s+)?tramo\s*(\d+)\s+y\s+(?:el\s+)?tramo\s*(\d+)\b",
        contexto,
    )
    if entre:
        n1 = int(entre.group(1))
        n2 = int(entre.group(2))
        m1 = _metrica_por_numero(metricas, n1)
        m2 = _metrica_por_numero(metricas, n2)
        if m1 and m2:
            x = m1["fin"]
            numero, fraccion = _ubicar_x_en_tramos(x, metricas, n2)
            return {
                "x_abs_m": x,
                "tramo_numero": numero,
                "posicion_fraccion": fraccion,
                "descripcion": entre.group(0).strip(),
                "confianza": 98,
            }

    # --------------------------------------------------------
    # 4) Posición dentro de un tramo concreto.
    # --------------------------------------------------------
    numero_contexto = _numero_tramo_desde_texto(contexto) or tramo_hint
    metrica = _metrica_por_numero(metricas, numero_contexto) if numero_contexto else None

    if metrica is not None and metrica["L"] > 0:
        # a X m del inicio del tramo
        local_inicio = re.search(
            r"(?:a|ubicad[oa]\s+a|situad[oa]\s+a)\s*(\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies)\s*(?:del|desde\s+el)\s+inicio(?:\s+del\s+tramo)?",
            contexto,
        )
        if local_inicio:
            local = convertir_longitud(_numero(local_inicio.group(1)), local_inicio.group(2))
            local = min(max(local, 0.0), metrica["L"])
            x = metrica["inicio"] + local
            return {
                "x_abs_m": x,
                "tramo_numero": metrica["numero"],
                "posicion_fraccion": local / metrica["L"],
                "descripcion": local_inicio.group(0).strip(),
                "confianza": 96,
            }

        # a X m del final del tramo
        local_final = re.search(
            r"(?:a|ubicad[oa]\s+a|situad[oa]\s+a)\s*(\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies)\s*(?:del|antes\s+del)\s+final(?:\s+del\s+tramo)?",
            contexto,
        )
        if local_final:
            distancia = convertir_longitud(_numero(local_final.group(1)), local_final.group(2))
            local = min(max(metrica["L"] - distancia, 0.0), metrica["L"])
            x = metrica["inicio"] + local
            return {
                "x_abs_m": x,
                "tramo_numero": metrica["numero"],
                "posicion_fraccion": local / metrica["L"],
                "descripcion": local_final.group(0).strip(),
                "confianza": 94,
            }

        porcentaje = re.search(
            r"(?:al|a\s+un|en\s+el)\s*(\d+(?:[\.,]\d+)?)\s*%\s*(?:del\s+tramo)?",
            contexto,
        )
        if porcentaje:
            fraccion = min(max(_numero(porcentaje.group(1)) / 100.0, 0.0), 1.0)
            x = metrica["inicio"] + fraccion * metrica["L"]
            return {
                "x_abs_m": x,
                "tramo_numero": metrica["numero"],
                "posicion_fraccion": fraccion,
                "descripcion": porcentaje.group(0).strip(),
                "confianza": 95,
            }

        if re.search(r"\b(?:a|en)\s+la\s+mitad(?:\s+del\s+tramo)?\b", contexto):
            return {
                "x_abs_m": metrica["inicio"] + 0.5 * metrica["L"],
                "tramo_numero": metrica["numero"],
                "posicion_fraccion": 0.5,
                "descripcion": "a la mitad del tramo",
                "confianza": 95,
            }

        if re.search(r"\bal\s+inicio\s+del\s+tramo\b", contexto):
            return {
                "x_abs_m": metrica["inicio"],
                "tramo_numero": metrica["numero"],
                "posicion_fraccion": 0.0,
                "descripcion": "al inicio del tramo",
                "confianza": 96,
            }

        if re.search(r"\bal\s+final\s+del\s+tramo\b", contexto):
            return {
                "x_abs_m": metrica["fin"],
                "tramo_numero": metrica["numero"],
                "posicion_fraccion": 1.0,
                "descripcion": "al final del tramo",
                "confianza": 96,
            }

    return None



def _extraer_posiciones_multiples_componente(
    texto,
    inicio_match,
    fin_match,
    metricas,
    tramo_hint,
    cantidad,
):
    """Extrae varias posiciones para accesorios repetidos en una misma oración."""
    if cantidad <= 1 or not metricas:
        return []

    separador = re.compile(r"\.(?=\s|$)|;|\n")
    anteriores = list(separador.finditer(texto, 0, inicio_match))
    inicio_oracion = anteriores[-1].end() if anteriores else 0
    siguiente = separador.search(texto, fin_match)
    fin_oracion = siguiente.start() if siguiente else len(texto)
    contexto = texto[inicio_oracion:fin_oracion]

    numero_contexto = _numero_tramo_desde_texto(contexto) or tramo_hint
    metrica = _metrica_por_numero(metricas, numero_contexto) if numero_contexto else None
    if metrica is None or metrica["L"] <= 0:
        return []

    candidatos = []

    # Porcentajes: "el primero al 56 % ... y el segundo al 91 %".
    for mm in re.finditer(r"(\d+(?:[\.,]\d+)?)\s*%", contexto):
        fraccion = min(max(_numero(mm.group(1)) / 100.0, 0.0), 1.0)
        candidatos.append((mm.start(), fraccion))

    # Distancias desde el inicio del tramo.
    for mm in re.finditer(
        r"(\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies)\s*(?:del|desde\s+el|despues\s+del)\s+inicio(?:\s+del\s+tramo)?",
        contexto,
    ):
        local = convertir_longitud(_numero(mm.group(1)), mm.group(2))
        fraccion = min(max(local / metrica["L"], 0.0), 1.0)
        candidatos.append((mm.start(), fraccion))

    # Distancias antes del final del tramo.
    for mm in re.finditer(
        r"(\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies)\s*(?:del|antes\s+del)\s+final(?:\s+del\s+tramo)?",
        contexto,
    ):
        distancia = convertir_longitud(_numero(mm.group(1)), mm.group(2))
        local = min(max(metrica["L"] - distancia, 0.0), metrica["L"])
        candidatos.append((mm.start(), local / metrica["L"]))

    candidatos.sort(key=lambda item: item[0])
    unicos = []
    for _, fraccion in candidatos:
        if not any(abs(fraccion - existente) < 1e-8 for existente in unicos):
            unicos.append(fraccion)

    return unicos[:cantidad]


def enriquecer_posiciones_componentes(texto, tramos):
    """
    Añade a los tramos las posiciones gráficas detectadas y devuelve
    las posiciones absolutas de bomba/turbina desde Punto 1.
    """

    tramos_enriquecidos = []
    for tramo in tramos:
        copia = dict(tramo)
        copia["accesorios"] = [dict(item) for item in (tramo.get("accesorios") or [])]
        copia["componentes_graficos"] = list(tramo.get("componentes_graficos") or [])
        tramos_enriquecidos.append(copia)

    metricas = _metricas_tramos(tramos_enriquecidos)
    segmentos = _segmentos_tramos_texto(texto)
    ubicaciones = []
    advertencias = []
    posicion_bomba = None
    posicion_turbina = None
    spans_especificos = []

    ocurrencias = []
    spans_componentes = []
    for patron, tipo, nombre in PATRONES_COMPONENTES_POSICION:
        for coincidencia in re.finditer(patron, texto):
            a, b = coincidencia.span()
            if any(not (b <= x1 or a >= x2) for x1, x2 in spans_componentes):
                continue
            ocurrencias.append((a, b, tipo, nombre, coincidencia))
            spans_componentes.append((a, b))
            if tipo == "accesorio" and "Válvula" in nombre:
                spans_especificos.append((a, b))

    # Válvula genérica: se reconoce la posición, pero no se asigna K automáticamente.
    for coincidencia in re.finditer(r"\bvalvulas?\b", texto):
        if any(a <= coincidencia.start() < b for a, b in spans_especificos):
            continue
        ocurrencias.append(
            (
                coincidencia.start(),
                coincidencia.end(),
                "generico",
                "Válvula (tipo/K por definir)",
                coincidencia,
            )
        )

    ocurrencias.sort(key=lambda item: item[0])

    for inicio, fin, tipo, nombre, coincidencia in ocurrencias:
        tramo_hint = _tramo_hint_por_posicion(inicio, segmentos)
        posicion = _resolver_posicion_componente(
            texto,
            inicio,
            fin,
            metricas,
            tramo_hint=tramo_hint,
        )

        if posicion is None:
            continue

        registro = {
            "componente": nombre,
            "tipo": tipo,
            **posicion,
        }
        ubicaciones.append(registro)

        if tipo == "bomba" and posicion_bomba is None:
            posicion_bomba = posicion["x_abs_m"]
            continue

        if tipo == "turbina" and posicion_turbina is None:
            posicion_turbina = posicion["x_abs_m"]
            continue

        numero_tramo = posicion.get("tramo_numero")
        tramo_objetivo = next(
            (
                t
                for t in tramos_enriquecidos
                if int(t.get("numero", 0)) == int(numero_tramo or -1)
            ),
            None,
        )

        if tramo_objetivo is None:
            continue

        if tipo == "accesorio":
            item = next(
                (a for a in tramo_objetivo["accesorios"] if a.get("nombre") == nombre),
                None,
            )

            if item is None:
                item = {
                    "nombre": nombre,
                    "cantidad": max(1, _cantidad_antes(texto, inicio)),
                }
                tramo_objetivo["accesorios"].append(item)

            cantidad_item = max(1, int(item.get("cantidad", 1) or 1))
            posiciones = item.setdefault("posiciones_fraccion", [])

            # Para accesorios repetidos se intenta recuperar todas las posiciones
            # declaradas en la oración (p. ej. "dos codos: 56 % y 91 %").
            multiples = _extraer_posiciones_multiples_componente(
                texto,
                inicio,
                fin,
                metricas,
                tramo_hint,
                cantidad_item,
            )

            if multiples:
                for fraccion_multi in multiples:
                    if not any(abs(fraccion_multi - existente) < 1e-6 for existente in posiciones):
                        posiciones.append(float(fraccion_multi))
            else:
                fraccion = float(posicion["posicion_fraccion"])
                if not any(abs(fraccion - existente) < 1e-6 for existente in posiciones):
                    posiciones.append(fraccion)

            posiciones.sort()
            if posiciones:
                item["posicion_fraccion"] = posiciones[0]
            item["posicion_detectada"] = True
            item["posicion_descripcion"] = posicion["descripcion"]

        elif tipo == "generico":
            tramo_objetivo["componentes_graficos"].append(
                {
                    "nombre": nombre,
                    "posicion_fraccion": float(posicion["posicion_fraccion"]),
                }
            )
            advertencias.append(
                f"Se detectó una válvula en x={posicion['x_abs_m']:.3f} m, "
                "pero el enunciado no especifica su tipo. Seleccione manualmente "
                "el tipo de válvula o introduzca su K antes de resolver."
            )

    return {
        "tramos": tramos_enriquecidos,
        "posicion_bomba_m": posicion_bomba,
        "posicion_turbina_m": posicion_turbina,
        "ubicaciones_detectadas": ubicaciones,
        "advertencias": advertencias,
    }

# ============================================================
# TRAMOS
# ============================================================

def extraer_tramos(texto):
    material_global = detectar_material(texto)

    marcas_todas = list(
        re.finditer(
            r"\btramo\s*(\d+)\b",
            texto,
        )
    )

    # Una misma frase puede volver a mencionar "tramo 2" para ubicar una
    # bomba, válvula, etc. Solo la primera aparición que parece describir datos
    # del tramo se usa como encabezado hidráulico.
    marcas = []
    numeros_usados = set()

    for marca in marcas_todas:
        numero = int(marca.group(1))
        if numero in numeros_usados:
            continue

        contexto_posterior = texto[marca.end():min(len(texto), marca.end() + 150)]
        parece_definicion = bool(
            re.search(
                r"(?:longitud|diametro|\bl\s*=|\bd\s*=|acero|pvc|hierro|cobre|concreto)",
                contexto_posterior,
            )
        )

        if parece_definicion:
            marcas.append(marca)
            numeros_usados.add(numero)

    # Compatibilidad con enunciados sencillos donde solo aparece una vez cada tramo.
    if not marcas and marcas_todas:
        for marca in marcas_todas:
            numero = int(marca.group(1))
            if numero not in numeros_usados:
                marcas.append(marca)
                numeros_usados.add(numero)

    tramos = []

    if marcas:
        for indice, marca in enumerate(marcas):
            inicio = marca.start()
            fin = (
                marcas[indice + 1].start()
                if indice + 1 < len(marcas)
                else len(texto)
            )

            segmento = texto[inicio:fin]
            longitudes = extraer_longitudes(segmento)
            diametros = extraer_diametros(segmento)
            material = detectar_material(segmento) or material_global
            accesorios = detectar_accesorios(segmento)
            curvas = detectar_curvas_tuberia(segmento)
            k_total = extraer_k_total(segmento)

            tramos.append(
                {
                    "numero": int(marca.group(1)),
                    "L_m": longitudes[0]["valor"] if longitudes else None,
                    "D_m": diametros[0]["valor"] if diametros else None,
                    "material": material,
                    "accesorios": accesorios,
                    "curvas": curvas,
                    "K_extra": k_total,
                }
            )

        tramos.sort(key=lambda x: x["numero"])
        return tramos

    longitudes = extraer_longitudes(texto)
    diametros = extraer_diametros(texto)

    # V14.20.1: evita crear tramos duplicados cuando dos patrones describen
    # la misma única longitud (p. ej. "la tubería tiene 600 pies de longitud").
    if len(longitudes) > 1 and not diametros:
        unicos = []
        for item in longitudes:
            if not any(abs(float(item["valor"]) - float(u["valor"])) < 1e-10 for u in unicos):
                unicos.append(item)
        longitudes = unicos

    cantidad = max(
        len(longitudes),
        len(diametros),
    )

    if cantidad == 0:
        return []

    accesorios_globales = detectar_accesorios(texto)
    curvas_globales = detectar_curvas_tuberia(texto)
    k_global = extraer_k_total(texto)

    for indice in range(cantidad):
        tramos.append(
            {
                "numero": indice + 1,
                "L_m": (
                    longitudes[indice]["valor"]
                    if indice < len(longitudes)
                    else None
                ),
                "D_m": (
                    diametros[indice]["valor"]
                    if indice < len(diametros)
                    else None
                ),
                "material": material_global,
                "accesorios": (
                    accesorios_globales
                    if indice == 0
                    else []
                ),
                "curvas": (
                    curvas_globales
                    if indice == 0
                    else []
                ),
                "K_extra": (
                    k_global
                    if indice == 0
                    else None
                ),
            }
        )

    return tramos


# ============================================================
# CONDICIONES DE EXTREMO
# ============================================================

def detectar_tipos_extremo(texto):
    v1 = None
    v2 = None

    if contiene_alguna(
        texto,
        [
            "entre dos depositos",
            "entre dos reservorios",
            "de un deposito a otro deposito",
            "desde un deposito hasta otro deposito",
        ],
    ):
        return {
            "v1_tipo": "deposito",
            "v2_tipo": "deposito",
        }

    # V15.0 FINAL: extremos explícitos en texto patrón / transcripción limpia.
    # Permite distinguir superficies libres de depósitos de secciones internas
    # de tubería sin depender del dibujo.
    tnorm = normalizar_texto(texto)
    if re.search(r"(?:punto|extremo)\s*1[^.\n]{0,45}(?:deposito|reservorio|tank|reservoir)", tnorm):
        v1 = "deposito"
    if re.search(r"(?:punto|extremo)\s*2[^.\n]{0,60}(?:seccion\s+de\s+tuberia|seccion\s+de\s+pipe|tuberia|pipe)", tnorm):
        v2 = "tuberia"
    if re.search(r"(?:punto|extremo)\s*1[^.\n]{0,60}(?:seccion\s+de\s+tuberia|tuberia|pipe)", tnorm):
        v1 = "tuberia"
    if re.search(r"(?:punto|extremo)\s*2[^.\n]{0,45}(?:deposito|reservorio|tank|reservoir)", tnorm):
        v2 = "deposito"
    if v1 is not None and v2 is not None:
        return {"v1_tipo": v1, "v2_tipo": v2}

    # V14.17.7.5: si el enunciado define una caída de presión entre puntos
    # situados sobre una tubería (Mott 11.2/11.3), ambos extremos son secciones
    # de tubería, no superficies libres de depósitos. Esto también corrige LE/LAM.
    tnorm = normalizar_texto(texto)
    if (
        (
            re.search(r"(?:entre|between)\s+(?:los\s+)?(?:puntos?|points?)\s*1\s*(?:y|and)\s*2", tnorm)
            or re.search(r"(?:caida|diferencia)\s+(?:maxima\s+)?de\s+presion", tnorm)
        )
        and re.search(r"(?:tuberia|tubo|pipe|piping)", tnorm)
        and not re.search(r"(?:deposito|reservorio|tank|reservoir)", tnorm)
    ):
        return {"v1_tipo": "tuberia", "v2_tipo": "tuberia"}

    if contiene_alguna(
        texto,
        [
            "desde un deposito",
            "desde el deposito",
            "sale de un deposito",
            "parte de un deposito",
        ],
    ):
        v1 = "deposito"

    if contiene_alguna(
        texto,
        [
            "hacia un deposito",
            "hasta un deposito",
            "a otro deposito",
            "descarga en un deposito",
        ],
    ):
        v2 = "deposito"

    return {
        "v1_tipo": v1,
        "v2_tipo": v2,
    }


# ============================================================
# INCÓGNITA DE CLASE I
# ============================================================

def detectar_incognita_clase_i(texto):
    reglas = [
        (["determine la presion en el punto 2", "calcule la presion en el punto 2", "determine p2", "calcule p2"], "Presión P2"),
        (["determine la presion en el punto 1", "calcule la presion en el punto 1", "determine p1", "calcule p1"], "Presión P1"),
        (["carga de la bomba", "carga agregada por la bomba", "determine ha", "calcule ha"], "Carga agregada por bomba hA"),
        (["carga retirada", "carga de la turbina", "determine hr", "calcule hr"], "Carga retirada hR"),
        (["determine la elevacion del punto 2", "calcule z2", "determine z2"], "Elevación z2"),
        (["determine la elevacion del punto 1", "calcule z1", "determine z1"], "Elevación z1"),
    ]

    for expresiones, etiqueta in reglas:
        if contiene_alguna(texto, expresiones):
            return etiqueta

    return None


# ============================================================
# INTERPRETACIÓN AUTOMÁTICA DE GEOMETRÍA VERTICAL
# ============================================================

def _x_nodos_desde_tramos(tramos):
    x = [0.0]
    acumulado = 0.0
    for tramo in tramos:
        L = tramo.get("L_m")
        acumulado += float(L) if L is not None else 1.0
        x.append(acumulado)
    return x


def extraer_geometria_vertical(texto, tramos, z1_exp=None, z2_exp=None):
    """
    Interpreta cotas absolutas y cambios relativos de elevación.

    Ejemplos reconocidos:
    - "el segundo depósito está 12 m por encima del primero"
    - "el tramo 1 asciende 5 m"
    - "el tramo 2 desciende 3 m"
    - "la unión 1 está a cota 18 m"
    - "el punto B está a cota 18 m"
    """
    n_tramos = max(1, len(tramos))
    n_nodos = n_tramos + 1
    z = [None] * n_nodos
    z[0] = z1_exp
    z[-1] = z2_exp
    eventos = []
    advertencias = []
    restricciones = []  # (i, j, delta), z_j = z_i + delta

    # --------------------------------------------------------
    # Cotas absolutas en uniones internas.
    # --------------------------------------------------------
    for m in re.finditer(
        r"(?:union|unión)\s*(\d+)[^\.\n]{0,45}(?:cota|elevacion|altura|z)\s*(?:=|:|de|es|esta\s+a)?\s*(-?\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies)\b",
        texto,
    ):
        idx = int(m.group(1))
        if 1 <= idx < n_nodos:
            valor = convertir_longitud(_numero(m.group(2)), m.group(3))
            z[idx] = valor
            eventos.append(f"Unión {idx}: z={valor:.4g} m")

    # Final de un tramo = nodo con el mismo número.
    for m in re.finditer(
        r"final\s+del\s+tramo\s*(\d+)[^\.\n]{0,45}(?:cota|elevacion|altura|z)\s*(?:=|:|de|es|esta\s+a)?\s*(-?\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies)\b",
        texto,
    ):
        idx = int(m.group(1))
        if 1 <= idx < n_nodos:
            valor = convertir_longitud(_numero(m.group(2)), m.group(3))
            z[idx] = valor
            eventos.append(f"Final tramo {idx}: z={valor:.4g} m")

    # Punto A, B, C... se interpreta como nodos consecutivos del sistema.
    for m in re.finditer(
        r"punto\s+([a-z])[^\.\n]{0,45}(?:cota|elevacion|altura|z)\s*(?:=|:|de|es|esta\s+a)?\s*(-?\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies)\b",
        texto,
    ):
        idx = ord(m.group(1)) - ord("a")
        if 0 <= idx < n_nodos:
            valor = convertir_longitud(_numero(m.group(2)), m.group(3))
            z[idx] = valor
            eventos.append(f"Punto {m.group(1).upper()}: z={valor:.4g} m")

    # --------------------------------------------------------
    # Diferencia entre punto/depósito final e inicial.
    # --------------------------------------------------------
    patron_rel_final = re.compile(
        r"(?:segundo\s+deposito|deposito\s*2|punto\s*2)[^\.\n]{0,55}?"
        r"(\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies)[^\.\n]{0,20}?"
        r"(por\s+encima|mas\s+alto|sobre|por\s+debajo|mas\s+bajo)"
        r"[^\.\n]{0,45}?(?:primer\s+deposito|deposito\s*1|primero|punto\s*1)"
    )
    m = patron_rel_final.search(texto)
    if m:
        delta = convertir_longitud(_numero(m.group(1)), m.group(2))
        direccion = m.group(3)
        if "debajo" in direccion or "bajo" in direccion:
            delta = -delta
        restricciones.append((0, n_nodos - 1, delta))
        eventos.append(f"Desnivel final-inicial = {delta:+.4g} m")

    # Forma inversa: "12 m por encima del primer depósito" cerca del segundo.
    patron_rel_inv = re.compile(
        r"(?:segundo\s+deposito|deposito\s*2|punto\s*2)[^\.\n]{0,35}?"
        r"(?:esta|se\s+encuentra|queda)?[^\.\n]{0,15}?"
        r"(\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies)\s*"
        r"(por\s+encima|por\s+debajo|mas\s+alto|mas\s+bajo)"
    )
    if not m:
        m2 = patron_rel_inv.search(texto)
        if m2:
            delta = convertir_longitud(_numero(m2.group(1)), m2.group(2))
            direccion = m2.group(3)
            if "debajo" in direccion or "bajo" in direccion:
                delta = -delta
            restricciones.append((0, n_nodos - 1, delta))
            eventos.append(f"Desnivel final-inicial = {delta:+.4g} m")

    # --------------------------------------------------------
    # Ascensos/descensos por tramo.
    # --------------------------------------------------------
    patrones_pendiente = [
        r"tramo\s*(\d+)[^\.\n]{0,80}?(asciende|sube|se\s+eleva|desciende|baja)\s*(\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies)",
        r"(?:en\s+el\s+)?tramo\s*(\d+)[^\.\n]{0,30}?la\s+tuberia[^\.\n]{0,35}?(asciende|sube|se\s+eleva|desciende|baja)\s*(\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies)",
    ]

    vistos = set()
    for patron in patrones_pendiente:
        for mm in re.finditer(patron, texto):
            n = int(mm.group(1))
            if not (1 <= n <= n_tramos) or n in vistos:
                continue
            delta = convertir_longitud(_numero(mm.group(3)), mm.group(4))
            verbo = mm.group(2)
            if verbo in ("desciende", "baja"):
                delta = -delta
            restricciones.append((n - 1, n, delta))
            eventos.append(f"Tramo {n}: Δz={delta:+.4g} m")
            vistos.add(n)

    # --------------------------------------------------------
    # Respaldo por segmento de definición de cada tramo.
    # Muchos enunciados escriben "Tramo 1: ... . Durante este tramo la tubería
    # asciende 4,35 m". La palabra "asciende" queda en una oración posterior y
    # los patrones anteriores no necesariamente conservan el número del tramo.
    # Aquí asociamos cada frase con el tramo cuya definición la precede.
    # --------------------------------------------------------
    marcas_def = []
    usados_def = set()
    for marca in re.finditer(r"\btramo\s*(\d+)\b", texto):
        numero = int(marca.group(1))
        if numero in usados_def or not (1 <= numero <= n_tramos):
            continue
        contexto_posterior = texto[marca.end():min(len(texto), marca.end() + 170)]
        if re.search(
            r"(?:longitud|diametro|\bl\s*=|\bd\s*=|acero|pvc|hierro|cobre|concreto)",
            contexto_posterior,
        ):
            marcas_def.append((numero, marca.start()))
            usados_def.add(numero)

    marcas_def.sort(key=lambda item: item[1])
    for idx, (numero, inicio_seg) in enumerate(marcas_def):
        if numero in vistos:
            continue
        fin_seg = marcas_def[idx + 1][1] if idx + 1 < len(marcas_def) else len(texto)
        segmento = texto[inicio_seg:fin_seg]
        mm = re.search(
            r"\b(asciende|sube|se\s+eleva|desciende|baja)\s*(\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies)\b",
            segmento,
        )
        if mm:
            delta = convertir_longitud(_numero(mm.group(2)), mm.group(3))
            verbo = mm.group(1)
            if verbo in ("desciende", "baja"):
                delta = -delta
            restricciones.append((numero - 1, numero, delta))
            eventos.append(f"Tramo {numero}: Δz={delta:+.4g} m")
            vistos.add(numero)

    # Si hay geometría relativa sin datum absoluto, usar z1=0 como referencia.
    if restricciones and all(valor is None for valor in z):
        z[0] = 0.0
        advertencias.append(
            "El enunciado proporciona desniveles relativos pero ninguna cota absoluta. "
            "Se tomó z1=0 m como datum de referencia; esto no altera la ecuación de energía basada en diferencias de elevación."
        )

    # Propagación bidireccional de las restricciones.
    for _ in range(max(4, 3 * len(restricciones) + 2)):
        cambio = False
        for i, j, delta in restricciones:
            if z[i] is not None and z[j] is None:
                z[j] = z[i] + delta
                cambio = True
            elif z[j] is not None and z[i] is None:
                z[i] = z[j] - delta
                cambio = True
            elif z[i] is not None and z[j] is not None:
                error = (z[j] - z[i]) - delta
                if abs(error) > 1e-3:
                    advertencias.append(
                        f"Existe una inconsistencia de elevación de {error:+.4g} m entre nodos {i} y {j}; "
                        "se conservaron las cotas explícitas."
                    )
        if not cambio:
            break

    # Completar nodos internos no especificados interpolando entre cotas conocidas.
    x = _x_nodos_desde_tramos(tramos)
    conocidos = [i for i, valor in enumerate(z) if valor is not None]

    if len(conocidos) >= 2:
        for a, b in zip(conocidos[:-1], conocidos[1:]):
            if b - a <= 1:
                continue
            xa, xb = x[a], x[b]
            for k in range(a + 1, b):
                if z[k] is None:
                    frac = (x[k] - xa) / (xb - xa) if xb != xa else (k - a) / (b - a)
                    z[k] = z[a] + frac * (z[b] - z[a])
                    eventos.append(f"Unión {k}: z≈{z[k]:.4g} m (interpolada)")

    # Si solo se conoce un extremo, completar el otro únicamente cuando las restricciones lo permitan.
    detectada = bool(eventos or restricciones or any(v is not None for v in z[1:-1]))

    return {
        "z1_m": z[0],
        "z2_m": z[-1],
        "z_nodos_m": z,
        "geometria_vertical_detectada": detectada,
        "eventos": eventos,
        "advertencias": list(dict.fromkeys(advertencias)),
    }


# ============================================================
# DATOS ESTRUCTURADOS PARA AUTOLLENADO
# ============================================================

def extraer_datos_estructurados(enunciado):
    # V14.12 analiza primero el texto original para conservar comillas, símbolos,
    # separadores decimales y la notación exacta de las unidades.
    analisis_v1412 = analizar_enunciado_v1412(enunciado)
    texto = normalizar_texto(enunciado)
    fluido = detectar_fluido(texto)
    extremos = detectar_tipos_extremo(texto)

    tramos_base = extraer_tramos(texto)
    posiciones = enriquecer_posiciones_componentes(texto, tramos_base)

    z1_explicita = extraer_elevacion_punto(texto, 1)
    z2_explicita = extraer_elevacion_punto(texto, 2)
    geometria_vertical = extraer_geometria_vertical(
        texto,
        posiciones["tramos"],
        z1_exp=z1_explicita,
        z2_exp=z2_explicita,
    )

    transiciones = detectar_transiciones_en_texto(texto, posiciones["tramos"])

    datos = {
        "fluido_app": fluido["fluido_app"],
        "fluido_detectado": fluido["fluido_detectado"],
        "temperatura_c": fluido["temperatura_c"],
        "advertencias": [],
        "Q_m3s": extraer_caudal(texto),
        "P1_kpa": extraer_presion_punto(texto, 1),
        "P2_kpa": extraer_presion_punto(texto, 2),
        "z1_m": geometria_vertical["z1_m"],
        "z2_m": geometria_vertical["z2_m"],
        "z_nodos_m": geometria_vertical["z_nodos_m"],
        "geometria_vertical_detectada": geometria_vertical["geometria_vertical_detectada"],
        "geometria_vertical_eventos": geometria_vertical["eventos"],
        "hA_m": extraer_carga(texto, "hA"),
        "hR_m": extraer_carga(texto, "hR"),
        "incognita_clase_i": detectar_incognita_clase_i(texto),
        "v1_tipo": extremos["v1_tipo"],
        "v2_tipo": extremos["v2_tipo"],
        "tramos": posiciones["tramos"],
        "posicion_bomba_m": posiciones["posicion_bomba_m"],
        "posicion_turbina_m": posiciones["posicion_turbina_m"],
        "ubicaciones_detectadas": posiciones["ubicaciones_detectadas"],
        "transiciones": transiciones,
    }

    if fluido["advertencia"]:
        datos["advertencias"].append(fluido["advertencia"])

    datos["advertencias"].extend(posiciones.get("advertencias", []))
    datos["advertencias"].extend(geometria_vertical.get("advertencias", []))

    # V14.12 solo rellena notaciones/unidades que la capa histórica no pudo
    # estructurar. Si existe una discrepancia, conserva el valor previo y la
    # convierte en advertencia visible en vez de sobrescribirla.
    datos = fusionar_prefill_v1412(datos, analisis_v1412)

    # V14.13 trabaja después de V14.12 para poder usar diámetros que hayan sido
    # normalizados desde NPS/DN + Schedule. Complementa accesorios y garantiza
    # que todo cambio real de diámetro quede representado como transición, aun
    # cuando el enunciado no diga si es súbita o gradual.
    analisis_v1413 = analizar_componentes_v1413(enunciado, datos.get("tramos") or [])
    datos = fusionar_prefill_v1413(datos, analisis_v1413)

    if not datos["tramos"]:
        datos["advertencias"].append(
            "No se detectaron tramos completos con longitud o diámetro. "
            "Revise esos campos manualmente."
        )

    return datos


# ============================================================
# RESUMEN LEGIBLE DE LOS DATOS DETECTADOS
# ============================================================

def detectar_datos_numericos(texto_original):
    prefill = extraer_datos_estructurados(texto_original)
    datos = []

    if prefill["Q_m3s"] is not None:
        datos.append(
            {
                "variable": "Caudal",
                "valores": [f"{prefill['Q_m3s']:.8g} m³/s"],
            }
        )

    if prefill["P1_kpa"] is not None:
        datos.append(
            {
                "variable": "P1",
                "valores": [f"{prefill['P1_kpa']:.8g} kPa"],
            }
        )

    if prefill["P2_kpa"] is not None:
        datos.append(
            {
                "variable": "P2",
                "valores": [f"{prefill['P2_kpa']:.8g} kPa"],
            }
        )

    if prefill["z1_m"] is not None:
        datos.append(
            {
                "variable": "z1",
                "valores": [f"{prefill['z1_m']:.8g} m"],
            }
        )

    if prefill["z2_m"] is not None:
        datos.append(
            {
                "variable": "z2",
                "valores": [f"{prefill['z2_m']:.8g} m"],
            }
        )

    z_nodos = prefill.get("z_nodos_m") or []
    if len(z_nodos) > 2:
        internos = [
            f"Unión {i}: {z:.6g} m"
            for i, z in enumerate(z_nodos[1:-1], start=1)
            if z is not None
        ]
        if internos:
            datos.append(
                {
                    "variable": "Geometría vertical",
                    "valores": internos,
                }
            )

    if prefill["fluido_detectado"]:
        descripcion = prefill["fluido_detectado"]

        if prefill["temperatura_c"] is not None:
            descripcion += f" a {prefill['temperatura_c']:g} °C"

        datos.append(
            {
                "variable": "Fluido",
                "valores": [descripcion],
            }
        )

    for tramo in prefill["tramos"]:
        valores = []

        if tramo["L_m"] is not None:
            valores.append(f"L={tramo['L_m']:.8g} m")

        if tramo["D_m"] is not None:
            valores.append(f"D={tramo['D_m']:.8g} m")

        if tramo["material"]:
            valores.append(tramo["material"])

        if tramo["accesorios"]:
            accesorios = ", ".join(
                f"{item['cantidad']} × {item['nombre']}"
                for item in tramo["accesorios"]
            )
            valores.append(accesorios)

            posiciones_texto = []
            for item in tramo["accesorios"]:
                posiciones = item.get("posiciones_fraccion") or []
                if not posiciones and item.get("posicion_fraccion") is not None:
                    posiciones = [item.get("posicion_fraccion")]

                if posiciones:
                    porcentajes = ", ".join(
                        f"{100.0 * float(fraccion):.1f}%"
                        for fraccion in posiciones
                    )
                    posiciones_texto.append(
                        f"{item['nombre']}: {porcentajes}"
                    )

            if posiciones_texto:
                valores.append(
                    "Posiciones: " + "; ".join(posiciones_texto)
                )

        if tramo["K_extra"] is not None:
            valores.append(f"K adicional={tramo['K_extra']:.4g}")

        if valores:
            datos.append(
                {
                    "variable": f"Tramo {tramo['numero']}",
                    "valores": valores,
                }
            )

    for transicion in prefill.get("transiciones") or []:
        vals = [transicion.get("tipo", "Transición")]
        if transicion.get("angulo_grados") is not None:
            vals.append(f"θ={transicion['angulo_grados']:.6g}°")
        datos.append({
            "variable": f"Transición entre tramos {transicion.get('entre')} y {int(transicion.get('entre', 0)) + 1}",
            "valores": vals,
        })

    if prefill.get("posicion_bomba_m") is not None:
        datos.append(
            {
                "variable": "Posición de bomba",
                "valores": [f"x={prefill['posicion_bomba_m']:.8g} m desde Punto 1"],
            }
        )

    if prefill.get("posicion_turbina_m") is not None:
        datos.append(
            {
                "variable": "Posición de turbina",
                "valores": [f"x={prefill['posicion_turbina_m']:.8g} m desde Punto 1"],
            }
        )

    return datos


# ============================================================
# IDENTIFICADOR AUTOMÁTICO
# ============================================================

def identificar_clase_automaticamente(enunciado):
    if not enunciado or not enunciado.strip():
        return {
            "clase": None,
            "confianza": 0,
            "razones": [],
            "advertencias": ["El enunciado está vacío."],
            "datos": [],
            "prefill": {},
        }

    texto = normalizar_texto(enunciado)
    razones = []
    advertencias = []

    busca_caudal = contiene_alguna(
        texto,
        [
            "determine el caudal",
            "determinar el caudal",
            "calcule el caudal",
            "calcular el caudal",
            "halle el caudal",
            "encuentre el caudal",
            "que caudal",
            "cual es el caudal",
            "cuanto caudal",
            "flujo volumetrico",
            "rapidez del flujo volumetrico",
            "flujo volumetrico maximo",
            "flujo volumetrico maxima",
            "rapidez de flujo volumetrico",
            "determine q",
            "calcule q",
            "q = ?",
            "q=?",
        ],
    )

    busca_diametro = contiene_alguna(
        texto,
        [
            "determine el diametro",
            "determinar el diametro",
            "calcule el diametro",
            "calcular el diametro",
            "diametro minimo",
            "diametro requerido",
            "diametro necesario",
            "tamano de tuberia",
            "tamano minimo de tuberia",
            "tamano mas pequeno permisible",
            "tamano mas pequeno de tuberia",
            "seleccione el diametro",
            "seleccione una tuberia",
        ],
    )

    busca_presion = contiene_alguna(
        texto,
        [
            "determine la presion",
            "calcule la presion",
            "presion en el punto",
            "presion requerida",
            "presion disponible",
            "determine p1",
            "calcule p1",
            "determine p2",
            "calcule p2",
            "p1 = ?",
            "p2 = ?",
            "p1=?",
            "p2=?",
        ],
    )

    busca_elevacion = contiene_alguna(
        texto,
        [
            "determine la elevacion",
            "calcule la elevacion",
            "altura requerida",
            "diferencia de elevacion",
        ],
    )

    busca_bomba = contiene_alguna(
        texto,
        [
            "carga de la bomba",
            "carga agregada por la bomba",
            "potencia de la bomba",
            "potencia requerida por la bomba",
            "determine la potencia",
            "calcule la potencia",
        ],
    )

    busca_perdida = contiene_alguna(
        texto,
        [
            "determine la perdida de carga",
            "calcule la perdida de carga",
            "perdida total de energia",
            "perdida total de carga",
        ],
    )

    ignora_perdidas_menores = contiene_alguna(
        texto,
        [
            "desprecie las perdidas menores",
            "despreciar las perdidas menores",
            "desprecie perdidas menores",
            "ignore las perdidas menores",
            "sin perdidas menores",
            "no considere perdidas menores",
            "desprecie los accesorios",
        ],
    )

    menciona_accesorios = contiene_alguna(
        texto,
        [
            "codo",
            "valvula",
            "tee",
            "entrada",
            "salida",
            "reduccion",
            "contraccion",
            "expansion",
            "accesorio",
            "perdidas menores",
            "coeficiente k",
            "k=",
        ],
    )

    perdidas_pequenas = contiene_alguna(
        texto,
        [
            "perdidas menores relativamente pequenas",
            "perdidas menores son pequenas",
            "correccion por perdidas menores",
            "como correccion",
            "pequena correccion",
        ],
    )

    perdidas_importantes = contiene_alguna(
        texto,
        [
            "perdidas menores significativas",
            "perdidas menores importantes",
            "incluya todas las perdidas",
            "considere todas las perdidas",
            "incluyendo las perdidas menores",
            "incluya las perdidas menores",
            "alta precision",
        ],
    )

    menciona_comercial = contiene_alguna(
        texto,
        [
            "diametro comercial",
            "tamano comercial",
            "tuberia comercial",
            "diametro real",
            "tuberia seleccionada",
            "diametro seleccionado",
            "tuberia estandar",
            "calibre 40",
            "calibre 80",
            "schedule 40",
            "schedule 80",
            "cedula 40",
            "cedula 80",
        ],
    )

    verifica_comercial = contiene_alguna(
        texto,
        [
            "verifique el diametro",
            "verifique la tuberia",
            "compruebe la presion",
            "verifique la presion",
            "compruebe si",
            "verifique si",
            "cumple la presion",
        ],
    )

    prefill = extraer_datos_estructurados(enunciado)

    # V14.17.7.5: respeta métodos exigidos literalmente por el enunciado.
    # "Prueba y error" con Darcy-Weisbach debe conservarse como estrategia
    # principal, aun cuando la Ec. (11-3) sirva como excelente estimación inicial.
    if re.search(r"\b(?:prueba\s+y\s+error|trial\s+and\s+error)\b", texto):
        prefill["metodo_solicitado_v1421"] = "prueba_y_error_darcy"
        prefill["metodo_solicitado_texto"] = "Prueba y error a partir de Darcy-Weisbach"

    if menciona_comercial and verifica_comercial:
        clase = "Clase III-B"
        confianza = 96
        razones = [
            "Se detectó una tubería o diámetro comercial ya seleccionado.",
            "El enunciado solicita verificar su comportamiento o la presión disponible.",
        ]

    elif busca_diametro:
        # III-B requiere que ya exista un diámetro/tamaño concreto que verificar.
        # Si solo se pide "el tamaño más pequeño Schedule 40", primero se debe
        # calcular D mínimo (III-A) y luego seleccionar el comercial inmediato.
        tiene_tamano_concreto = any(t.get("D_m") is not None for t in (prefill.get("tramos") or [])) or bool(
            re.search(r"\b(?:nps|dn)\s*[-:]?\s*\d+|\bdiametro\s*(?:=|de|:)\s*\d", texto)
        )
        if menciona_comercial and tiene_tamano_concreto:
            clase = "Clase III-B"
            confianza = 91
            razones = [
                "La incógnita principal está relacionada con el desempeño de un tamaño comercial concreto.",
                "Se detectó un diámetro/NPS/DN ya seleccionado que debe verificarse.",
            ]
        else:
            clase = "Clase III-A"
            confianza = 95 if not menciona_comercial else 93
            razones = [
                "La incógnita principal detectada es el diámetro/tamaño mínimo requerido.",
                "Se calculará primero el diámetro mínimo y, si se solicita Schedule/Cédula, se seleccionará después el tamaño comercial inmediato superior.",
            ]

    elif busca_caudal:
        razones = ["La incógnita principal detectada es el caudal Q."]

        if ignora_perdidas_menores:
            clase = "Clase II-A"
            confianza = 98
            razones.append(
                "El enunciado indica explícitamente despreciar las pérdidas menores."
            )

        elif not menciona_accesorios:
            clase = "Clase II-A"
            confianza = 90
            razones.append(
                "No se detectaron accesorios ni pérdidas menores."
            )

        elif perdidas_pequenas:
            clase = "Clase II-B"
            confianza = 94
            razones.append(
                "Las pérdidas menores aparecen como una corrección relativamente pequeña."
            )

        elif perdidas_importantes:
            clase = "Clase II-C"
            confianza = 96
            razones.append(
                "El problema solicita incorporar las pérdidas menores en la solución completa."
            )

        else:
            # V14.20.1: una sola línea de diámetro uniforme con accesorios es el
            # patrón típico II-B de Mott (p. ej. Ejemplo 11.3). II-C se reserva
            # para sistemas con varios diámetros/tramos o transiciones.
            tramos_pf = list((prefill or {}).get("tramos") or [])
            diametros = {round(float(t.get("D_m")), 9) for t in tramos_pf if t.get("D_m") is not None}
            trans_pf = list((prefill or {}).get("transiciones") or [])
            evidencia_multitramo = bool(re.search(
                r"\b(?:dos|tres|cuatro|varios)\s+(?:tramos|tuberias)|distintos?\s+diametros|diferentes?\s+diametros|cambio\s+de\s+seccion|contraccion|expansion",
                texto,
            ))
            if len(diametros) <= 1 and not trans_pf and not evidencia_multitramo:
                clase = "Clase II-B"
                confianza = 88
                razones.append(
                    "Se detectó una línea de diámetro uniforme con pérdidas menores; corresponde al esquema II-B de Mott."
                )
            else:
                clase = "Clase II-C"
                confianza = 82
                razones.append(
                    "Se detectaron varios diámetros/tramos o transiciones junto con pérdidas menores; se usa el procedimiento completo II-C."
                )
                advertencias.append(
                    "Confirme II-C si el esquema contiene múltiples diámetros o transiciones relevantes."
                )

    elif busca_presion or busca_elevacion or busca_bomba or busca_perdida:
        clase = "Clase I"
        confianza = 91
        razones = [
            "No se detectó el caudal ni el diámetro como incógnitas principales.",
            "La incógnita corresponde a presión, elevación, carga, potencia o pérdida de energía.",
        ]

    else:
        clase = None
        confianza = 25
        advertencias.extend(
            [
                "No se pudo determinar con suficiente seguridad cuál es la incógnita principal.",
                "Utilice el asistente guiado o seleccione la clase manualmente.",
            ]
        )

    advertencias.extend(prefill.get("advertencias", []))

    return {
        "clase": clase,
        "confianza": confianza,
        "razones": razones,
        "advertencias": advertencias,
        "datos": detectar_datos_numericos(enunciado),
        "prefill": prefill,
    }


# ============================================================
# IDENTIFICADOR GUIADO
# ============================================================

def identificar_clase_guiada(
    incognita,
    perdidas_menores="No sé / no aplica",
    objetivo_diametro="No aplica",
):
    if incognita == "Caudal":
        if perdidas_menores == "No existen / se despreciarán":
            return {
                "clase": "Clase II-A",
                "confianza": 99,
                "razones": [
                    "El caudal Q es la incógnita principal.",
                    "Las pérdidas menores no se consideran.",
                ],
            }

        if perdidas_menores == "Existen pero son relativamente pequeñas":
            return {
                "clase": "Clase II-B",
                "confianza": 98,
                "razones": [
                    "El caudal Q es la incógnita principal.",
                    "Las pérdidas menores se incorporan como una corrección.",
                ],
            }

        if perdidas_menores == "Son importantes / usar solución completa":
            return {
                "clase": "Clase II-C",
                "confianza": 99,
                "razones": [
                    "El caudal Q es la incógnita principal.",
                    "Las pérdidas menores deben incluirse en la solución completa.",
                ],
            }

        return {
            "clase": "Clase II-C",
            "confianza": 70,
            "razones": [
                "El caudal Q es la incógnita principal.",
                "Como no se conoce la importancia de las pérdidas menores, se recomienda II-C.",
            ],
        }

    if incognita == "Diámetro":
        if objetivo_diametro == "Calcular diámetro mínimo teórico":
            return {
                "clase": "Clase III-A",
                "confianza": 99,
                "razones": [
                    "El diámetro es la incógnita principal.",
                    "Se desea obtener el diámetro hidráulico mínimo teórico.",
                ],
            }

        if objetivo_diametro == "Verificar un diámetro comercial ya seleccionado":
            return {
                "clase": "Clase III-B",
                "confianza": 99,
                "razones": [
                    "Existe un diámetro comercial seleccionado.",
                    "Se desea verificar que satisfaga las condiciones del sistema.",
                ],
            }

        return {
            "clase": "Clase III-A",
            "confianza": 75,
            "razones": [
                "El diámetro es la variable principal.",
                "Como no se indicó que ya exista un diámetro comercial, se recomienda comenzar por III-A.",
            ],
        }

    if incognita in (
        "Presión",
        "Pérdida de carga",
        "Potencia de bomba",
        "Elevación",
    ):
        return {
            "clase": "Clase I",
            "confianza": 98,
            "razones": [
                "El caudal y el diámetro no son las incógnitas principales.",
                f"La incógnita indicada es: {incognita}.",
            ],
        }

    return {
        "clase": None,
        "confianza": 30,
        "razones": [
            "No existen suficientes datos para determinar la clase."
        ],
    }
