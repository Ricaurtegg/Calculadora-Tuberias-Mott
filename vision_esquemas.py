"""Reconocimiento geométrico conservador de esquemas hidráulicos — V14.4.1.

Objetivo
--------
Complementar el OCR/interpretación espacial de V14.3 con evidencia de la figura
misma mediante OpenCV. Esta capa NO calcula longitudes físicas desde píxeles y
NO modifica el solver hidráulico.

Detecta de forma conservadora:
- trazado principal de tubería (línea dominante);
- candidatos a depósitos/reservorios (rectángulos grandes conectados a la línea);
- candidato a bomba (círculo sobre la tubería);
- candidato a válvula (símbolo tipo bow-tie/X sobre la tubería);
- orden relativo de componentes a lo largo del recorrido;
- posibles cambios de sección solo como advertencia geométrica (sin asignar D).

Las detecciones sin etiqueta OCR se marcan como "Confirmar". El usuario debe
revisarlas antes de fusionarlas con V14.3.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from io import BytesIO
from pathlib import Path
import math

EXTENSIONES_VISION = (".png", ".jpg", ".jpeg", ".pdf")


class ErrorVisionEsquema(ValueError):
    pass


@dataclass
class CandidatoGeometrico:
    tipo: str
    x_rel: float
    y_rel: float
    confianza: float
    estado: str
    detalle: str
    bbox_rel: tuple[float, float, float, float] | None = None
    fraccion_recorrido: float | None = None

    def como_dict(self):
        return asdict(self)


@dataclass
class ResultadoVision:
    nombre: str
    pagina: int
    ancho: int
    alto: int
    tuberia_principal: dict | None
    depositos: list[dict]
    equipos: list[dict]
    cambios_seccion: list[dict]
    orden: list[str]
    confianza_global: float
    advertencias: list[str]
    imagen_anotada_png: bytes | None = None

    def como_dict(self):
        d = asdict(self)
        return d


def _cv2_numpy():
    try:
        import cv2
        import numpy as np
    except ImportError as e:
        raise ErrorVisionEsquema(
            "Falta OpenCV. Instale dentro del .venv con: python -m pip install opencv-python"
        ) from e
    return cv2, np


def _abrir_cv(nombre: str, datos: bytes, pagina_pdf: int = 1):
    cv2, np = _cv2_numpy()
    ext = Path(nombre).suffix.lower()
    if ext not in EXTENSIONES_VISION:
        raise ErrorVisionEsquema(
            f"V14.4 admite PNG, JPG, JPEG y PDF para visión geométrica; recibido: {ext or 'sin extensión'}."
        )

    if ext in (".png", ".jpg", ".jpeg"):
        arr = np.frombuffer(datos, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ErrorVisionEsquema("OpenCV no pudo decodificar la imagen.")
        return img, 1

    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf
        except ImportError as e:
            raise ErrorVisionEsquema(
                "Falta PyMuPDF para analizar figuras dentro de PDF. Instale: python -m pip install pymupdf"
            ) from e

    try:
        doc = pymupdf.open(stream=datos, filetype="pdf")
    except Exception as e:
        raise ErrorVisionEsquema(f"No se pudo abrir el PDF: {e}") from e

    try:
        if len(doc) == 0:
            raise ErrorVisionEsquema("El PDF no contiene páginas.")
        pagina_pdf = int(pagina_pdf)
        if not 1 <= pagina_pdf <= len(doc):
            raise ErrorVisionEsquema(
                f"Página fuera de rango: {pagina_pdf}. El PDF tiene {len(doc)} página(s)."
            )
        page = doc[pagina_pdf - 1]
        pix = page.get_pixmap(matrix=pymupdf.Matrix(2.0, 2.0), alpha=False)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
        elif pix.n == 3:
            arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        else:
            arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
        return arr, pagina_pdf
    finally:
        doc.close()




def _enmascarar_texto_opcional(img):
    """Blanquea cajas OCR para que letras/títulos no se confundan con tuberías o círculos.

    Si Tesseract no está disponible, devuelve la imagen sin cambios. La detección
    geométrica sigue funcionando para esquemas sin texto.
    """
    cv2, np = _cv2_numpy()
    out = img.copy()
    try:
        import pytesseract
        from lectura_archivos import ocr_disponible
        disponible, ruta = ocr_disponible()
        if not disponible:
            return out
        pytesseract.pytesseract.tesseract_cmd = ruta
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        data = pytesseract.image_to_data(
            rgb,
            config="--psm 11",
            output_type=pytesseract.Output.DICT,
        )
        n = len(data.get("text", []))
        h, w = img.shape[:2]
        pad = max(2, int(0.004 * min(w, h)))
        for i in range(n):
            txt = str(data["text"][i] or "").strip()
            if not txt:
                continue
            try:
                conf = float(data["conf"][i])
            except Exception:
                conf = -1
            if conf < 0:
                continue
            x = int(data["left"][i]); y = int(data["top"][i])
            ww = int(data["width"][i]); hh = int(data["height"][i])
            x1=max(0,x-pad); y1=max(0,y-pad); x2=min(w,x+ww+pad); y2=min(h,y+hh+pad)
            cv2.rectangle(out,(x1,y1),(x2,y2),(255,255,255),-1)
    except Exception:
        return img.copy()
    return out

def _clip01(v):
    return max(0.0, min(1.0, float(v)))


def _normalizar_lineas_hough(lines):
    """Normaliza la salida de cv2.HoughLinesP a una matriz (N, 4).

    OpenCV puede devolver HoughLinesP como (N, 1, 4) o (N, 4)
    dependiendo de la versión/build/plataforma. V14.4.1 acepta ambas
    representaciones para evitar errores de indexación.
    """
    _, np = _cv2_numpy()
    if lines is None:
        return np.empty((0, 4), dtype=np.float64)

    arr = np.asarray(lines)
    if arr.size == 0:
        return np.empty((0, 4), dtype=np.float64)

    # Elimina dimensiones unitarias: (N,1,4)->(N,4), (1,1,4)->(4,),
    # (N,4,1)->(N,4), etc.
    arr = np.squeeze(arr)

    if arr.ndim == 1:
        if arr.size < 4:
            raise ErrorVisionEsquema(
                f"Salida inesperada de HoughLinesP: forma {np.asarray(lines).shape}."
            )
        arr = arr.reshape(1, -1)
    elif arr.ndim > 2:
        arr = arr.reshape(-1, arr.shape[-1])

    if arr.ndim != 2 or arr.shape[1] < 4:
        raise ErrorVisionEsquema(
            f"Salida inesperada de HoughLinesP: forma {np.asarray(lines).shape}."
        )

    return arr[:, :4]


def _distance_point_line(x, y, linea):
    if not linea:
        return 1e9
    x1, y1 = linea["x1"], linea["y1"]
    x2, y2 = linea["x2"], linea["y2"]
    dx, dy = x2 - x1, y2 - y1
    den = math.hypot(dx, dy)
    if den < 1e-9:
        return math.hypot(x - x1, y - y1)
    return abs(dy * x - dx * y + x2 * y1 - y2 * x1) / den


def _projection_fraction(x, y, linea):
    if not linea:
        return None
    x1, y1 = linea["x1"], linea["y1"]
    x2, y2 = linea["x2"], linea["y2"]
    dx, dy = x2 - x1, y2 - y1
    den = dx * dx + dy * dy
    if den < 1e-9:
        return None
    f = ((x - x1) * dx + (y - y1) * dy) / den
    return _clip01(f)


def _detectar_tuberia(gray):
    cv2, np = _cv2_numpy()
    h, w = gray.shape[:2]
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    min_len = max(35, int(0.07 * w))
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180.0,
        threshold=max(30, int(0.025 * w)),
        minLineLength=min_len,
        maxLineGap=max(12, int(0.025 * w)),
    )
    if lines is None:
        return None, []

    candidatos = []
    for raw in _normalizar_lineas_hough(lines):
        x1, y1, x2, y2 = map(float, raw)
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy)
        if L < min_len:
            continue
        angle = math.degrees(math.atan2(dy, dx))
        # Normaliza para evitar 180°.
        if angle > 90:
            angle -= 180
        if angle < -90:
            angle += 180
        # Los esquemas típicos de tuberías en serie suelen ser horizontales o suavemente inclinados.
        if abs(angle) > 38:
            continue
        m = dy / dx if abs(dx) > 1e-9 else 0.0
        cx = 0.5 * (x1 + x2)
        cy = 0.5 * (y1 + y2)
        b = cy - m * cx
        candidatos.append({
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "L": L, "angle": angle, "m": m, "b": b,
        })

    if not candidatos:
        return None, []

    # Agrupa segmentos de ángulo/intercepto similares. El score favorece una línea
    # hidráulica larga aunque esté cortada por bomba/válvula.
    clusters = []
    for seg in sorted(candidatos, key=lambda s: s["L"], reverse=True):
        colocado = False
        for c in clusters:
            if abs(seg["angle"] - c["angle_med"]) <= 5.5 and abs(seg["b"] - c["b_med"]) <= 0.045 * h:
                c["segs"].append(seg)
                pesos = [s["L"] for s in c["segs"]]
                den = sum(pesos)
                c["angle_med"] = sum(s["angle"] * s["L"] for s in c["segs"]) / den
                c["b_med"] = sum(s["b"] * s["L"] for s in c["segs"]) / den
                colocado = True
                break
        if not colocado:
            clusters.append({"segs": [seg], "angle_med": seg["angle"], "b_med": seg["b"]})

    for c in clusters:
        xs = []
        ys = []
        total = 0.0
        for s in c["segs"]:
            xs.extend([s["x1"], s["x2"]])
            ys.extend([s["y1"], s["y2"]])
            total += s["L"]
        c["score"] = total
        c["span_x"] = max(xs) - min(xs)
        # favorece continuidad horizontal además de longitud total
        c["score2"] = total + 0.75 * c["span_x"]

    best = max(clusters, key=lambda c: c["score2"])
    pts = []
    for s in best["segs"]:
        pts.append((s["x1"], s["y1"]))
        pts.append((s["x2"], s["y2"]))
    arr = np.asarray(pts, dtype=np.float32)
    xs = arr[:, 0]
    ys = arr[:, 1]
    if float(xs.max() - xs.min()) < 1.0:
        return None, candidatos
    coef = np.polyfit(xs, ys, 1)
    m, b = float(coef[0]), float(coef[1])
    x1 = float(xs.min())
    x2 = float(xs.max())
    y1 = m * x1 + b
    y2 = m * x2 + b
    span = math.hypot(x2 - x1, y2 - y1)
    conf = 55.0 + min(40.0, 40.0 * span / max(w, 1))
    return {
        "x1": x1, "y1": y1, "x2": x2, "y2": y2,
        "angulo_deg": math.degrees(math.atan2(y2-y1, x2-x1)),
        "confianza": round(min(conf, 95.0), 1),
    }, candidatos


def _detectar_depositos(gray, linea):
    cv2, np = _cv2_numpy()
    h, w = gray.shape[:2]
    # Umbral invertido para contornos negros sobre fondo claro.
    _, bw = cv2.threshold(gray, 210, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(bw, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    candidatos = []
    area_img = float(w * h)
    for cnt in contours:
        area = abs(cv2.contourArea(cnt))
        if not (0.003 * area_img <= area <= 0.22 * area_img):
            continue
        peri = cv2.arcLength(cnt, True)
        if peri <= 0:
            continue
        approx = cv2.approxPolyDP(cnt, 0.025 * peri, True)
        if len(approx) not in (4, 5):
            continue
        x, y, ww, hh = cv2.boundingRect(cnt)
        if ww < 0.035 * w or hh < 0.08 * h:
            continue
        aspect = ww / max(hh, 1)
        if not (0.25 <= aspect <= 2.2):
            continue
        cx = x + ww / 2.0
        cy = y + hh / 2.0
        if linea:
            # El eje de la tubería debe cruzar o quedar muy cerca del rectángulo.
            if _distance_point_line(cx, cy, linea) > max(0.22 * hh, 0.06 * h):
                # También acepta si la línea cruza verticalmente el bbox.
                f = _projection_fraction(cx, cy, linea)
                if f is None:
                    continue
        # Los depósitos útiles para un sistema en serie suelen estar cerca de extremos.
        f = _projection_fraction(cx, cy, linea) if linea else None
        prox_extremo = 0.5
        if f is not None:
            prox_extremo = min(f, 1.0 - f)
        conf = 58.0 + max(0.0, 25.0 * (1.0 - min(prox_extremo / 0.35, 1.0)))
        candidatos.append({
            "cx": cx, "cy": cy, "x": x, "y": y, "w": ww, "h": hh,
            "confianza": min(conf, 90.0), "f": f,
        })

    # Elimina rectángulos anidados/duplicados por cercanía.
    candidatos.sort(key=lambda c: (c["confianza"], c["w"]*c["h"]), reverse=True)
    limpios = []
    for c in candidatos:
        if any(math.hypot(c["cx"]-d["cx"], c["cy"]-d["cy"]) < 0.06 * w for d in limpios):
            continue
        limpios.append(c)

    if linea and len(limpios) >= 2:
        # Selecciona candidatos extremos según proyección.
        con_f = [c for c in limpios if c["f"] is not None]
        if len(con_f) >= 2:
            con_f.sort(key=lambda c: c["f"])
            return [con_f[0], con_f[-1]]
    return limpios[:2]


def _detectar_bomba(gray, linea, excluir=None):
    cv2, np = _cv2_numpy()
    h, w = gray.shape[:2]
    blur = cv2.GaussianBlur(gray, (7, 7), 1.4)
    min_r = max(12, int(0.018 * min(w, h)))
    max_r = max(min_r + 2, int(0.11 * min(w, h)))
    circles = cv2.HoughCircles(
        blur,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(30, int(0.08*w)),
        param1=100,
        param2=28,
        minRadius=min_r,
        maxRadius=max_r,
    )
    if circles is None:
        return []
    edges = cv2.Canny(gray, 50, 150)
    out = []
    for x, y, r in np.round(circles[0]).astype(int):
        if linea and _distance_point_line(x, y, linea) > max(0.055*h, 0.55*r):
            continue
        if excluir and any(math.hypot(x-e[0], y-e[1]) < max(r, e[2]) * 1.35 for e in excluir):
            continue
        f = _projection_fraction(x, y, linea) if linea else None
        if f is not None and not (0.08 <= f <= 0.92):
            continue

        # Verifica que exista realmente un arco alrededor de gran parte de la
        # circunferencia. Una válvula en X puede engañar a HoughCircles, pero
        # normalmente no presenta cobertura radial suficiente.
        hits = 0
        muestras = 72
        for k in range(muestras):
            a = 2.0 * math.pi * k / muestras
            px = int(round(x + r * math.cos(a)))
            py = int(round(y + r * math.sin(a)))
            x1=max(0,px-2); x2=min(w,px+3); y1=max(0,py-2); y2=min(h,py+3)
            if x1 < x2 and y1 < y2 and edges[y1:y2, x1:x2].max() > 0:
                hits += 1
        cobertura = hits / muestras
        if cobertura < 0.42:
            continue

        conf = 66.0 + 22.0 * min(cobertura, 1.0)
        if linea:
            dist = _distance_point_line(x, y, linea)
            conf += max(0.0, 8.0 * (1.0 - dist / max(r, 1)))
        out.append({"cx":float(x),"cy":float(y),"r":float(r),"f":f,"confianza":min(conf,94.0),"cobertura_arco":cobertura})
    out.sort(key=lambda c:c["confianza"], reverse=True)
    return out[:2]


def _detectar_valvula(gray, linea, circulos=None):
    cv2, np = _cv2_numpy()
    h, w = gray.shape[:2]
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi/180.0,
        threshold=max(18, int(0.012*w)),
        minLineLength=max(10, int(0.018*w)),
        maxLineGap=max(4, int(0.006*w)),
    )
    if lines is None:
        return []
    diags = []
    for x1,y1,x2,y2 in _normalizar_lineas_hough(lines):
        dx, dy = float(x2-x1), float(y2-y1)
        L = math.hypot(dx,dy)
        if L < 8:
            continue
        ang = math.degrees(math.atan2(dy,dx))
        a = abs(ang)
        if a > 90:
            a = 180-a
        if not (18 <= a <= 72):
            continue
        cx, cy = 0.5*(x1+x2), 0.5*(y1+y2)
        if linea and _distance_point_line(cx,cy,linea) > 0.09*h:
            continue
        diags.append({"x1":x1,"y1":y1,"x2":x2,"y2":y2,"cx":cx,"cy":cy,"L":L})

    if len(diags) < 2:
        return []

    # Agrupa diagonales cercanas en x; un bow-tie suele aportar varias diagonales.
    diags.sort(key=lambda d:d["cx"])
    grupos=[]
    ancho_grupo=max(24.0,0.055*w)
    for d in diags:
        puesto=False
        for g in grupos:
            if abs(d["cx"]-g["cx_med"]) <= ancho_grupo:
                g["items"].append(d)
                g["cx_med"] = sum(x["cx"] for x in g["items"])/len(g["items"])
                g["cy_med"] = sum(x["cy"] for x in g["items"])/len(g["items"])
                puesto=True
                break
        if not puesto:
            grupos.append({"items":[d],"cx_med":d["cx"],"cy_med":d["cy"]})

    out=[]
    for g in grupos:
        n=len(g["items"])
        if n < 2:
            continue
        cx,cy=g["cx_med"],g["cy_med"]
        if circulos and any(math.hypot(cx-c["cx"],cy-c["cy"]) < 1.5*c["r"] for c in circulos):
            continue
        f=_projection_fraction(cx,cy,linea) if linea else None
        if f is not None and not (0.08 <= f <= 0.92):
            continue
        # exige diagonales de ambos signos para parecer una X/bow-tie
        signos=[]
        for d in g["items"]:
            slope=(d["y2"]-d["y1"])/max(abs(d["x2"]-d["x1"]),1)
            signos.append(1 if slope>0 else -1)
        if len(set(signos)) < 2:
            continue
        conf = min(88.0, 58.0 + 7.0*n)
        out.append({"cx":cx,"cy":cy,"f":f,"confianza":conf,"n_diagonales":n})
    out.sort(key=lambda c:c["confianza"], reverse=True)
    return out[:3]


def _detectar_cambios_seccion(gray, linea):
    """Detecta candidatos muy conservadores a cambio de sección.

    Busca agrupaciones de trazos verticales cortos sobre la tubería. No asigna D,
    solo devuelve una señal para revisión. Se evita reportar cerca de bomba/válvula
    en la fusión posterior.
    """
    cv2, np = _cv2_numpy()
    h,w=gray.shape[:2]
    edges=cv2.Canny(gray,50,150)
    lines=cv2.HoughLinesP(edges,1,np.pi/180,threshold=max(18,int(0.012*w)),minLineLength=max(8,int(0.018*h)),maxLineGap=5)
    if lines is None or not linea:
        return []
    cand=[]
    for x1,y1,x2,y2 in _normalizar_lineas_hough(lines):
        dx,dy=float(x2-x1),float(y2-y1)
        L=math.hypot(dx,dy)
        if L<8: continue
        ang=abs(math.degrees(math.atan2(dy,dx)))
        if not (70 <= ang <= 110):
            continue
        cx,cy=0.5*(x1+x2),0.5*(y1+y2)
        if _distance_point_line(cx,cy,linea) > 0.07*h:
            continue
        f=_projection_fraction(cx,cy,linea)
        if f is None or not (0.12 <= f <= 0.88):
            continue
        cand.append({"cx":cx,"cy":cy,"f":f,"L":L})
    # Agrupa trazos muy próximos; requiere al menos dos para un posible cambio geométrico.
    cand.sort(key=lambda c:c["cx"])
    grupos=[]
    for c in cand:
        if grupos and abs(c["cx"]-grupos[-1][0]["cx"])<0.025*w:
            grupos[-1].append(c)
        else:
            grupos.append([c])
    out=[]
    for g in grupos:
        if len(g)>=2:
            f=sum(x["f"] for x in g)/len(g)
            out.append({"fraccion_recorrido":f,"confianza":55.0,"estado":"Confirmar","detalle":"Posible cambio de sección detectado por trazos geométricos; confirme tipo y diámetros."})
    return out


def _anotar(img, linea, depositos, bombas, valvulas, cambios):
    cv2, np = _cv2_numpy()
    out=img.copy()
    if linea:
        p1=(int(linea["x1"]),int(linea["y1"]))
        p2=(int(linea["x2"]),int(linea["y2"]))
        cv2.line(out,p1,p2,(255,0,0),3)
        cv2.putText(out,"Tuberia principal",(max(5,p1[0]),max(25,p1[1]-12)),cv2.FONT_HERSHEY_SIMPLEX,0.7,(255,0,0),2,cv2.LINE_AA)
    for i,d in enumerate(depositos,1):
        x,y,ww,hh=int(d["x"]),int(d["y"]),int(d["w"]),int(d["h"])
        cv2.rectangle(out,(x,y),(x+ww,y+hh),(0,170,0),3)
        cv2.putText(out,f"Deposito? {i}",(x,max(25,y-8)),cv2.FONT_HERSHEY_SIMPLEX,0.65,(0,170,0),2,cv2.LINE_AA)
    for c in bombas:
        cv2.circle(out,(int(c["cx"]),int(c["cy"])),int(c["r"]),(0,0,255),3)
        cv2.putText(out,"Bomba?",(int(c["cx"])-35,int(c["cy"])-int(c["r"])-8),cv2.FONT_HERSHEY_SIMPLEX,0.65,(0,0,255),2,cv2.LINE_AA)
    for v in valvulas:
        x,y=int(v["cx"]),int(v["cy"])
        cv2.rectangle(out,(x-35,y-35),(x+35,y+35),(0,140,255),2)
        cv2.putText(out,"Valvula?",(x-35,y-42),cv2.FONT_HERSHEY_SIMPLEX,0.65,(0,140,255),2,cv2.LINE_AA)
    for c in cambios:
        if not linea: continue
        f=float(c["fraccion_recorrido"])
        x=linea["x1"]+f*(linea["x2"]-linea["x1"])
        y=linea["y1"]+f*(linea["y2"]-linea["y1"])
        cv2.circle(out,(int(x),int(y)),18,(160,0,160),2)
    ok, enc=cv2.imencode('.png',out)
    return bytes(enc.tobytes()) if ok else None


def analizar_geometria_archivo(nombre: str, datos: bytes, pagina_pdf: int = 1) -> ResultadoVision:
    cv2, np = _cv2_numpy()
    img,pagina=_abrir_cv(nombre,datos,pagina_pdf=pagina_pdf)
    h,w=img.shape[:2]
    img_geometria = _enmascarar_texto_opcional(img)
    gray=cv2.cvtColor(img_geometria,cv2.COLOR_BGR2GRAY)
    gray=cv2.GaussianBlur(gray,(3,3),0)

    linea,_=_detectar_tuberia(gray)
    depositos=_detectar_depositos(gray,linea)
    excluir=[(d["cx"],d["cy"],0.5*max(d["w"],d["h"])) for d in depositos]
    # Primero busca la geometría de válvula. Un bow-tie/X puede generar un falso
    # círculo en HoughCircles; por eso se filtra la bomba contra estas zonas.
    valvulas=_detectar_valvula(gray,linea,circulos=None)
    bombas=_detectar_bomba(gray,linea,excluir=excluir)
    if valvulas:
        bombas=[
            b for b in bombas
            if not any(math.hypot(b["cx"]-v["cx"], b["cy"]-v["cy"]) < max(0.06*w, 1.8*b["r"]) for v in valvulas)
        ]
    cambios=_detectar_cambios_seccion(gray,linea)

    # Filtra posibles cambios que caen encima de equipos detectados.
    cambios_fil=[]
    for c in cambios:
        f=float(c["fraccion_recorrido"])
        if any(b.get("f") is not None and abs(f-b["f"])<0.06 for b in bombas):
            continue
        if any(v.get("f") is not None and abs(f-v["f"])<0.06 for v in valvulas):
            continue
        cambios_fil.append(c)
    cambios=cambios_fil

    # Asigna depósitos 1/2 por recorrido, solo si hay dos candidatos claros.
    deps_out=[]
    if len(depositos)>=2:
        dep_sorted=sorted(depositos,key=lambda d:(d.get("f") if d.get("f") is not None else d["cx"]))
        elegidos=[dep_sorted[0],dep_sorted[-1]]
        tipos=["deposito_1","deposito_2"]
    else:
        elegidos=depositos
        tipos=["deposito"]*len(elegidos)
    for tipo,d in zip(tipos,elegidos):
        deps_out.append(CandidatoGeometrico(
            tipo=tipo,
            x_rel=_clip01(d["cx"]/w),
            y_rel=_clip01(d["cy"]/h),
            confianza=round(float(d["confianza"]),1),
            estado="Confirmar",
            detalle="Rectángulo grande conectado/cercano al trazado principal. Confirmar que corresponde a un depósito.",
            bbox_rel=(d["x"]/w,d["y"]/h,d["w"]/w,d["h"]/h),
            fraccion_recorrido=d.get("f"),
        ).como_dict())

    equipos=[]
    for b in bombas:
        equipos.append(CandidatoGeometrico(
            tipo="bomba",
            x_rel=_clip01(b["cx"]/w),y_rel=_clip01(b["cy"]/h),
            confianza=round(float(b["confianza"]),1),estado="Confirmar",
            detalle="Círculo detectado sobre el trazado principal; posible símbolo de bomba. Requiere confirmación.",
            bbox_rel=((b["cx"]-b["r"])/w,(b["cy"]-b["r"])/h,2*b["r"]/w,2*b["r"]/h),
            fraccion_recorrido=b.get("f"),
        ).como_dict())
    for v in valvulas:
        equipos.append(CandidatoGeometrico(
            tipo="valvula",
            x_rel=_clip01(v["cx"]/w),y_rel=_clip01(v["cy"]/h),
            confianza=round(float(v["confianza"]),1),estado="Confirmar",
            detalle=f"Grupo de {v['n_diagonales']} trazos diagonales de ambos sentidos sobre la tubería; posible símbolo de válvula.",
            bbox_rel=None,fraccion_recorrido=v.get("f"),
        ).como_dict())

    orden=[]
    items=[]
    for d in deps_out:
        f=d.get("fraccion_recorrido")
        items.append((0.0 if d["tipo"]=="deposito_1" else 1.0 if d["tipo"]=="deposito_2" else (f if f is not None else 0.5),d["tipo"]))
    for e in equipos:
        f=e.get("fraccion_recorrido")
        if f is not None:
            items.append((float(f),e["tipo"]))
    for c in cambios:
        items.append((float(c["fraccion_recorrido"]),"cambio_seccion"))
    orden=[x[1] for x in sorted(items,key=lambda z:z[0])]

    tuberia_out=None
    if linea:
        tuberia_out={
            "x1_rel":_clip01(linea["x1"]/w),"y1_rel":_clip01(linea["y1"]/h),
            "x2_rel":_clip01(linea["x2"]/w),"y2_rel":_clip01(linea["y2"]/h),
            "angulo_deg":round(float(linea["angulo_deg"]),2),
            "confianza":round(float(linea["confianza"]),1),
            "detalle":"Línea/recorrido dominante inferido a partir de segmentos de Hough. No representa una longitud física."
        }

    confs=[]
    if tuberia_out: confs.append(tuberia_out["confianza"])
    confs += [float(d["confianza"]) for d in deps_out]
    confs += [float(e["confianza"]) for e in equipos]
    confianza_global=round(sum(confs)/len(confs),1) if confs else 0.0

    advertencias=[
        "V14.4 usa geometría de píxeles únicamente para reconocer símbolos, orden y posiciones relativas.",
        "No se convierten píxeles a metros ni se inventan diámetros, longitudes, cotas o pérdidas.",
        "Toda detección geométrica sin etiqueta OCR se marca como Confirmar antes de fusionarse con V14.3.",
    ]
    if linea is None:
        advertencias.append("No se identificó un trazado principal de tubería con confianza suficiente.")
    if len(deps_out)<2:
        advertencias.append("No se identificaron dos depósitos geométricos claros; conserve la interpretación OCR como fuente principal.")

    anotada=_anotar(img,linea,depositos,bombas,valvulas,cambios)
    return ResultadoVision(
        nombre=nombre,pagina=pagina,ancho=w,alto=h,
        tuberia_principal=tuberia_out,depositos=deps_out,equipos=equipos,
        cambios_seccion=cambios,orden=orden,confianza_global=confianza_global,
        advertencias=advertencias,imagen_anotada_png=anotada,
    )


def fusionar_figura_con_geometria(figura: dict, geometria: dict) -> dict:
    """Refina V14.3 con evidencia geométrica confirmada.

    - Si existe una etiqueta OCR del mismo tipo, solo actualiza posición relativa.
    - Si no existe etiqueta, agrega candidato marcado Confirmar.
    - No agrega valores hidráulicos (hA, D, L, etc.).
    - Recalcula fracción de recorrido usando depósito 1 -> depósito 2.
    """
    import copy
    f=copy.deepcopy(figura or {})
    g=copy.deepcopy(geometria or {})
    hall=list(f.get("hallazgos") or [])

    candidatos=[]
    candidatos += list(g.get("depositos") or [])
    candidatos += list(g.get("equipos") or [])

    for c in candidatos:
        tipo=c.get("tipo")
        mismos=[h for h in hall if h.get("tipo")==tipo]
        if mismos:
            # Refina la mejor coincidencia OCR con la geometría.
            h=max(mismos,key=lambda x:float(x.get("confianza",0) or 0))
            h["x_rel"]=float(c.get("x_rel",h.get("x_rel",0.5)))
            h["y_rel"]=float(c.get("y_rel",h.get("y_rel",0.5)))
            if c.get("fraccion_recorrido") is not None:
                h["fraccion_recorrido"]=float(c["fraccion_recorrido"])
            det=str(h.get("detalle","")).strip()
            extra="Posición refinada con geometría V14.4 confirmada."
            h["detalle"]=(det+" "+extra).strip()
        else:
            # Símbolo no rotulado: se conserva como hipótesis, nunca como dato de alta confianza.
            hall.append({
                "tipo":tipo,
                "texto":f"{tipo.replace('_',' ').title()} inferido por geometría",
                "pagina":int(g.get("pagina",1) or 1),
                "x_rel":float(c.get("x_rel",0.5)),
                "y_rel":float(c.get("y_rel",0.5)),
                "confianza":min(float(c.get("confianza",60) or 60),79.0),
                "estado":"Confirmar",
                "detalle":str(c.get("detalle", "Detección geométrica V14.4; requiere confirmación.")),
                "fraccion_recorrido":c.get("fraccion_recorrido"),
                "fuente":"geometria_v14_4",
            })

    # Recalcula fracciones entre depósitos geométricos/OCR.
    def mejor(tipo):
        xs=[h for h in hall if h.get("tipo")==tipo]
        return max(xs,key=lambda x:float(x.get("confianza",0) or 0)) if xs else None
    d1,d2=mejor("deposito_1"),mejor("deposito_2")
    if d1 and d2:
        dx=float(d2.get("x_rel",0))-float(d1.get("x_rel",0))
        dy=float(d2.get("y_rel",0))-float(d1.get("y_rel",0))
        den=dx*dx+dy*dy
        if den>1e-9:
            for h in hall:
                if h.get("tipo") not in {"bomba","turbina","valvula","codo"}:
                    continue
                px=float(h.get("x_rel",0))-float(d1.get("x_rel",0))
                py=float(h.get("y_rel",0))-float(d1.get("y_rel",0))
                frac=(px*dx+py*dy)/den
                h["fraccion_recorrido"]=_clip01(frac)

    f["hallazgos"]=hall
    f["geometria_v14_4"]=g
    advert=list(f.get("advertencias") or [])
    advert.append("V14.4 refinó posiciones/símbolos con geometría confirmada; no convirtió píxeles a unidades físicas.")
    f["advertencias"]=list(dict.fromkeys(advert))
    return f

# ============================================================================
# V14.14 — Visión geométrica 2.0
# ============================================================================
# Esta sección extiende V14.4.1 conservando su API pública. Las funciones
# redefinidas al final sustituyen únicamente el análisis/fusión de alto nivel;
# los helpers históricos permanecen disponibles para compatibilidad y pruebas.

VERSION_VISION = "V14.14"


@dataclass
class ResultadoVisionV1414:
    nombre: str
    pagina: int
    ancho: int
    alto: int
    tuberia_principal: dict | None
    depositos: list[dict]
    equipos: list[dict]
    cambios_seccion: list[dict]
    orden: list[str]
    confianza_global: float
    advertencias: list[str]
    imagen_anotada_png: bytes | None = None
    version: str = VERSION_VISION
    recorrido_polilinea: dict | None = None
    niveles_relativos: list[dict] | None = None
    cambios_nivel: list[dict] | None = None
    perspectiva: dict | None = None
    calidad_imagen: dict | None = None

    def como_dict(self):
        return asdict(self)


def _ordenar_cuatro_puntos_v1414(pts):
    """Orden TL, TR, BR, BL para una cuadrícula de cuatro puntos."""
    _, np = _cv2_numpy()
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).reshape(-1)
    return np.array([
        pts[np.argmin(s)],  # TL
        pts[np.argmin(d)],  # TR
        pts[np.argmax(s)],  # BR
        pts[np.argmax(d)],  # BL
    ], dtype=np.float32)


def _corregir_perspectiva_v1414(img):
    """Rectifica una hoja fotografiada solo cuando existe evidencia fuerte.

    No intenta 'enderezar' la tubería: únicamente corrige el plano de una hoja
    completa detectada como cuadrilátero grande. De esta forma una pendiente
    real del esquema no se confunde con inclinación de cámara.
    """
    cv2, np = _cv2_numpy()
    h, w = img.shape[:2]
    area_img = float(w * h)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    # Busca tanto una hoja clara sobre fondo oscuro como una hoja delimitada.
    candidatos = []
    for modo in (cv2.THRESH_BINARY, cv2.THRESH_BINARY_INV):
        _, bw = cv2.threshold(blur, 0, 255, modo + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = abs(cv2.contourArea(cnt))
            ratio = area / max(area_img, 1.0)
            if not (0.42 <= ratio <= 0.97):
                continue
            peri = cv2.arcLength(cnt, True)
            if peri <= 0:
                continue
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            if len(approx) != 4 or not cv2.isContourConvex(approx):
                continue
            pts = approx.reshape(4, 2).astype(np.float32)
            # Debe cubrir buena parte de ambos ejes.
            if np.ptp(pts[:, 0]) < 0.65 * w or np.ptp(pts[:, 1]) < 0.65 * h:
                continue
            candidatos.append((ratio, pts))

    if not candidatos:
        return img, {
            "aplicada": False,
            "confianza": 0.0,
            "detalle": "No se detectó una hoja/cuadrilátero grande con evidencia suficiente; se conservó la imagen original.",
            "esquinas_rel": None,
        }

    ratio, pts = max(candidatos, key=lambda x: x[0])
    rect = _ordenar_cuatro_puntos_v1414(pts)
    tl, tr, br, bl = rect
    ancho_a = float(np.linalg.norm(br - bl))
    ancho_b = float(np.linalg.norm(tr - tl))
    alto_a = float(np.linalg.norm(tr - br))
    alto_b = float(np.linalg.norm(tl - bl))
    nw = int(round(max(ancho_a, ancho_b)))
    nh = int(round(max(alto_a, alto_b)))
    if nw < 200 or nh < 200:
        return img, {
            "aplicada": False,
            "confianza": 0.0,
            "detalle": "El cuadrilátero detectado era demasiado pequeño para una rectificación segura.",
            "esquinas_rel": None,
        }

    dst = np.array([[0, 0], [nw - 1, 0], [nw - 1, nh - 1], [0, nh - 1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(img, M, (nw, nh), borderValue=(255, 255, 255))

    # Evita rectificaciones extremas que suelen ser falsos positivos.
    factor_area = (nw * nh) / max(area_img, 1.0)
    if not (0.35 <= factor_area <= 1.45):
        return img, {
            "aplicada": False,
            "confianza": 0.0,
            "detalle": "Se descartó una rectificación geométricamente extrema.",
            "esquinas_rel": None,
        }

    esquinas_rel = [[round(float(x / w), 5), round(float(y / h), 5)] for x, y in rect]
    conf = min(96.0, 70.0 + 25.0 * min(max((ratio - 0.42) / 0.45, 0.0), 1.0))
    return warped, {
        "aplicada": True,
        "confianza": round(conf, 1),
        "detalle": "Se rectificó el plano de una hoja fotografiada antes del análisis geométrico. Las coordenadas posteriores son relativas a la hoja rectificada.",
        "esquinas_rel": esquinas_rel,
    }


def _calidad_imagen_v1414(img):
    cv2, np = _cv2_numpy()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    lap = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    contraste = float(gray.std())
    h, w = gray.shape[:2]
    min_dim = min(w, h)
    if lap < 20 or contraste < 18 or min_dim < 320:
        nivel = "Baja"
    elif lap < 55 or contraste < 28 or min_dim < 650:
        nivel = "Media"
    else:
        nivel = "Alta"
    return {
        "nivel": nivel,
        "nitidez_laplaciana": round(lap, 2),
        "contraste_std": round(contraste, 2),
        "ancho_px": int(w),
        "alto_px": int(h),
        "detalle": "Métrica heurística para decidir cuánto confiar en la geometría; no altera magnitudes hidráulicas.",
    }


def _detectar_depositos_libres_v1414(gray):
    """Depósitos rectangulares sin asumir una línea dominante."""
    cv2, np = _cv2_numpy()
    h, w = gray.shape[:2]
    _, bw = cv2.threshold(gray, 210, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(bw, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    area_img = float(w * h)
    cand = []
    for cnt in contours:
        area = abs(cv2.contourArea(cnt))
        if not (0.003 * area_img <= area <= 0.22 * area_img):
            continue
        peri = cv2.arcLength(cnt, True)
        if peri <= 0:
            continue
        approx = cv2.approxPolyDP(cnt, 0.025 * peri, True)
        if len(approx) not in (4, 5):
            continue
        x, y, ww, hh = cv2.boundingRect(cnt)
        if ww < 0.035 * w or hh < 0.075 * h:
            continue
        aspect = ww / max(hh, 1)
        if not (0.22 <= aspect <= 2.4):
            continue
        # Los depósitos suelen ser cajas relativamente grandes; reduce etiquetas.
        if area < 0.008 * area_img and hh < 0.15 * h:
            continue
        cx, cy = x + ww / 2.0, y + hh / 2.0
        conf = 58.0 + min(26.0, 18.0 * area / max(0.04 * area_img, 1.0))
        cand.append({"cx": cx, "cy": cy, "x": x, "y": y, "w": ww, "h": hh, "confianza": min(conf, 90.0)})

    cand.sort(key=lambda c: (c["w"] * c["h"], c["confianza"]), reverse=True)
    limpios = []
    diag = math.hypot(w, h)
    for c in cand:
        if any(math.hypot(c["cx"] - d["cx"], c["cy"] - d["cy"]) < 0.045 * diag for d in limpios):
            continue
        limpios.append(c)
    if len(limpios) <= 2:
        return limpios
    # Para sistemas en serie prioriza cajas extremas en x, sin afirmar cuál es 1/2 físicamente.
    izq = min(limpios, key=lambda c: c["cx"])
    der = max(limpios, key=lambda c: c["cx"])
    return [izq, der] if izq is not der else [izq]


def _cluster_endpoints_v1414(segmentos, tol):
    """Crea nodos aproximados para extremos Hough."""
    nodes = []
    seg_nodes = []
    for s in segmentos:
        pair = []
        for p in ((s["x1"], s["y1"]), (s["x2"], s["y2"])):
            idx = None
            best = tol
            for i, n in enumerate(nodes):
                d = math.hypot(p[0] - n["x"], p[1] - n["y"])
                if d <= best:
                    idx, best = i, d
            if idx is None:
                nodes.append({"x": float(p[0]), "y": float(p[1]), "pts": [p]})
                idx = len(nodes) - 1
            else:
                nodes[idx]["pts"].append(p)
                xs = [q[0] for q in nodes[idx]["pts"]]
                ys = [q[1] for q in nodes[idx]["pts"]]
                nodes[idx]["x"] = float(sum(xs) / len(xs))
                nodes[idx]["y"] = float(sum(ys) / len(ys))
            pair.append(idx)
        seg_nodes.append(tuple(pair))
    return nodes, seg_nodes


def _point_in_padded_box_v1414(x, y, box, pad=0.0):
    return (box["x"] - pad <= x <= box["x"] + box["w"] + pad and
            box["y"] - pad <= y <= box["y"] + box["h"] + pad)


def _detectar_recorrido_polilinea_v1414(gray, depositos=None):
    """Detecta un recorrido de tubería 2D sin restringirlo a una sola pendiente."""
    cv2, np = _cv2_numpy()
    h, w = gray.shape[:2]
    diag = math.hypot(w, h)
    # Retira las cajas de depósitos antes de Hough para que sus bordes no se
    # conviertan por error en parte del recorrido. La tubería exterior permanece.
    gray_ruta = gray.copy()
    for d in list(depositos or []):
        pad_box=max(8,int(0.012*min(w,h)))
        x1=max(0,int(d["x"])-pad_box); y1=max(0,int(d["y"])-pad_box)
        x2=min(w-1,int(d["x"]+d["w"])+pad_box); y2=min(h-1,int(d["y"]+d["h"])+pad_box)
        cv2.rectangle(gray_ruta,(x1,y1),(x2,y2),255,-1)
    edges = cv2.Canny(gray_ruta, 45, 145, apertureSize=3)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180.0,
        threshold=max(20, int(0.015 * diag)),
        minLineLength=max(20, int(0.028 * diag)),
        maxLineGap=max(8, int(0.015 * diag)),
    )
    if lines is None:
        return None

    segmentos = []
    deps = list(depositos or [])
    for raw in _normalizar_lineas_hough(lines):
        x1, y1, x2, y2 = map(float, raw)
        L = math.hypot(x2 - x1, y2 - y1)
        if L < max(18.0, 0.025 * diag):
            continue
        mx, my = 0.5 * (x1 + x2), 0.5 * (y1 + y2)
        # Descarta bordes internos de depósitos, pero conserva conexiones próximas.
        if any(_point_in_padded_box_v1414(mx, my, d, pad=-0.05 * min(d["w"], d["h"])) for d in deps):
            continue
        # Descarta casi todo el borde de la imagen.
        if (mx < 0.01 * w or mx > 0.99 * w or my < 0.01 * h or my > 0.99 * h):
            continue
        ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
        # Orientación indiferente al sentido.
        if ang > 90:
            ang -= 180
        if ang < -90:
            ang += 180
        segmentos.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "L": L, "angulo": ang, "virtual": False})

    if not segmentos:
        return None

    # Primero crea nodos con tolerancia pequeña.
    tol = max(8.0, 0.010 * diag)
    nodes, seg_nodes = _cluster_endpoints_v1414(segmentos, tol)
    adj = {i: [] for i in range(len(nodes))}
    for si, (a, b) in enumerate(seg_nodes):
        if a == b:
            continue
        L = segmentos[si]["L"]
        adj[a].append((b, L, si, False))
        adj[b].append((a, L, si, False))

    # Puentes conservadores para cortes por símbolos de bomba/válvula.
    bridge_max = 0.075 * diag
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            d = math.hypot(nodes[i]["x"] - nodes[j]["x"], nodes[i]["y"] - nodes[j]["y"])
            if not (tol < d <= bridge_max):
                continue
            # Solo puentea cuando ambos nodos ya participan en trazos y la unión no es
            # casi vertical muy larga respecto a su avance horizontal.
            if not adj[i] or not adj[j]:
                continue
            dx = abs(nodes[i]["x"] - nodes[j]["x"])
            dy = abs(nodes[i]["y"] - nodes[j]["y"])
            if dx < 0.25 * d and dy > 0.055 * h:
                continue
            # Coste algo mayor para preferir líneas reales.
            adj[i].append((j, d * 1.18, None, True))
            adj[j].append((i, d * 1.18, None, True))

    def nearest_node(tx, ty):
        return min(range(len(nodes)), key=lambda i: math.hypot(nodes[i]["x"] - tx, nodes[i]["y"] - ty))

    if len(deps) >= 2:
        ds = sorted(deps, key=lambda d: d["cx"])
        izq, der = ds[0], ds[-1]
        start = nearest_node(izq["x"] + izq["w"], izq["cy"])
        end = nearest_node(der["x"], der["cy"])
    else:
        start = min(range(len(nodes)), key=lambda i: nodes[i]["x"])
        end = max(range(len(nodes)), key=lambda i: nodes[i]["x"])

    # Dijkstra. Se penalizan puentes pero se permiten para cruzar equipos.
    import heapq
    INF = float("inf")
    dist = [INF] * len(nodes)
    prev = [None] * len(nodes)
    dist[start] = 0.0
    heap = [(0.0, start)]
    while heap:
        du, u = heapq.heappop(heap)
        if du != dist[u]:
            continue
        if u == end:
            break
        for v, cost, si, virtual in adj[u]:
            nd = du + cost
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = (u, si, virtual)
                heapq.heappush(heap, (nd, v))

    if not math.isfinite(dist[end]):
        # Fallback: línea dominante histórica.
        linea, _ = _detectar_tuberia(gray)
        if not linea:
            return None
        verts = [(linea["x1"], linea["y1"]), (linea["x2"], linea["y2"])]
        return _construir_recorrido_v1414(verts, w, h, virtuales=0, confianza_base=float(linea["confianza"]))

    path_nodes = [end]
    virtuales = 0
    cur = end
    while cur != start and prev[cur] is not None:
        p, _, virt = prev[cur]
        virtuales += int(bool(virt))
        path_nodes.append(p)
        cur = p
    path_nodes.reverse()
    verts = [(nodes[i]["x"], nodes[i]["y"]) for i in path_nodes]

    # Simplifica puntos casi colineales.
    simp = []
    for p in verts:
        if not simp:
            simp.append(p); continue
        if math.hypot(p[0] - simp[-1][0], p[1] - simp[-1][1]) < 4:
            continue
        simp.append(p)
    changed = True
    while changed and len(simp) > 2:
        changed = False
        out = [simp[0]]
        for i in range(1, len(simp) - 1):
            a, b, c = out[-1], simp[i], simp[i + 1]
            v1 = (b[0] - a[0], b[1] - a[1]); v2 = (c[0] - b[0], c[1] - b[1])
            n1 = math.hypot(*v1); n2 = math.hypot(*v2)
            if n1 > 0 and n2 > 0:
                cosang = max(-1.0, min(1.0, (v1[0]*v2[0] + v1[1]*v2[1])/(n1*n2)))
                delta = math.degrees(math.acos(cosang))
                if delta < 7.0:
                    changed = True
                    continue
            out.append(b)
        out.append(simp[-1])
        simp = out

    span_x = abs(simp[-1][0] - simp[0][0]) if len(simp) >= 2 else 0.0
    conf = 58.0 + min(28.0, 30.0 * span_x / max(w, 1)) - min(18.0, 5.0 * virtuales)
    if len(deps) >= 2:
        conf += 5.0
    return _construir_recorrido_v1414(simp, w, h, virtuales=virtuales, confianza_base=min(max(conf, 35.0), 95.0))


def _construir_recorrido_v1414(vertices, w, h, virtuales=0, confianza_base=70.0):
    if len(vertices) < 2:
        return None
    lens = [math.hypot(vertices[i+1][0]-vertices[i][0], vertices[i+1][1]-vertices[i][1]) for i in range(len(vertices)-1)]
    total = sum(lens)
    if total <= 1e-9:
        return None
    segs = []
    acc = 0.0
    for i, L in enumerate(lens):
        a, b = vertices[i], vertices[i+1]
        ang = math.degrees(math.atan2(b[1]-a[1], b[0]-a[0]))
        aa = abs(ang)
        if aa > 90:
            aa = 180 - aa
        if aa <= 12:
            ori = "horizontal"
        elif aa >= 78:
            ori = "vertical"
        else:
            ori = "inclinado"
        segs.append({
            "indice": i + 1,
            "x1_rel": _clip01(a[0]/w), "y1_rel": _clip01(a[1]/h),
            "x2_rel": _clip01(b[0]/w), "y2_rel": _clip01(b[1]/h),
            "angulo_deg": round(float(ang), 2),
            "orientacion": ori,
            "longitud_px": round(float(L), 2),
            "fraccion_inicio": round(acc/total, 5),
            "fraccion_fin": round((acc+L)/total, 5),
        })
        acc += L
    return {
        "vertices_rel": [[round(_clip01(x/w), 5), round(_clip01(y/h), 5)] for x, y in vertices],
        "segmentos": segs,
        "longitud_total_px": round(float(total), 2),
        "puentes_inferidos": int(virtuales),
        "confianza": round(float(confianza_base), 1),
        "detalle": "Recorrido poligonal en coordenadas de imagen. Las longitudes en píxeles NO se convierten a unidades físicas.",
    }


def _proyectar_polilinea_v1414(x, y, recorrido, w, h):
    verts_rel = list((recorrido or {}).get("vertices_rel") or [])
    if len(verts_rel) < 2:
        return None, 1e9, None
    verts = [(float(px)*w, float(py)*h) for px, py in verts_rel]
    lens = [math.hypot(verts[i+1][0]-verts[i][0], verts[i+1][1]-verts[i][1]) for i in range(len(verts)-1)]
    total = sum(lens)
    best = None
    acc = 0.0
    for i, L in enumerate(lens):
        ax, ay = verts[i]; bx, by = verts[i+1]
        dx, dy = bx-ax, by-ay
        den = dx*dx + dy*dy
        if den <= 1e-12:
            acc += L; continue
        t = ((x-ax)*dx + (y-ay)*dy)/den
        t = max(0.0, min(1.0, t))
        qx, qy = ax+t*dx, ay+t*dy
        d = math.hypot(x-qx, y-qy)
        f = (acc + t*L)/max(total, 1e-9)
        if best is None or d < best[1]:
            ang = math.degrees(math.atan2(dy, dx))
            best = (f, d, ang)
        acc += L
    return best if best is not None else (None, 1e9, None)


def _detectar_circulos_polilinea_v1414(gray, recorrido, excluir=None):
    cv2, np = _cv2_numpy()
    h, w = gray.shape[:2]
    blur = cv2.GaussianBlur(gray, (7, 7), 1.4)
    min_r = max(12, int(0.018 * min(w, h)))
    max_r = max(min_r + 2, int(0.11 * min(w, h)))
    circles = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, dp=1.2,
        minDist=max(30, int(0.07*w)), param1=100, param2=27,
        minRadius=min_r, maxRadius=max_r)
    if circles is None:
        return []
    edges = cv2.Canny(gray, 50, 150)
    out = []
    for x, y, r in np.round(circles[0]).astype(int):
        f, dist, _ = _proyectar_polilinea_v1414(x, y, recorrido, w, h)
        if f is None or dist > max(0.055*h, 0.65*r) or not (0.05 <= f <= 0.95):
            continue
        if excluir and any(math.hypot(x-e[0], y-e[1]) < max(r, e[2])*1.3 for e in excluir):
            continue
        hits = 0
        for k in range(72):
            a = 2*math.pi*k/72
            px = int(round(x+r*math.cos(a))); py=int(round(y+r*math.sin(a)))
            x1=max(0,px-2); x2=min(w,px+3); y1=max(0,py-2); y2=min(h,py+3)
            if x1<x2 and y1<y2 and edges[y1:y2,x1:x2].max()>0:
                hits += 1
        cobertura = hits/72
        if cobertura < 0.40:
            continue
        # Busca triángulo dentro del círculo: se trata como equipo rotativo ambiguo.
        mask = np.zeros_like(gray)
        cv2.circle(mask, (x,y), max(3,int(0.72*r)), 255, -1)
        roi_edges = cv2.bitwise_and(edges, edges, mask=mask)
        contours,_ = cv2.findContours(roi_edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        triangulo = False
        for cnt in contours:
            ar = abs(cv2.contourArea(cnt))
            if not (0.03*math.pi*r*r <= ar <= 0.75*math.pi*r*r):
                continue
            per = cv2.arcLength(cnt, True)
            if per <= 0: continue
            ap = cv2.approxPolyDP(cnt, 0.06*per, True)
            if len(ap) == 3:
                triangulo = True; break
        tipo = "equipo_rotativo" if triangulo else "bomba"
        conf = min(94.0, 64.0 + 24.0*cobertura)
        out.append({"tipo":tipo,"cx":float(x),"cy":float(y),"r":float(r),"f":float(f),"confianza":conf,"triangulo_interno":triangulo,"cobertura_arco":cobertura})
    out.sort(key=lambda c:c["confianza"], reverse=True)
    return out[:3]


def _detectar_valvulas_polilinea_v1414(gray, recorrido, circulos=None):
    cv2, np = _cv2_numpy()
    h,w=gray.shape[:2]
    edges=cv2.Canny(gray,50,150)
    lines=cv2.HoughLinesP(edges,1,np.pi/180,threshold=max(16,int(0.01*w)),minLineLength=max(9,int(0.014*w)),maxLineGap=max(4,int(0.006*w)))
    if lines is None:
        return []
    diags=[]
    for x1,y1,x2,y2 in _normalizar_lineas_hough(lines):
        dx,dy=float(x2-x1),float(y2-y1); L=math.hypot(dx,dy)
        if L < 8: continue
        ang=math.degrees(math.atan2(dy,dx)); a=abs(ang); a=180-a if a>90 else a
        if not (18<=a<=72): continue
        cx,cy=0.5*(x1+x2),0.5*(y1+y2)
        f,dist,_=_proyectar_polilinea_v1414(cx,cy,recorrido,w,h)
        if f is None or dist>0.075*h: continue
        diags.append({"cx":cx,"cy":cy,"x1":x1,"y1":y1,"x2":x2,"y2":y2,"f":f})
    grupos=[]; ancho=max(22.0,0.045*w)
    for d in sorted(diags,key=lambda q:q["f"]):
        puesto=False
        for g in grupos:
            if abs(d["f"]-g["f_med"])<=0.04 and math.hypot(d["cx"]-g["cx"],d["cy"]-g["cy"])<=ancho:
                g["items"].append(d)
                g["cx"]=sum(q["cx"] for q in g["items"])/len(g["items"])
                g["cy"]=sum(q["cy"] for q in g["items"])/len(g["items"])
                g["f_med"]=sum(q["f"] for q in g["items"])/len(g["items"])
                puesto=True; break
        if not puesto:
            grupos.append({"items":[d],"cx":d["cx"],"cy":d["cy"],"f_med":d["f"]})
    out=[]
    for g in grupos:
        if len(g["items"])<2: continue
        cx,cy=g["cx"],g["cy"]
        if circulos and any(math.hypot(cx-c["cx"],cy-c["cy"]) < 1.5*c["r"] for c in circulos):
            continue
        signs=[]
        for d in g["items"]:
            dx=float(d["x2"]-d["x1"]); dy=float(d["y2"]-d["y1"])
            signs.append(1 if dy*dx>0 else -1)
        if len(set(signs))<2: continue
        out.append({"cx":cx,"cy":cy,"f":float(g["f_med"]),"confianza":min(90.0,58+7*len(g["items"])),"n_diagonales":len(g["items"])})
    out.sort(key=lambda c:c["f"])
    # Un símbolo bow-tie ancho puede producir dos grupos Hough separados.
    # Fusiona candidatos cercanos en el recorrido para conservar una sola válvula.
    clean=[]
    for c in out:
        if clean and abs(float(c["f"])-float(clean[-1]["f"])) < 0.095:
            a=clean[-1]
            wa=max(float(a.get("confianza",1)),1.0); wb=max(float(c.get("confianza",1)),1.0)
            den=wa+wb
            a["cx"]=(a["cx"]*wa+c["cx"]*wb)/den
            a["cy"]=(a["cy"]*wa+c["cy"]*wb)/den
            a["f"]=(a["f"]*wa+c["f"]*wb)/den
            a["n_diagonales"]=int(a.get("n_diagonales",0))+int(c.get("n_diagonales",0))
            a["confianza"]=max(a["confianza"],c["confianza"])
        else:
            clean.append(dict(c))
    clean.sort(key=lambda c:c["confianza"], reverse=True)
    return clean[:5]


def _detectar_cambios_seccion_polilinea_v1414(gray, recorrido):
    cv2, np = _cv2_numpy()
    h,w=gray.shape[:2]; diag=math.hypot(w,h)
    edges=cv2.Canny(gray,50,150)
    lines=cv2.HoughLinesP(edges,1,np.pi/180,threshold=max(14,int(0.009*diag)),minLineLength=max(8,int(0.012*diag)),maxLineGap=4)
    if lines is None or not recorrido:
        return []
    cand=[]
    for x1,y1,x2,y2 in _normalizar_lineas_hough(lines):
        dx,dy=float(x2-x1),float(y2-y1); L=math.hypot(dx,dy)
        if not (8 <= L <= 0.12*diag):
            continue
        cx,cy=0.5*(x1+x2),0.5*(y1+y2)
        f,dist,local_ang=_proyectar_polilinea_v1414(cx,cy,recorrido,w,h)
        if f is None or dist>0.055*h or not (0.08<=f<=0.92):
            continue
        ang=math.degrees(math.atan2(dy,dx))
        diff=abs(((ang-local_ang+90)%180)-90)
        if not (55<=diff<=90):
            continue
        cand.append({"f":f,"cx":cx,"cy":cy,"L":L})
    groups=[]
    for c in sorted(cand,key=lambda q:q["f"]):
        if groups and abs(c["f"]-sum(x["f"] for x in groups[-1])/len(groups[-1]))<0.025:
            groups[-1].append(c)
        else:
            groups.append([c])
    out=[]
    for g in groups:
        if len(g)<2: continue
        f=sum(x["f"] for x in g)/len(g)
        out.append({"fraccion_recorrido":round(float(f),5),"confianza":58.0,"estado":"Confirmar","detalle":"Posible cambio de sección detectado por trazos perpendiculares al recorrido local; confirme tipo y diámetros."})
    # Elimina grupos casi idénticos.
    clean=[]
    for c in out:
        if clean and abs(c["fraccion_recorrido"]-clean[-1]["fraccion_recorrido"])<0.04:
            continue
        clean.append(c)
    return clean


def _niveles_relativos_v1414(recorrido):
    if not recorrido:
        return [], []
    segs=list(recorrido.get("segmentos") or [])
    horizontales=[]
    for s in segs:
        if s.get("orientacion") != "horizontal":
            continue
        y=0.5*(float(s["y1_rel"])+float(s["y2_rel"]))
        horizontales.append({"y_rel":y,"x1":min(float(s["x1_rel"]),float(s["x2_rel"])),"x2":max(float(s["x1_rel"]),float(s["x2_rel"]))})
    clusters=[]
    for q in sorted(horizontales,key=lambda x:x["y_rel"]):
        if clusters and abs(q["y_rel"]-sum(x["y_rel"] for x in clusters[-1])/len(clusters[-1]))<=0.035:
            clusters[-1].append(q)
        else:
            clusters.append([q])
    niveles=[]
    for i,g in enumerate(clusters,1):
        y=sum(x["y_rel"] for x in g)/len(g)
        niveles.append({"nivel":i,"y_rel":round(y,5),"x_min_rel":round(min(x["x1"] for x in g),5),"x_max_rel":round(max(x["x2"] for x in g),5),"estado":"Relativo","detalle":"Nivel gráfico relativo; no equivale a una elevación z sin escala/dato explícito."})
    cambios=[]
    verts=list(recorrido.get("vertices_rel") or [])
    for i in range(len(verts)-1):
        x1,y1=map(float,verts[i]); x2,y2=map(float,verts[i+1])
        dy=y2-y1
        if abs(dy)<0.055:
            continue
        cambios.append({"indice":i+1,"sentido_dibujo":"sube" if dy<0 else "baja","delta_y_rel":round(abs(dy),5),"estado":"Confirmar","detalle":"Cambio vertical observado en el dibujo; no se convierte automáticamente a z física."})
    return niveles,cambios


def _anotar_v1414(img, recorrido, depositos, equipos, cambios):
    cv2, np = _cv2_numpy()
    out=img.copy(); h,w=out.shape[:2]
    if recorrido:
        verts=[(int(round(x*w)),int(round(y*h))) for x,y in recorrido.get("vertices_rel",[])]
        for i in range(len(verts)-1):
            cv2.line(out,verts[i],verts[i+1],(255,0,0),4)
        if verts:
            cv2.putText(out,"Recorrido V14.14",(max(5,verts[0][0]),max(25,verts[0][1]-12)),cv2.FONT_HERSHEY_SIMPLEX,0.68,(255,0,0),2,cv2.LINE_AA)
    for i,d in enumerate(depositos,1):
        x,y,ww,hh=int(d["x"]),int(d["y"]),int(d["w"]),int(d["h"])
        cv2.rectangle(out,(x,y),(x+ww,y+hh),(0,170,0),3)
        cv2.putText(out,f"Deposito? {i}",(x,max(25,y-8)),cv2.FONT_HERSHEY_SIMPLEX,0.62,(0,170,0),2,cv2.LINE_AA)
    for e in equipos:
        x,y=int(e["cx"]),int(e["cy"])
        if e.get("tipo") in {"bomba","equipo_rotativo"}:
            r=int(e.get("r",28)); cv2.circle(out,(x,y),r,(0,0,255),3)
            lab="Rotativo?" if e.get("tipo")=="equipo_rotativo" else "Bomba?"
            cv2.putText(out,lab,(x-r,max(25,y-r-8)),cv2.FONT_HERSHEY_SIMPLEX,0.60,(0,0,255),2,cv2.LINE_AA)
        elif e.get("tipo")=="valvula":
            cv2.rectangle(out,(x-32,y-32),(x+32,y+32),(0,140,255),2)
            cv2.putText(out,"Valvula?",(x-32,max(25,y-38)),cv2.FONT_HERSHEY_SIMPLEX,0.60,(0,140,255),2,cv2.LINE_AA)
    if recorrido:
        verts_rel=recorrido.get("vertices_rel") or []
        for c in cambios:
            f=float(c["fraccion_recorrido"])
            # Reusa proyección aproximando punto por longitud relativa.
            segs=recorrido.get("segmentos") or []
            px=py=None
            for s in segs:
                fi=float(s["fraccion_inicio"]); ff=float(s["fraccion_fin"])
                if fi-1e-9<=f<=ff+1e-9:
                    t=(f-fi)/max(ff-fi,1e-9)
                    px=(float(s["x1_rel"])+t*(float(s["x2_rel"])-float(s["x1_rel"])))*w
                    py=(float(s["y1_rel"])+t*(float(s["y2_rel"])-float(s["y1_rel"])))*h
                    break
            if px is not None:
                cv2.circle(out,(int(px),int(py)),17,(160,0,160),2)
    ok,enc=cv2.imencode('.png',out)
    return bytes(enc.tobytes()) if ok else None


def analizar_geometria_archivo(nombre: str, datos: bytes, pagina_pdf: int = 1) -> ResultadoVisionV1414:
    """V14.14: análisis geométrico 2.0, compatible con la API V14.4."""
    cv2, np = _cv2_numpy()
    img_original,pagina=_abrir_cv(nombre,datos,pagina_pdf=pagina_pdf)
    img,perspectiva=_corregir_perspectiva_v1414(img_original)
    h,w=img.shape[:2]
    calidad=_calidad_imagen_v1414(img)
    img_geo=_enmascarar_texto_opcional(img)
    gray=cv2.cvtColor(img_geo,cv2.COLOR_BGR2GRAY)
    gray=cv2.GaussianBlur(gray,(3,3),0)

    depositos_raw=_detectar_depositos_libres_v1414(gray)
    recorrido=_detectar_recorrido_polilinea_v1414(gray,depositos_raw)

    # Fallback histórico si la nueva ruta no se pudo reconstruir.
    linea_hist,_=_detectar_tuberia(gray)
    if recorrido is None and linea_hist:
        recorrido=_construir_recorrido_v1414([(linea_hist["x1"],linea_hist["y1"]),(linea_hist["x2"],linea_hist["y2"])],w,h,0,float(linea_hist["confianza"]))

    # Cuerda inicio-fin para compatibilidad V14.4; NO sustituye la polilínea.
    linea=None
    if recorrido and len(recorrido.get("vertices_rel") or [])>=2:
        a=recorrido["vertices_rel"][0]; b=recorrido["vertices_rel"][-1]
        x1,y1=float(a[0])*w,float(a[1])*h; x2,y2=float(b[0])*w,float(b[1])*h
        linea={"x1":x1,"y1":y1,"x2":x2,"y2":y2,"angulo_deg":math.degrees(math.atan2(y2-y1,x2-x1)),"confianza":float(recorrido.get("confianza",70))}
    elif linea_hist:
        linea=linea_hist

    excluir=[(d["cx"],d["cy"],0.5*max(d["w"],d["h"])) for d in depositos_raw]
    circulos=_detectar_circulos_polilinea_v1414(gray,recorrido,excluir=excluir) if recorrido else []
    valvulas=_detectar_valvulas_polilinea_v1414(gray,recorrido,circulos=circulos) if recorrido else []
    # Evita dobles detecciones válvula/círculo.
    circulos=[c for c in circulos if not any(math.hypot(c["cx"]-v["cx"],c["cy"]-v["cy"])<max(0.055*w,1.7*c["r"]) for v in valvulas)]
    cambios=_detectar_cambios_seccion_polilinea_v1414(gray,recorrido) if recorrido else []
    for c in list(cambios):
        f=float(c["fraccion_recorrido"])
        if any(abs(f-e.get("f",-9))<0.055 for e in circulos+valvulas):
            cambios.remove(c)

    # Ordena depósitos por fracción real sobre la polilínea, no solo x.
    deps_out=[]
    deps_calc=[]
    for d in depositos_raw:
        if recorrido:
            f,dist,_=_proyectar_polilinea_v1414(d["cx"],d["cy"],recorrido,w,h)
        else:
            f,dist=None,1e9
        q=dict(d); q["f"]=f; q["dist_ruta"]=dist; deps_calc.append(q)
    if len(deps_calc)>=2:
        ds=sorted(deps_calc,key=lambda d:(d.get("f") if d.get("f") is not None else d["cx"]))
        elegidos=[ds[0],ds[-1]]; tipos=["deposito_1","deposito_2"]
    else:
        elegidos=deps_calc; tipos=["deposito"]*len(elegidos)
    for tipo,d in zip(tipos,elegidos):
        deps_out.append(CandidatoGeometrico(
            tipo=tipo,x_rel=_clip01(d["cx"]/w),y_rel=_clip01(d["cy"]/h),
            confianza=round(float(d["confianza"]),1),estado="Confirmar",
            detalle="Rectángulo grande detectado como candidato a depósito. Confirmar identidad y condición de superficie/presión.",
            bbox_rel=(d["x"]/w,d["y"]/h,d["w"]/w,d["h"]/h),fraccion_recorrido=d.get("f")
        ).como_dict())

    equipos=[]
    for c in circulos:
        tipo=c.get("tipo","bomba")
        if tipo=="equipo_rotativo":
            detalle="Símbolo circular con geometría interna detectado sobre el recorrido: posible bomba o turbina. La geometría sola no decide cuál; confirmar con etiqueta/enunciado."
            estado="Confirmar"
            conf=min(float(c["confianza"]),82.0)
        else:
            detalle="Símbolo circular simple sobre el recorrido; candidato a bomba. Confirmar con etiqueta/enunciado."
            estado="Confirmar"; conf=float(c["confianza"])
        equipos.append(CandidatoGeometrico(
            tipo=tipo,x_rel=_clip01(c["cx"]/w),y_rel=_clip01(c["cy"]/h),
            confianza=round(conf,1),estado=estado,detalle=detalle,
            bbox_rel=((c["cx"]-c["r"])/w,(c["cy"]-c["r"])/h,2*c["r"]/w,2*c["r"]/h),fraccion_recorrido=c.get("f")
        ).como_dict())
    for v in valvulas:
        equipos.append(CandidatoGeometrico(
            tipo="valvula",x_rel=_clip01(v["cx"]/w),y_rel=_clip01(v["cy"]/h),
            confianza=round(float(v["confianza"]),1),estado="Confirmar",
            detalle=f"Grupo de {v['n_diagonales']} trazos diagonales de ambos sentidos próximo al recorrido; posible válvula.",
            bbox_rel=None,fraccion_recorrido=v.get("f")
        ).como_dict())

    niveles,cambios_nivel=_niveles_relativos_v1414(recorrido)

    items=[]
    for d in deps_out:
        f=d.get("fraccion_recorrido")
        if d["tipo"]=="deposito_1": f=0.0 if f is None else f
        if d["tipo"]=="deposito_2": f=1.0 if f is None else f
        if f is not None: items.append((float(f),d["tipo"]))
    for e in equipos:
        if e.get("fraccion_recorrido") is not None: items.append((float(e["fraccion_recorrido"]),e["tipo"]))
    for c in cambios:
        items.append((float(c["fraccion_recorrido"]),"cambio_seccion"))
    orden=[x[1] for x in sorted(items,key=lambda z:z[0])]

    tuberia_out=None
    if linea:
        tuberia_out={
            "x1_rel":_clip01(linea["x1"]/w),"y1_rel":_clip01(linea["y1"]/h),
            "x2_rel":_clip01(linea["x2"]/w),"y2_rel":_clip01(linea["y2"]/h),
            "angulo_deg":round(float(linea["angulo_deg"]),2),
            "confianza":round(float(linea["confianza"]),1),
            "detalle":"Cuerda entre extremos del recorrido para compatibilidad V14.4. Use recorrido_polilinea para geometría escalonada/inclinada. No representa longitud física."
        }

    confs=[]
    if recorrido: confs.append(float(recorrido.get("confianza",0)))
    confs += [float(d["confianza"]) for d in deps_out]
    confs += [float(e["confianza"]) for e in equipos]
    confianza=round(sum(confs)/len(confs),1) if confs else 0.0
    if calidad.get("nivel")=="Baja": confianza=max(0.0,round(confianza-10.0,1))

    advertencias=[
        "V14.14 usa geometría de imagen para recorrido, posiciones, niveles relativos y símbolos; no convierte píxeles a metros.",
        "Los ascensos/descensos del dibujo son evidencia visual relativa y no sustituyen z1/z2 ni cotas explícitas.",
        "Un símbolo rotativo sin etiqueta se conserva como bomba/turbina por confirmar; la visión no decide su función hidráulica por apariencia sola.",
    ]
    if perspectiva.get("aplicada"):
        advertencias.append("Se aplicó rectificación de perspectiva de la hoja antes de detectar la geometría.")
    if calidad.get("nivel")=="Baja":
        advertencias.append("La calidad visual es baja; confirme manualmente todas las detecciones geométricas.")
    if not recorrido:
        advertencias.append("No se reconstruyó un recorrido poligonal con confianza suficiente; conserve OCR/texto como fuente principal.")
    if len(deps_out)<2:
        advertencias.append("No se identificaron dos depósitos geométricos claros.")

    raw_eq=[]
    for c in circulos:
        raw_eq.append(c)
    for v in valvulas:
        q=dict(v); q["tipo"]="valvula"; raw_eq.append(q)
    anotada=_anotar_v1414(img,recorrido,elegidos,raw_eq,cambios)

    return ResultadoVisionV1414(
        nombre=nombre,pagina=pagina,ancho=w,alto=h,tuberia_principal=tuberia_out,
        depositos=deps_out,equipos=equipos,cambios_seccion=cambios,orden=orden,
        confianza_global=confianza,advertencias=advertencias,imagen_anotada_png=anotada,
        recorrido_polilinea=recorrido,niveles_relativos=niveles,cambios_nivel=cambios_nivel,
        perspectiva=perspectiva,calidad_imagen=calidad,
    )


def fusionar_figura_con_geometria(figura: dict, geometria: dict) -> dict:
    """V14.14: fusión conservadora con OCR/V14.3, compatible con V14.4.

    Mejora adicional: un círculo/rotativo ambiguo puede refinar una etiqueta OCR
    'bomba' o 'turbina' cercana sin inventar cuál de las dos es.
    """
    import copy
    f=copy.deepcopy(figura or {})
    g=copy.deepcopy(geometria or {})
    hall=list(f.get("hallazgos") or [])

    candidatos=list(g.get("depositos") or []) + list(g.get("equipos") or [])
    for c in candidatos:
        tipo=c.get("tipo")
        # Equipos rotativos ambiguos se asocian primero con OCR de bomba/turbina por proximidad.
        if tipo=="equipo_rotativo":
            posibles=[h for h in hall if h.get("tipo") in {"bomba","turbina"}]
            posibles=[h for h in posibles if math.hypot(float(h.get("x_rel",.5))-float(c.get("x_rel",.5)),float(h.get("y_rel",.5))-float(c.get("y_rel",.5)))<=0.16]
            mismos=posibles
        else:
            mismos=[h for h in hall if h.get("tipo")==tipo]
            # Un círculo legado no debe contradecir una turbina OCR colocada en el mismo sitio.
            if tipo=="bomba" and not mismos:
                turb=[h for h in hall if h.get("tipo")=="turbina" and math.hypot(float(h.get("x_rel",.5))-float(c.get("x_rel",.5)),float(h.get("y_rel",.5))-float(c.get("y_rel",.5)))<=0.14]
                if turb: mismos=turb
        if mismos:
            h0=max(mismos,key=lambda x:float(x.get("confianza",0) or 0))
            h0["x_rel"]=float(c.get("x_rel",h0.get("x_rel",0.5)))
            h0["y_rel"]=float(c.get("y_rel",h0.get("y_rel",0.5)))
            if c.get("fraccion_recorrido") is not None:
                h0["fraccion_recorrido"]=float(c["fraccion_recorrido"])
            det=str(h0.get("detalle","")).strip()
            extra="Posición refinada con geometría V14.14 confirmada."
            h0["detalle"]=(det+" "+extra).strip()
        else:
            hall.append({
                "tipo":tipo,
                "texto":f"{str(tipo).replace('_',' ').title()} inferido por geometría",
                "pagina":int(g.get("pagina",1) or 1),
                "x_rel":float(c.get("x_rel",0.5)),"y_rel":float(c.get("y_rel",0.5)),
                "confianza":min(float(c.get("confianza",60) or 60),79.0),
                "estado":"Confirmar","detalle":str(c.get("detalle","Detección geométrica V14.14; requiere confirmación.")),
                "fraccion_recorrido":c.get("fraccion_recorrido"),"fuente":"geometria_v14_4","fuente_version":"V14.14",
            })

    # Recalcula fracción de recorrido preferentemente con la polilínea V14.14.
    recorrido=g.get("recorrido_polilinea") or {}
    if recorrido.get("vertices_rel"):
        # Proyección en coordenadas normalizadas: usar w=h=1.
        for h0 in hall:
            if h0.get("tipo") not in {"bomba","turbina","equipo_rotativo","valvula","codo"}:
                continue
            frac,_,_=_proyectar_polilinea_v1414(float(h0.get("x_rel",.5)),float(h0.get("y_rel",.5)),recorrido,1.0,1.0)
            if frac is not None:
                h0["fraccion_recorrido"]=_clip01(frac)
    else:
        def mejor(tipo):
            xs=[h for h in hall if h.get("tipo")==tipo]
            return max(xs,key=lambda x:float(x.get("confianza",0) or 0)) if xs else None
        d1,d2=mejor("deposito_1"),mejor("deposito_2")
        if d1 and d2:
            dx=float(d2.get("x_rel",0))-float(d1.get("x_rel",0)); dy=float(d2.get("y_rel",0))-float(d1.get("y_rel",0)); den=dx*dx+dy*dy
            if den>1e-9:
                for h0 in hall:
                    if h0.get("tipo") not in {"bomba","turbina","valvula","codo"}: continue
                    px=float(h0.get("x_rel",0))-float(d1.get("x_rel",0)); py=float(h0.get("y_rel",0))-float(d1.get("y_rel",0))
                    h0["fraccion_recorrido"]=_clip01((px*dx+py*dy)/den)

    f["hallazgos"]=hall
    # Mantiene la clave histórica y agrega la nueva para trazabilidad explícita.
    f["geometria_v14_4"]=g
    f["geometria_v14_14"]=g
    advert=list(f.get("advertencias") or [])
    advert.append("V14.14 refinó recorrido/posiciones con geometría confirmada; no convirtió píxeles a unidades físicas.")
    f["advertencias"]=list(dict.fromkeys(advert))
    return f
