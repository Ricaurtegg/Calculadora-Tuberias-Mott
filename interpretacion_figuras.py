"""Interpretación conservadora de figuras y esquemas hidráulicos — V14.3.

Objetivo
--------
Analizar la *disposición espacial* del texto y las etiquetas de una figura para
extraer componentes hidráulicos y relaciones aproximadas. No sustituye el OCR
de V14.2 ni intenta reconstruir a ciegas un esquema complejo.

La filosofía es deliberadamente segura:
- conserva el texto OCR original;
- devuelve hallazgos con confianza y posición relativa;
- no convierte distancias en píxeles a metros;
- no inventa diámetros, cotas, presiones ni longitudes;
- las inferencias espaciales se muestran para confirmación antes de agregarlas
  al enunciado que recibirá el clasificador.

V14.3 reconoce por etiquetas:
- depósitos/reservorios/tanques;
- bombas y turbinas;
- válvulas y codos;
- referencias P1/P2, z1/z2, hA/hR, D, L y Q cuando aparecen en la figura;
- orden aproximado de componentes entre depósito 1 y depósito 2.

Para imágenes y PDF se apoya en Tesseract (image_to_data). Los PDF se
rasterizan con PyMuPDF. No requiere dependencias nuevas respecto de V14.2.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from io import BytesIO
from pathlib import Path
import math
import re
import unicodedata


EXTENSIONES_FIGURA = (".png", ".jpg", ".jpeg", ".pdf")


class ErrorInterpretacionFigura(ValueError):
    pass


@dataclass
class HallazgoFigura:
    tipo: str
    texto: str
    pagina: int
    x_rel: float
    y_rel: float
    confianza: float
    estado: str
    detalle: str = ""
    fraccion_recorrido: float | None = None

    def como_dict(self):
        return asdict(self)


@dataclass
class ResultadoFigura:
    nombre: str
    pagina: int
    ancho: int
    alto: int
    hallazgos: list[dict]
    orientacion: str | None
    confianza_global: float
    texto_sugerido: str
    advertencias: list[str]
    lineas_ocr: list[dict]

    def como_dict(self):
        return asdict(self)


def _norm(texto: str) -> str:
    texto = (texto or "").lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.replace("º", "°")
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def _motor_tesseract():
    try:
        import pytesseract
    except ImportError as e:
        raise ErrorInterpretacionFigura(
            "Falta pytesseract. Instale con: python -m pip install pytesseract"
        ) from e

    try:
        from lectura_archivos import ocr_disponible
    except Exception as e:
        raise ErrorInterpretacionFigura(
            "No se pudo consultar el motor OCR de lectura_archivos.py."
        ) from e

    disponible, ruta = ocr_disponible()
    if not disponible:
        raise ErrorInterpretacionFigura(ruta)

    pytesseract.pytesseract.tesseract_cmd = ruta
    return pytesseract


def _abrir_imagen(nombre: str, datos: bytes, pagina_pdf: int = 1):
    ext = Path(nombre).suffix.lower()
    if ext not in EXTENSIONES_FIGURA:
        raise ErrorInterpretacionFigura(
            f"V14.3 interpreta figuras PNG, JPG, JPEG o PDF; recibido: {ext or 'sin extensión'}."
        )

    try:
        from PIL import Image, ImageOps
    except ImportError as e:
        raise ErrorInterpretacionFigura(
            "Falta Pillow. Instale con: python -m pip install pillow"
        ) from e

    if ext in (".png", ".jpg", ".jpeg"):
        try:
            img = Image.open(BytesIO(datos))
            img.load()
            img = ImageOps.exif_transpose(img).convert("RGB")
            return img, 1
        except Exception as e:
            raise ErrorInterpretacionFigura(f"No se pudo abrir la imagen: {e}") from e

    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf
        except ImportError as e:
            raise ErrorInterpretacionFigura(
                "Falta PyMuPDF. Instale con: python -m pip install pymupdf"
            ) from e

    try:
        doc = pymupdf.open(stream=datos, filetype="pdf")
    except Exception as e:
        raise ErrorInterpretacionFigura(f"No se pudo abrir el PDF: {e}") from e

    try:
        if len(doc) == 0:
            raise ErrorInterpretacionFigura("El PDF no contiene páginas.")
        pagina_pdf = int(pagina_pdf)
        if not 1 <= pagina_pdf <= len(doc):
            raise ErrorInterpretacionFigura(
                f"Página fuera de rango: {pagina_pdf}. El PDF tiene {len(doc)} página(s)."
            )
        page = doc[pagina_pdf - 1]
        pix = page.get_pixmap(matrix=pymupdf.Matrix(2.0, 2.0), alpha=False)
        modo = "RGB" if pix.n >= 3 else "L"
        img = Image.frombytes(modo, [pix.width, pix.height], pix.samples).convert("RGB")
        return img, pagina_pdf
    finally:
        doc.close()


def _preprocesar_layout(img):
    """Preprocesamiento suave: conserva la geometría y mejora contraste."""
    from PIL import ImageOps

    gris = ImageOps.grayscale(img)
    gris = ImageOps.autocontrast(gris)
    # No se rota ni recorta: las posiciones relativas deben conservarse.
    if max(gris.size) < 1800:
        escala = min(2.0, 1800.0 / max(max(gris.size), 1))
        gris = gris.resize((int(gris.width * escala), int(gris.height * escala)))
    return gris


def _lineas_ocr(img):
    pytesseract = _motor_tesseract()
    img = _preprocesar_layout(img)

    # psm 11 funciona mejor para etiquetas dispersas de esquemas.
    configs = [
        ("spa+eng", "--psm 11"),
        ("eng", "--psm 11"),
        (None, "--psm 11"),
    ]

    ultimo_error = None
    data = None
    for idioma, config in configs:
        try:
            kwargs = {
                "config": config,
                "output_type": pytesseract.Output.DICT,
            }
            if idioma:
                kwargs["lang"] = idioma
            data = pytesseract.image_to_data(img, **kwargs)
            if data and data.get("text"):
                break
        except Exception as e:
            ultimo_error = e
            data = None

    if data is None:
        raise ErrorInterpretacionFigura(f"No se pudo obtener OCR espacial: {ultimo_error}")

    grupos = {}
    n = len(data.get("text", []))
    for i in range(n):
        palabra = str(data["text"][i] or "").strip()
        if not palabra:
            continue
        try:
            conf = float(data["conf"][i])
        except Exception:
            conf = -1.0
        if conf < 0:
            continue

        clave = (
            int(data.get("page_num", [1] * n)[i]),
            int(data.get("block_num", [0] * n)[i]),
            int(data.get("par_num", [0] * n)[i]),
            int(data.get("line_num", [0] * n)[i]),
        )
        g = grupos.setdefault(
            clave,
            {"palabras": [], "conf": [], "left": [], "top": [], "right": [], "bottom": []},
        )
        x = int(data["left"][i])
        y = int(data["top"][i])
        w = int(data["width"][i])
        h = int(data["height"][i])
        g["palabras"].append(palabra)
        g["conf"].append(conf)
        g["left"].append(x)
        g["top"].append(y)
        g["right"].append(x + w)
        g["bottom"].append(y + h)

    lineas = []
    for clave, g in grupos.items():
        texto = " ".join(g["palabras"]).strip()
        if not texto:
            continue
        x1, y1 = min(g["left"]), min(g["top"])
        x2, y2 = max(g["right"]), max(g["bottom"])
        confs = [c for c in g["conf"] if c >= 0]
        conf = sum(confs) / len(confs) if confs else 0.0
        lineas.append(
            {
                "texto": texto,
                "texto_norm": _norm(texto),
                "confianza": round(conf, 1),
                "x": x1,
                "y": y1,
                "w": x2 - x1,
                "h": y2 - y1,
                "cx": (x1 + x2) / 2.0,
                "cy": (y1 + y2) / 2.0,
            }
        )

    lineas.sort(key=lambda x: (x["y"], x["x"]))
    return lineas, img.width, img.height


def _estado(conf: float, *, espacial: bool = False) -> str:
    limite_alta = 75.0 if not espacial else 82.0
    if conf >= limite_alta:
        return "Alta"
    if conf >= 50.0:
        return "Confirmar"
    return "Baja"


def _agregar_hallazgo(lista, tipo, linea, pagina, ancho, alto, detalle=""):
    # Evita duplicados de líneas casi idénticas del OCR.
    clave = (tipo, _norm(linea["texto"]))
    if any((h.tipo, _norm(h.texto)) == clave for h in lista):
        return
    lista.append(
        HallazgoFigura(
            tipo=tipo,
            texto=linea["texto"],
            pagina=pagina,
            x_rel=max(0.0, min(1.0, linea["cx"] / max(ancho, 1))),
            y_rel=max(0.0, min(1.0, linea["cy"] / max(alto, 1))),
            confianza=float(linea["confianza"]),
            estado=_estado(float(linea["confianza"])),
            detalle=detalle,
        )
    )


def _detectar_hallazgos(lineas, pagina, ancho, alto):
    hallazgos: list[HallazgoFigura] = []

    for ln in lineas:
        t = ln["texto_norm"]

        # Anclas / equipos.
        if re.search(r"\b(deposito|reservorio|tanque)\b", t):
            if re.search(r"\b(?:1|i)\b", t):
                _agregar_hallazgo(hallazgos, "deposito_1", ln, pagina, ancho, alto)
            elif re.search(r"\b(?:2|ii)\b", t):
                _agregar_hallazgo(hallazgos, "deposito_2", ln, pagina, ancho, alto)
            else:
                _agregar_hallazgo(hallazgos, "deposito", ln, pagina, ancho, alto)

        if re.search(r"\b(bomba|pump)\b", t):
            _agregar_hallazgo(hallazgos, "bomba", ln, pagina, ancho, alto)
        if re.search(r"\b(turbina|turbine)\b", t):
            _agregar_hallazgo(hallazgos, "turbina", ln, pagina, ancho, alto)
        if re.search(r"\b(valvula|valve|compuerta|globo|mariposa|gate|globe|butterfly)\b", t):
            _agregar_hallazgo(hallazgos, "valvula", ln, pagina, ancho, alto)
        if re.search(r"\b(codo|elbow)\b", t):
            _agregar_hallazgo(hallazgos, "codo", ln, pagina, ancho, alto)

        # Variables explícitas. Se guardan como evidencia, no se reinterpreta el valor.
        # OCR suele confundir el dígito 1 con "l" o "i" en etiquetas cortas
        # (por ejemplo z1 -> zl). Se aceptan esas variantes SOLO cuando la
        # etiqueta va seguida de = o :, para no crear variables espurias.
        if re.search(r"\bp\s*(?:1|l|i)\s*(?:=|:)", t):
            _agregar_hallazgo(hallazgos, "P1", ln, pagina, ancho, alto)
        if re.search(r"\bp\s*2\s*(?:=|:)", t):
            _agregar_hallazgo(hallazgos, "P2", ln, pagina, ancho, alto)
        if re.search(r"\bz\s*(?:1|l|i)\s*(?:=|:)", t):
            _agregar_hallazgo(hallazgos, "z1", ln, pagina, ancho, alto)
        if re.search(r"\bz\s*2\s*(?:=|:)", t):
            _agregar_hallazgo(hallazgos, "z2", ln, pagina, ancho, alto)
        if re.search(r"\bh\s*a\s*(?:=|:)", t) or re.search(r"\bha\s*(?:=|:)", t):
            _agregar_hallazgo(hallazgos, "hA", ln, pagina, ancho, alto)
        if re.search(r"\bh\s*r\s*(?:=|:)", t) or re.search(r"\bhr\s*(?:=|:)", t):
            _agregar_hallazgo(hallazgos, "hR", ln, pagina, ancho, alto)
        if re.search(r"\b(?:d|d1|d2)\s*(?:=|:)", t):
            _agregar_hallazgo(hallazgos, "diametro", ln, pagina, ancho, alto)
        if re.search(r"\b(?:l|l1|l2)\s*(?:=|:)", t):
            _agregar_hallazgo(hallazgos, "longitud", ln, pagina, ancho, alto)
        if re.search(r"\bq\s*(?:=|:)", t):
            _agregar_hallazgo(hallazgos, "caudal", ln, pagina, ancho, alto)

    return hallazgos


def _mejor(hallazgos, tipo):
    candidatos = [h for h in hallazgos if h.tipo == tipo]
    if not candidatos:
        return None
    return max(candidatos, key=lambda h: h.confianza)


def _inferir_recorrido(hallazgos):
    d1 = _mejor(hallazgos, "deposito_1")
    d2 = _mejor(hallazgos, "deposito_2")

    # Si no hay números pero hay exactamente dos depósitos, usa orden horizontal.
    if d1 is None or d2 is None:
        deps = [h for h in hallazgos if h.tipo == "deposito"]
        if len(deps) == 2:
            deps = sorted(deps, key=lambda h: h.x_rel)
            d1 = d1 or deps[0]
            d2 = d2 or deps[1]

    if d1 is None or d2 is None:
        return None, None, None

    dx = d2.x_rel - d1.x_rel
    dy = d2.y_rel - d1.y_rel
    den = dx * dx + dy * dy
    if den < 1e-6:
        return d1, d2, None

    for h in hallazgos:
        if h.tipo not in {"bomba", "turbina", "valvula", "codo"}:
            continue
        px = h.x_rel - d1.x_rel
        py = h.y_rel - d1.y_rel
        f = (px * dx + py * dy) / den
        if -0.15 <= f <= 1.15:
            h.fraccion_recorrido = max(0.0, min(1.0, f))
            # La posición espacial es una inferencia; exige mayor confianza.
            if h.estado == "Alta" and h.confianza < 88:
                h.estado = "Confirmar"

    if abs(dx) >= abs(dy):
        orientacion = "izquierda → derecha" if dx > 0 else "derecha → izquierda"
    else:
        orientacion = "arriba → abajo" if dy > 0 else "abajo → arriba"
    return d1, d2, orientacion


def _texto_sugerido(hallazgos, d1, d2, orientacion):
    lineas = []
    if d1 and d2:
        lineas.append(
            "La figura ubica el depósito 1 y el depósito 2 como extremos del sistema"
            + (f", con recorrido gráfico {orientacion}." if orientacion else ".")
        )

    nombres = {
        "bomba": "La bomba",
        "turbina": "La turbina",
        "valvula": "La válvula",
        "codo": "El codo",
    }
    for h in sorted(
        [x for x in hallazgos if x.tipo in nombres],
        key=lambda x: (x.fraccion_recorrido if x.fraccion_recorrido is not None else 99.0, x.x_rel),
    ):
        if h.fraccion_recorrido is not None and d1 and d2:
            pct = 100.0 * h.fraccion_recorrido
            lineas.append(
                f"{nombres[h.tipo]} aparece aproximadamente al {pct:.1f}% del recorrido gráfico entre el depósito 1 y el depósito 2."
            )
        else:
            lineas.append(f"{nombres[h.tipo]} fue detectad{'a' if h.tipo in {'bomba','turbina','valvula'} else 'o'} en la figura; confirme su posición hidráulica.")

    # Las líneas con variables se copian como evidencia para revisión humana.
    for h in hallazgos:
        if h.tipo in {"P1", "P2", "z1", "z2", "hA", "hR", "diametro", "longitud", "caudal"}:
            lineas.append(f"Etiqueta de figura: {h.texto}")

    return "\n".join(dict.fromkeys(lineas))


def interpretar_figura_archivo(nombre: str, datos: bytes, pagina_pdf: int = 1) -> ResultadoFigura:
    img, pagina = _abrir_imagen(nombre, datos, pagina_pdf=pagina_pdf)
    lineas, ancho, alto = _lineas_ocr(img)
    hallazgos = _detectar_hallazgos(lineas, pagina, ancho, alto)
    d1, d2, orientacion = _inferir_recorrido(hallazgos)

    advertencias = [
        "V14.3 interpreta etiquetas y su posición espacial; no convierte distancias en píxeles a metros.",
        "Las posiciones relativas son aproximadas y deben confirmarse antes de agregarlas al enunciado.",
        "Un símbolo sin etiqueta puede no ser reconocido; la interpretación visual completa de símbolos complejos sigue siendo conservadora.",
    ]

    if not hallazgos:
        advertencias.append(
            "No se detectaron etiquetas hidráulicas suficientes en esta página. Puede seguir usando el texto OCR de V14.2."
        )

    confs = [h.confianza for h in hallazgos]
    confianza_global = sum(confs) / len(confs) if confs else 0.0
    texto = _texto_sugerido(hallazgos, d1, d2, orientacion)

    return ResultadoFigura(
        nombre=nombre,
        pagina=pagina,
        ancho=ancho,
        alto=alto,
        hallazgos=[h.como_dict() for h in hallazgos],
        orientacion=orientacion,
        confianza_global=round(confianza_global, 1),
        texto_sugerido=texto,
        advertencias=advertencias,
        lineas_ocr=lineas,
    )


# ============================================================
# V14.3.2 — FUSIÓN ESTRUCTURADA FIGURA -> PREFILL
# ============================================================

def _numero_figura(texto):
    m = re.search(r"-?\d+(?:[\.,]\d+)?", str(texto or ""))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "."))
    except Exception:
        return None


def _valor_presion_kpa_figura(texto):
    m = re.search(r"(?:=|:)\s*(-?\d+(?:[\.,]\d+)?)\s*(pa|kpa|mpa|psi)\b", _norm(texto))
    if not m:
        return None
    v = float(m.group(1).replace(",", "."))
    u = m.group(2)
    if u == "pa":
        return v / 1000.0
    if u == "mpa":
        return v * 1000.0
    if u == "psi":
        return v * 6.894757293168361
    return v


def _valor_longitud_m_figura(texto):
    m = re.search(r"(?:=|:)\s*(-?\d+(?:[\.,]\d+)?)\s*(mm|cm|m|ft|pie|pies|in|pulg|pulgada|pulgadas)\b", _norm(texto))
    if not m:
        return None
    v = float(m.group(1).replace(",", "."))
    u = m.group(2)
    if u == "mm":
        return v / 1000.0
    if u == "cm":
        return v / 100.0
    if u in {"ft", "pie", "pies"}:
        return v * 0.3048
    if u in {"in", "pulg", "pulgada", "pulgadas"}:
        return v * 0.0254
    return v


def _hallazgo_mejor_dict(figura, tipo):
    hall = list((figura or {}).get("hallazgos") or [])
    cand = [h for h in hall if h.get("tipo") == tipo]
    if not cand:
        return None
    return max(cand, key=lambda h: float(h.get("confianza", 0.0) or 0.0))


def _agregar_dato_resultado(resultado, variable, valor, detalle="Detectado en la figura confirmada."):
    datos = resultado.setdefault("datos", [])
    if any(str(d.get("variable", "")).strip().lower() == variable.lower() for d in datos):
        return
    datos.append({"variable": variable, "valores": [valor], "detalle": detalle})


def fusionar_resultado_con_figura(resultado, figura):
    """Fusiona evidencia visual confirmada sin duplicar tramos ni sobrescribir conflictos.

    La figura solo completa valores faltantes del parser textual. Si texto y figura contienen
    valores distintos, conserva el valor textual y añade una advertencia para revisión.

    Las posiciones espaciales de bomba/válvula son exclusivamente gráficas: se convierten a
    fracción del recorrido para dibujar el esquema/LE-LAM, no para alterar pérdidas hidráulicas.
    """
    import copy

    salida = copy.deepcopy(resultado or {})
    pre = salida.setdefault("prefill", {})
    figura = figura or {}
    advertencias = salida.setdefault("advertencias", [])

    # V14.14 — conserva evidencia geométrica confirmada para trazabilidad.
    # No se usa para crear magnitudes físicas; únicamente acompaña el expediente/reporte.
    if figura.get("geometria_v14_14"):
        salida["geometria_v14_14"] = copy.deepcopy(figura.get("geometria_v14_14"))

    def completar(clave, nuevo, etiqueta, tol=1e-8, fmt=None):
        if nuevo is None:
            return
        viejo = pre.get(clave)
        if viejo is None:
            pre[clave] = float(nuevo)
            if fmt:
                _agregar_dato_resultado(salida, etiqueta, fmt(float(nuevo)))
            return
        try:
            if abs(float(viejo) - float(nuevo)) > tol * max(1.0, abs(float(nuevo))):
                advertencias.append(
                    f"V14.3: el texto y la figura difieren para {etiqueta}: "
                    f"texto={float(viejo):.8g}, figura={float(nuevo):.8g}. Se conserva el texto hasta confirmación manual."
                )
        except Exception:
            pass

    # Variables de extremos y máquinas.
    mapa_pres = (("P1", "P1_kpa"), ("P2", "P2_kpa"))
    for tipo, clave in mapa_pres:
        h = _hallazgo_mejor_dict(figura, tipo)
        v = _valor_presion_kpa_figura(h.get("texto", "")) if h else None
        completar(clave, v, tipo, fmt=lambda x: f"{x:.8g} kPa")

    mapa_long = (
        ("z1", "z1_m", "z1"),
        ("z2", "z2_m", "z2"),
        ("hA", "hA_m", "hA"),
        ("hR", "hR_m", "hR"),
    )
    for tipo, clave, etiqueta in mapa_long:
        h = _hallazgo_mejor_dict(figura, tipo)
        v = _valor_longitud_m_figura(h.get("texto", "")) if h else None
        completar(clave, v, etiqueta, fmt=lambda x: f"{x:.8g} m")

    # Los depósitos detectados fijan únicamente la condición de velocidad superficial.
    if _hallazgo_mejor_dict(figura, "deposito_1") and not pre.get("v1_tipo"):
        pre["v1_tipo"] = "deposito"
    if _hallazgo_mejor_dict(figura, "deposito_2") and not pre.get("v2_tipo"):
        pre["v2_tipo"] = "deposito"

    # L y D completan el primer tramo existente. No se crea un segundo tramo por repetir
    # una etiqueta que ya estaba en el OCR general.
    tramos = pre.get("tramos") or []
    if not tramos:
        tramos = [{"numero": 1, "L_m": None, "D_m": None, "material": None,
                   "accesorios": [], "curvas": [], "K_extra": None,
                   "componentes_graficos": []}]
        pre["tramos"] = tramos
    t1 = tramos[0]

    hL = _hallazgo_mejor_dict(figura, "longitud")
    Lfig = _valor_longitud_m_figura(hL.get("texto", "")) if hL else None
    if Lfig is not None:
        if t1.get("L_m") is None:
            t1["L_m"] = float(Lfig)
        elif abs(float(t1["L_m"]) - float(Lfig)) > 1e-8 * max(1.0, abs(float(Lfig))):
            advertencias.append(
                f"V14.3: el texto y la figura difieren para L: texto={float(t1['L_m']):.8g} m, figura={float(Lfig):.8g} m."
            )

    hD = _hallazgo_mejor_dict(figura, "diametro")
    Dfig = _valor_longitud_m_figura(hD.get("texto", "")) if hD else None
    if Dfig is not None:
        if t1.get("D_m") is None:
            t1["D_m"] = float(Dfig)
        elif abs(float(t1["D_m"]) - float(Dfig)) > 1e-8 * max(1.0, abs(float(Dfig))):
            advertencias.append(
                f"V14.3: el texto y la figura difieren para D: texto={float(t1['D_m']):.8g} m, figura={float(Dfig):.8g} m."
            )

    total_L = sum(float(t.get("L_m") or 0.0) for t in tramos)

    # Entrada y salida tienen ubicación física inequívoca si ya fueron reconocidas como accesorios.
    for t in tramos:
        for item in t.get("accesorios") or []:
            nombre = str(item.get("nombre", ""))
            if nombre.startswith("Entrada —"):
                item["posiciones_fraccion"] = [0.0]
                item["posicion_fraccion"] = 0.0
                item["posicion_detectada"] = True
                item["posicion_descripcion"] = "Entrada al inicio del sistema"
            elif nombre == "Salida hacia depósito grande":
                item["posiciones_fraccion"] = [1.0]
                item["posicion_fraccion"] = 1.0
                item["posicion_detectada"] = True
                item["posicion_descripcion"] = "Salida al final del sistema"

    # Posiciones visuales aproximadas de equipos. Solo sirven para el dibujo/LE-LAM.
    hb = _hallazgo_mejor_dict(figura, "bomba")
    if hb and hb.get("fraccion_recorrido") is not None and total_L > 0:
        pre["posicion_bomba_m"] = float(hb["fraccion_recorrido"]) * total_L
        pre["posicion_bomba_aproximada_figura"] = True

    ht = _hallazgo_mejor_dict(figura, "turbina")
    if ht and ht.get("fraccion_recorrido") is not None and total_L > 0:
        pre["posicion_turbina_m"] = float(ht["fraccion_recorrido"]) * total_L
        pre["posicion_turbina_aproximada_figura"] = True

    hv = _hallazgo_mejor_dict(figura, "valvula")
    if hv and hv.get("fraccion_recorrido") is not None:
        fv = min(max(float(hv["fraccion_recorrido"]), 0.0), 1.0)
        # Solo aplica la posición a una válvula ya reconocida por el parser textual.
        for t in tramos:
            valvulas = [a for a in (t.get("accesorios") or []) if "Válvula" in str(a.get("nombre", ""))]
            if valvulas:
                valvulas[0]["posiciones_fraccion"] = [fv]
                valvulas[0]["posicion_fraccion"] = fv
                valvulas[0]["posicion_detectada"] = True
                valvulas[0]["posicion_descripcion"] = "Posición aproximada confirmada desde figura V14.3"
                break

    advertencias.append(
        "V14.3: los valores faltantes se completaron con la figura confirmada; "
        "las posiciones derivadas de píxeles se usan solo para representación gráfica."
    )
    salida["fusion_figura_v143"] = True
    return salida
