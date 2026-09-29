"""Pruebas V14.3.2 — fusión estructurada de figura confirmada."""
from pathlib import Path
from io import BytesIO

from interpretacion_figuras import interpretar_figura_archivo, fusionar_resultado_con_figura

BASE = Path(__file__).resolve().parent
APP = (BASE / "app.py").read_text(encoding="utf-8")


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)


def fuente(size=34):
    from PIL import ImageFont
    candidatos = [
        r"C:\\Windows\\Fonts\\arial.ttf",
        r"C:\\Windows\\Fonts\\calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "DejaVuSans.ttf",
    ]
    for p in candidatos:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def crear_esquema():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (1900, 1050), "white")
    d = ImageDraw.Draw(img)
    f = fuente(38)
    fs = fuente(30)

    d.line((260, 520, 1600, 520), fill="black", width=8)
    d.rectangle((90, 360, 280, 650), outline="black", width=6)
    d.rectangle((1600, 420, 1780, 710), outline="black", width=6)
    d.ellipse((700, 465, 810, 575), outline="black", width=5)
    d.polygon([(1120, 485), (1170, 520), (1120, 555)], outline="black")
    d.polygon([(1220, 485), (1170, 520), (1220, 555)], outline="black")

    d.text((70, 235), "Deposito 1", fill="black", font=f)
    d.text((65, 285), "P1 = 85 kPa", fill="black", font=fs)
    d.text((65, 720), "z1 = 18 m", fill="black", font=fs)

    d.text((665, 385), "Bomba", fill="black", font=f)
    d.text((660, 600), "hA = 8 m", fill="black", font=fs)
    d.text((1080, 385), "Valvula de compuerta", fill="black", font=f)

    d.text((1535, 275), "Deposito 2", fill="black", font=f)
    d.text((1535, 325), "P2 = 0 kPa", fill="black", font=fs)
    d.text((1535, 760), "z2 = 5 m", fill="black", font=fs)

    d.text((650, 680), "L = 120 m", fill="black", font=fs)
    d.text((650, 735), "D = 0.1023 m", fill="black", font=fs)

    bio = BytesIO()
    img.save(bio, format="PNG")
    return bio.getvalue()


def resultado_base():
    return {
        "clase": "Clase II-C",
        "confianza": 72,
        "advertencias": [],
        "datos": [],
        "prefill": {
            "P1_kpa": None,
            "P2_kpa": 0.0,
            "z1_m": None,
            "z2_m": 5.0,
            "hA_m": 8.0,
            "hR_m": None,
            "v1_tipo": None,
            "v2_tipo": None,
            "tramos": [
                {
                    "numero": 1,
                    "L_m": 120.0,
                    "D_m": 0.1023,
                    "material": "Acero comercial o soldado",
                    "accesorios": [
                        {"nombre": "Válvula de compuerta — totalmente abierta", "cantidad": 1},
                        {"nombre": "Entrada — borde cuadrado/agudo", "cantidad": 1},
                        {"nombre": "Salida hacia depósito grande", "cantidad": 1},
                    ],
                    "curvas": [],
                    "K_extra": None,
                    "componentes_graficos": [],
                }
            ],
        },
    }


print("[1/7] Figura recupera P1, z1 y hA...")
r = interpretar_figura_archivo("esquema.png", crear_esquema())
tipos = [h["tipo"] for h in r.hallazgos]
ok("P1" in tipos and "z1" in tipos and "hA" in tipos, f"Hallazgos insuficientes: {tipos}")
print("  OK")

print("[2/7] Fusión completa solo datos faltantes...")
f = fusionar_resultado_con_figura(resultado_base(), r.como_dict())
p = f["prefill"]
ok(abs(p["P1_kpa"] - 85.0) < 1e-9, p)
ok(abs(p["z1_m"] - 18.0) < 1e-9, p)
ok(abs(p["hA_m"] - 8.0) < 1e-9, p)
ok(p["v1_tipo"] == "deposito" and p["v2_tipo"] == "deposito", p)
print("  OK")

print("[3/7] No duplica tramos al repetir L/D en la figura...")
ok(len(p["tramos"]) == 1, f"Se duplicaron tramos: {p['tramos']}")
ok(abs(p["tramos"][0]["L_m"] - 120.0) < 1e-9, p["tramos"])
ok(abs(p["tramos"][0]["D_m"] - 0.1023) < 1e-9, p["tramos"])
print("  OK")

print("[4/7] Entrada=0 %, salida=100 %, válvula conserva posición visual...")
acc = {a["nombre"]: a for a in p["tramos"][0]["accesorios"]}
ok(acc["Entrada — borde cuadrado/agudo"]["posicion_fraccion"] == 0.0, acc)
ok(acc["Salida hacia depósito grande"]["posicion_fraccion"] == 1.0, acc)
fv = acc["Válvula de compuerta — totalmente abierta"].get("posicion_fraccion")
ok(fv is not None and 0.5 < fv < 0.9, f"Posición de válvula inesperada: {fv}")
print("  OK")

print("[5/7] Bomba usa posición gráfica aproximada, no el 5 % por defecto...")
xb = p.get("posicion_bomba_m")
ok(xb is not None and 25.0 < xb < 80.0, f"Posición bomba inesperada: {xb}")
ok(p.get("posicion_bomba_aproximada_figura") is True, p)
print("  OK")

print("[6/7] Un conflicto textual explícito no se sobrescribe silenciosamente...")
base_conf = resultado_base()
base_conf["prefill"]["P1_kpa"] = 90.0
fc = fusionar_resultado_con_figura(base_conf, r.como_dict())
ok(abs(fc["prefill"]["P1_kpa"] - 90.0) < 1e-9, fc["prefill"])
ok(any("difieren para P1" in a for a in fc.get("advertencias", [])), fc.get("advertencias"))
print("  OK")

print("[7/7] Integración V14.3.2 en app.py...")
for token in (
    "fusionar_resultado_con_figura",
    "figura_confirmada_v143",
    "AGREGAR INTERPRETACIÓN DE FIGURA AL ENUNCIADO",
    "completará datos faltantes y posiciones gráficas sin duplicar tramos",
    "OCR automáticamente",
):
    ok(token in APP, f"Falta integración V14.3.2 en app.py: {token}")
print("  OK")

print("\nTODAS LAS PRUEBAS V14.3.2 PASARON.")
