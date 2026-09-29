"""Pruebas V14.3 — interpretación conservadora de figuras hidráulicas."""
from pathlib import Path
from io import BytesIO
import tempfile

from interpretacion_figuras import interpretar_figura_archivo, ErrorInterpretacionFigura

BASE = Path(__file__).resolve().parent
APP = (BASE / "app.py").read_text(encoding="utf-8")


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)


def fuente(size=34):
    from PIL import ImageFont
    candidatos = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "DejaVuSans.ttf",
    ]
    for p in candidatos:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def crear_esquema_png():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (1800, 900), "white")
    d = ImageDraw.Draw(img)
    f = fuente(38)
    fs = fuente(30)

    # Tubería esquemática
    d.line((280, 500, 1500, 500), fill="black", width=8)
    # Depósitos
    d.rectangle((120, 350, 300, 620), outline="black", width=6)
    d.rectangle((1500, 420, 1680, 690), outline="black", width=6)
    # Bomba y válvula: los símbolos son decorativos; V14.3 usa sus etiquetas.
    d.ellipse((720, 445, 830, 555), outline="black", width=5)
    d.polygon([(1090, 470), (1140, 500), (1090, 530)], outline="black")
    d.polygon([(1190, 470), (1140, 500), (1190, 530)], outline="black")

    d.text((95, 255), "Deposito 1", fill="black", font=f)
    d.text((90, 300), "P1 = 85 kPa", fill="black", font=fs)
    d.text((90, 650), "z1 = 18 m", fill="black", font=fs)

    d.text((680, 365), "Bomba", fill="black", font=f)
    d.text((1040, 365), "Valvula", fill="black", font=f)

    d.text((1430, 300), "Deposito 2", fill="black", font=f)
    d.text((1430, 345), "P2 = 0 kPa", fill="black", font=fs)
    d.text((1430, 720), "z2 = 5 m", fill="black", font=fs)

    d.text((650, 600), "D = 0.1023 m", fill="black", font=fs)
    d.text((650, 650), "L = 120 m", fill="black", font=fs)

    bio = BytesIO()
    img.save(bio, format="PNG")
    return bio.getvalue()


print("[1/8] PNG esquemático: detecta depósitos y equipos...")
datos = crear_esquema_png()
r = interpretar_figura_archivo("esquema.png", datos)
tipos = [h["tipo"] for h in r.hallazgos]
ok("deposito_1" in tipos, f"No detectó depósito 1: {tipos}")
ok("deposito_2" in tipos, f"No detectó depósito 2: {tipos}")
ok("bomba" in tipos, f"No detectó bomba: {tipos}")
ok("valvula" in tipos, f"No detectó válvula: {tipos}")
print("  OK")

print("[2/8] Variables de la figura se conservan como evidencia...")
for requerido in ("P1", "P2", "z1", "z2", "diametro", "longitud"):
    ok(requerido in tipos, f"Falta hallazgo {requerido}: {tipos}")
print("  OK")

print("[3/8] Orientación depósito 1 -> depósito 2...")
ok(r.orientacion == "izquierda → derecha", f"Orientación inesperada: {r.orientacion}")
print("  OK")

print("[4/8] Posiciones relativas de bomba/válvula son razonables...")
bomba = next(h for h in r.hallazgos if h["tipo"] == "bomba")
valvula = next(h for h in r.hallazgos if h["tipo"] == "valvula")
ok(bomba["fraccion_recorrido"] is not None, "Bomba sin posición relativa")
ok(valvula["fraccion_recorrido"] is not None, "Válvula sin posición relativa")
ok(0.25 < bomba["fraccion_recorrido"] < 0.60, f"Posición bomba extraña: {bomba}")
ok(0.55 < valvula["fraccion_recorrido"] < 0.90, f"Posición válvula extraña: {valvula}")
print("  OK")

print("[5/8] No inventa escala física a partir de píxeles...")
t = r.texto_sugerido.lower()
ok("pixel" not in t or "metros" not in t, "No debe convertir píxeles a metros")
ok("aproximadamente" in t, "Las posiciones deben marcarse como aproximadas")
print("  OK")

print("[6/8] PDF escaneado con esquema usa la misma interpretación...")
from PIL import Image
pdf_bio = BytesIO()
Image.open(BytesIO(datos)).convert("RGB").save(pdf_bio, format="PDF", resolution=200.0)
r_pdf = interpretar_figura_archivo("esquema.pdf", pdf_bio.getvalue(), pagina_pdf=1)
tipos_pdf = [h["tipo"] for h in r_pdf.hallazgos]
ok("deposito_1" in tipos_pdf and "deposito_2" in tipos_pdf, f"PDF no conservó depósitos: {tipos_pdf}")
ok("bomba" in tipos_pdf and "valvula" in tipos_pdf, f"PDF no conservó equipos: {tipos_pdf}")
print("  OK")

print("[7/8] Formato no visual se rechaza en interpretación de figura...")
try:
    interpretar_figura_archivo("problema.txt", b"Deposito 1 -> Deposito 2")
except ErrorInterpretacionFigura:
    pass
else:
    raise AssertionError("V14.3 no debe tratar TXT como figura")
print("  OK")

print("[8/8] Integración V14.3 en app.py...")
for token in (
    "interpretar_figura_archivo",
    "V14.3 — Interpretar figura / esquema hidráulico",
    "ANALIZAR FIGURA / ESQUEMA",
    "AGREGAR INTERPRETACIÓN DE FIGURA AL ENUNCIADO",
    "resultado_figura_v143",
):
    ok(token in APP, f"Falta integración V14.3 en app.py: {token}")
print("  OK")

print("\nTODAS LAS PRUEBAS V14.3 DE INTERPRETACIÓN DE FIGURAS PASARON.")
