from pathlib import Path
import tempfile

from vision_esquemas import (
    analizar_geometria_archivo,
    fusionar_figura_con_geometria,
    ErrorVisionEsquema,
    _normalizar_lineas_hough,
)

BASE = Path(__file__).resolve().parent
APP = (BASE / "app.py").read_text(encoding="utf-8")


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)


def crear_esquema_sin_etiquetas(path: Path):
    import cv2
    import numpy as np
    w, h = 1400, 700
    img = np.full((h, w, 3), 255, np.uint8)
    cv2.rectangle(img, (80, 190), (250, 510), (0, 0, 0), 5)
    cv2.rectangle(img, (1150, 210), (1320, 490), (0, 0, 0), 5)
    cv2.line(img, (250, 350), (1150, 350), (0, 0, 0), 6)
    cv2.circle(img, (570, 350), 48, (0, 0, 0), 5)
    # válvula tipo bow-tie/X
    cv2.line(img, (820, 315), (870, 350), (0, 0, 0), 4)
    cv2.line(img, (820, 385), (870, 350), (0, 0, 0), 4)
    cv2.line(img, (920, 315), (870, 350), (0, 0, 0), 4)
    cv2.line(img, (920, 385), (870, 350), (0, 0, 0), 4)
    cv2.imwrite(str(path), img)


print("[compat] HoughLinesP acepta salida (N,1,4) y (N,4)...")
import numpy as np
_h3 = np.array([[[1, 2, 3, 4]], [[5, 6, 7, 8]]], dtype=np.int32)
_h2 = np.array([[1, 2, 3, 4], [5, 6, 7, 8]], dtype=np.int32)
ok(_normalizar_lineas_hough(_h3).shape == (2, 4), "No normalizó HoughLinesP (N,1,4)")
ok(_normalizar_lineas_hough(_h2).shape == (2, 4), "No normalizó HoughLinesP (N,4)")
print("  OK")

print("[1/8] OpenCV detecta el trazado principal sin depender de texto...")
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "esquema.png"
    crear_esquema_sin_etiquetas(p)
    r = analizar_geometria_archivo(p.name, p.read_bytes()).como_dict()
    ok(r.get("tuberia_principal") is not None, "No detectó la tubería principal")
    ok(abs(float(r["tuberia_principal"]["angulo_deg"])) < 3.0, "La tubería horizontal quedó mal orientada")
    print("  OK")

    print("[2/8] Detecta dos depósitos geométricos...")
    deps = r.get("depositos", [])
    ok(len(deps) == 2, f"Se esperaban 2 depósitos; obtuvo {len(deps)}")
    ok(deps[0]["tipo"] == "deposito_1" and deps[1]["tipo"] == "deposito_2", "No ordenó los depósitos correctamente")
    print("  OK")

    print("[3/8] Detecta bomba circular sin etiqueta OCR...")
    bombas = [e for e in r.get("equipos", []) if e.get("tipo") == "bomba"]
    ok(bombas, "No detectó la bomba geométrica")
    ok(0.25 < float(bombas[0]["fraccion_recorrido"]) < 0.50, "Posición de bomba no razonable")
    print("  OK")

    print("[4/8] Detecta válvula tipo bow-tie/X sin etiqueta OCR...")
    valv = [e for e in r.get("equipos", []) if e.get("tipo") == "valvula"]
    ok(valv, "No detectó la válvula geométrica")
    ok(0.55 < float(valv[0]["fraccion_recorrido"]) < 0.80, "Posición de válvula no razonable")
    print("  OK")

    print("[5/8] Orden espacial depósito 1 -> bomba -> válvula -> depósito 2...")
    orden = r.get("orden", [])
    ok(orden[:4] == ["deposito_1", "bomba", "valvula", "deposito_2"], f"Orden inesperado: {orden}")
    print("  OK")

    print("[6/8] La visión no inventa unidades físicas...")
    texto = repr(r)
    ok("longitud_m" not in texto and "diametro_m" not in texto and "hA_m" not in texto, "La geometría inventó datos físicos")
    ok(r.get("cambios_seccion", []) == [], "Un esquema uniforme generó falso cambio de sección")
    print("  OK")

    print("[7/8] Fusión con V14.3 agrega símbolos como Confirmar, no como Alta...")
    figura = {
        "pagina": 1,
        "hallazgos": [],
        "advertencias": [],
        "orientacion": None,
        "confianza_global": 0.0,
    }
    f = fusionar_figura_con_geometria(figura, r)
    tipos = [h.get("tipo") for h in f.get("hallazgos", [])]
    ok("bomba" in tipos and "valvula" in tipos, "La fusión no agregó bomba/válvula")
    inferred = [h for h in f["hallazgos"] if h.get("fuente") == "geometria_v14_4"]
    ok(inferred and all(h.get("estado") == "Confirmar" for h in inferred), "Símbolos geométricos sin OCR deben quedar en Confirmar")
    print("  OK")

print("[8/8] Integración V14.4 en app.py...")
for token in (
    "analizar_geometria_archivo",
    "fusionar_figura_con_geometria",
    "V14.4 — Reconocimiento geométrico del esquema",
    "USAR GEOMETRÍA PARA REFINAR V14.3",
):
    ok(token in APP, f"Falta integración V14.4 en app.py: {token}")
print("  OK")

print("\nTODAS LAS PRUEBAS V14.4 DE VISIÓN GEOMÉTRICA PASARON.")
