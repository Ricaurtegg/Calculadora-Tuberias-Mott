import math

# ============================================================
# TUBERÍA COMERCIAL — MOTT 7a ED., APÉNDICE F
# Dimensiones de tubería de acero Schedule 40 y Schedule 80.
# Valores en SI. El diámetro que se usa hidráulicamente es el
# diámetro interior real, no el NPS/DN nominal.
# ============================================================


def _fila(nps, dn, od_mm, wall_mm, id_mm):
    return {
        "nps": str(nps),
        "dn": int(dn),
        "od_m": float(od_mm) / 1000.0,
        "wall_m": float(wall_mm) / 1000.0,
        "id_m": float(id_mm) / 1000.0,
        "area_m2": math.pi * (float(id_mm) / 1000.0) ** 2 / 4.0,
    }


TUBERIA_ACERO_SCH40 = [
    _fila("1/8", 6, 10.3, 1.73, 6.8),
    _fila("1/4", 8, 13.7, 2.24, 9.2),
    _fila("3/8", 10, 17.1, 2.31, 12.5),
    _fila("1/2", 15, 21.3, 2.77, 15.8),
    _fila("3/4", 20, 26.7, 2.87, 20.9),
    _fila("1", 25, 33.4, 3.38, 26.6),
    _fila("1 1/4", 32, 42.2, 3.56, 35.1),
    _fila("1 1/2", 40, 48.3, 3.68, 40.9),
    _fila("2", 50, 60.3, 3.91, 52.5),
    _fila("2 1/2", 65, 73.0, 5.16, 62.7),
    _fila("3", 80, 88.9, 5.49, 77.9),
    _fila("3 1/2", 90, 101.6, 5.74, 90.1),
    _fila("4", 100, 114.3, 6.02, 102.3),
    _fila("5", 125, 141.3, 6.55, 128.2),
    _fila("6", 150, 168.3, 7.11, 154.1),
    _fila("8", 200, 219.1, 8.18, 202.7),
    _fila("10", 250, 273.1, 9.27, 254.5),
    _fila("12", 300, 323.9, 10.31, 303.2),
    _fila("14", 350, 355.6, 11.10, 333.4),
    _fila("16", 400, 406.4, 12.70, 381.0),
    _fila("18", 450, 457.2, 14.27, 428.7),
    _fila("20", 500, 508.0, 15.06, 477.9),
    _fila("24", 600, 609.6, 17.45, 574.7),
]

TUBERIA_ACERO_SCH80 = [
    _fila("1/8", 6, 10.3, 2.41, 5.5),
    _fila("1/4", 8, 13.7, 3.02, 7.7),
    _fila("3/8", 10, 17.1, 3.20, 10.7),
    _fila("1/2", 15, 21.3, 3.73, 13.9),
    _fila("3/4", 20, 26.7, 3.91, 18.8),
    _fila("1", 25, 33.4, 4.55, 24.3),
    _fila("1 1/4", 32, 42.2, 4.85, 32.5),
    _fila("1 1/2", 40, 48.3, 5.08, 38.1),
    _fila("2", 50, 60.3, 5.54, 49.3),
    _fila("2 1/2", 65, 73.0, 7.01, 59.0),
    _fila("3", 80, 88.9, 7.62, 73.7),
    _fila("3 1/2", 90, 101.6, 8.08, 85.4),
    _fila("4", 100, 114.3, 8.56, 97.2),
    _fila("5", 125, 141.3, 9.53, 122.3),
    _fila("6", 150, 168.3, 10.97, 146.3),
    _fila("8", 200, 219.1, 12.70, 193.7),
    _fila("10", 250, 273.1, 15.06, 242.9),
    _fila("12", 300, 323.9, 17.45, 289.0),
    _fila("14", 350, 355.6, 19.05, 317.5),
    _fila("16", 400, 406.4, 21.39, 363.6),
    _fila("18", 450, 457.2, 23.80, 409.6),
    _fila("20", 500, 508.0, 26.19, 455.6),
    _fila("24", 600, 609.6, 30.94, 547.7),
]

CATALOGOS_TUBERIA = {
    "Acero Schedule 40 — Mott Apéndice F": TUBERIA_ACERO_SCH40,
    "Acero Schedule 80 — Mott Apéndice F": TUBERIA_ACERO_SCH80,
}


def obtener_catalogo(nombre):
    if nombre not in CATALOGOS_TUBERIA:
        raise KeyError(f"Catálogo comercial no reconocido: {nombre}")
    return CATALOGOS_TUBERIA[nombre]


def seleccionar_tamano_comercial(d_min_m, catalogo_nombre):
    """
    Selecciona el primer diámetro interior real >= D mínimo teórico.
    Este es el paso recomendado por Mott para pasar de III-A a III-B.
    """
    d_min_m = float(d_min_m)
    if d_min_m <= 0:
        raise ValueError("D mínimo debe ser mayor que cero.")

    tabla = obtener_catalogo(catalogo_nombre)
    previo = None
    for fila in tabla:
        if fila["id_m"] + 1e-15 >= d_min_m:
            return {
                **fila,
                "catalogo": catalogo_nombre,
                "d_min_m": d_min_m,
                "margen_diametro_m": fila["id_m"] - d_min_m,
                "margen_diametro_pct": (fila["id_m"] - d_min_m) / d_min_m * 100.0,
                "tamano_anterior": previo,
                "cumple_d_min": True,
            }
        previo = dict(fila)

    raise ValueError(
        f"D mínimo = {d_min_m*1000:.2f} mm supera el mayor tamaño incluido "
        f"en {catalogo_nombre}."
    )


def buscar_tamano_por_nps(catalogo_nombre, nps):
    nps = str(nps).strip()
    for fila in obtener_catalogo(catalogo_nombre):
        if fila["nps"] == nps:
            return dict(fila)
    raise KeyError(f"NPS {nps} no encontrado en {catalogo_nombre}.")


def opciones_nps(catalogo_nombre):
    return [fila["nps"] for fila in obtener_catalogo(catalogo_nombre)]
