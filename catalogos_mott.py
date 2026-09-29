import math
import re

# ============================================================
# CATÁLOGOS HIDRÁULICOS
# Basados en Applied Fluid Mechanics, Mott & Untener, 7th ed.
# - Appendix A: water properties
# - Appendix B: common liquids at 25 °C
# - Appendix C: typical petroleum lubricating oils
# - Chapter 8, Table 8.2: pipe roughness
# - Chapter 10, Tables 10.4 and 10.5: valves/fittings
# ============================================================


# ============================================================
# RUGOSIDAD DE TUBERÍAS — MOTT 7a ED., TABLA 8.2
# Valores de diseño de rugosidad absoluta ε en SI [m].
# ============================================================

MATERIALES = {
    "Vidrio — liso": 0.0,
    "Plástico": 3.0e-7,
    "Tubería estirada — cobre, latón o acero": 1.5e-6,
    "Acero comercial o soldado": 4.6e-5,
    "Hierro galvanizado": 1.5e-4,
    "Hierro dúctil recubierto": 1.2e-4,
    "Hierro dúctil sin recubrir": 2.4e-4,
    "Concreto bien hecho": 1.2e-4,
    "Acero remachado": 1.8e-3,
    "Personalizada": None,
}

MATERIALES_INFO = {
    "Vidrio — liso": {"epsilon_m": 0.0, "fuente": "Mott 7e — Tabla 8.2", "descripcion": "Vidrio; Mott lo clasifica como liso."},
    "Plástico": {"epsilon_m": 3.0e-7, "fuente": "Mott 7e — Tabla 8.2", "descripcion": "Plástico."},
    "Tubería estirada — cobre, latón o acero": {"epsilon_m": 1.5e-6, "fuente": "Mott 7e — Tabla 8.2", "descripcion": "Tubería estirada; cobre, latón o acero."},
    "Acero comercial o soldado": {"epsilon_m": 4.6e-5, "fuente": "Mott 7e — Tabla 8.2", "descripcion": "Acero comercial o soldado."},
    "Hierro galvanizado": {"epsilon_m": 1.5e-4, "fuente": "Mott 7e — Tabla 8.2", "descripcion": "Hierro galvanizado."},
    "Hierro dúctil recubierto": {"epsilon_m": 1.2e-4, "fuente": "Mott 7e — Tabla 8.2", "descripcion": "Hierro dúctil recubierto."},
    "Hierro dúctil sin recubrir": {"epsilon_m": 2.4e-4, "fuente": "Mott 7e — Tabla 8.2", "descripcion": "Hierro dúctil sin recubrimiento."},
    "Concreto bien hecho": {"epsilon_m": 1.2e-4, "fuente": "Mott 7e — Tabla 8.2", "descripcion": "Concreto bien hecho."},
    "Acero remachado": {"epsilon_m": 1.8e-3, "fuente": "Mott 7e — Tabla 8.2", "descripcion": "Acero remachado."},
    "Personalizada": {"epsilon_m": None, "fuente": "Usuario", "descripcion": "Rugosidad introducida manualmente."},
}

ALIASES_MATERIALES = {
    "Acero comercial": "Acero comercial o soldado",
    "Acero soldado": "Acero comercial o soldado",
    "Acero estirado / tubería lisa": "Tubería estirada — cobre, latón o acero",
    "Cobre / latón": "Tubería estirada — cobre, latón o acero",
    "PVC / plástico liso": "Plástico",
    "Concreto liso": "Concreto bien hecho",
}

# ============================================================
# AGUA — APÉNDICE A, SI, 101 kPa(abs)
# T [°C], gamma [kN/m³], rho [kg/m³], mu [Pa·s], nu [m²/s]
# ============================================================

AGUA_MOTT = {
    0:   {"gamma_kN_m3": 9.81, "rho": 1000.0, "mu": 1.75e-3, "nu": 1.75e-6},
    5:   {"gamma_kN_m3": 9.81, "rho": 1000.0, "mu": 1.52e-3, "nu": 1.52e-6},
    10:  {"gamma_kN_m3": 9.81, "rho": 1000.0, "mu": 1.30e-3, "nu": 1.30e-6},
    15:  {"gamma_kN_m3": 9.81, "rho": 1000.0, "mu": 1.15e-3, "nu": 1.15e-6},
    20:  {"gamma_kN_m3": 9.79, "rho": 998.0,  "mu": 1.02e-3, "nu": 1.02e-6},
    25:  {"gamma_kN_m3": 9.78, "rho": 997.0,  "mu": 8.91e-4, "nu": 8.94e-7},
    30:  {"gamma_kN_m3": 9.77, "rho": 996.0,  "mu": 8.00e-4, "nu": 8.03e-7},
    35:  {"gamma_kN_m3": 9.75, "rho": 994.0,  "mu": 7.18e-4, "nu": 7.22e-7},
    40:  {"gamma_kN_m3": 9.73, "rho": 992.0,  "mu": 6.51e-4, "nu": 6.56e-7},
    45:  {"gamma_kN_m3": 9.71, "rho": 990.0,  "mu": 5.94e-4, "nu": 6.00e-7},
    50:  {"gamma_kN_m3": 9.69, "rho": 988.0,  "mu": 5.41e-4, "nu": 5.48e-7},
    55:  {"gamma_kN_m3": 9.67, "rho": 986.0,  "mu": 4.98e-4, "nu": 5.05e-7},
    60:  {"gamma_kN_m3": 9.65, "rho": 984.0,  "mu": 4.60e-4, "nu": 4.67e-7},
    65:  {"gamma_kN_m3": 9.62, "rho": 981.0,  "mu": 4.31e-4, "nu": 4.39e-7},
    70:  {"gamma_kN_m3": 9.59, "rho": 978.0,  "mu": 4.02e-4, "nu": 4.11e-7},
    75:  {"gamma_kN_m3": 9.56, "rho": 975.0,  "mu": 3.73e-4, "nu": 3.83e-7},
    80:  {"gamma_kN_m3": 9.53, "rho": 971.0,  "mu": 3.50e-4, "nu": 3.60e-7},
    85:  {"gamma_kN_m3": 9.50, "rho": 968.0,  "mu": 3.30e-4, "nu": 3.41e-7},
    90:  {"gamma_kN_m3": 9.47, "rho": 965.0,  "mu": 3.11e-4, "nu": 3.22e-7},
    95:  {"gamma_kN_m3": 9.44, "rho": 962.0,  "mu": 2.92e-4, "nu": 3.04e-7},
    100: {"gamma_kN_m3": 9.40, "rho": 958.0,  "mu": 2.82e-4, "nu": 2.94e-7},
}


# ============================================================
# LÍQUIDOS COMUNES — APÉNDICE B, SI, 101 kPa(abs), 25 °C
# mu es viscosidad dinámica. nu se calcula como mu/rho.
# ============================================================

_LIQUIDOS_MOTT_BASE = {
    "Acetona — 25 °C":                    {"sg": 0.787, "rho": 787.0,   "mu": 3.16e-4},
    "Alcohol etílico (etanol) — 25 °C":  {"sg": 0.787, "rho": 787.0,   "mu": 1.00e-3},
    "Alcohol metílico (metanol) — 25 °C": {"sg": 0.789, "rho": 789.0,  "mu": 5.60e-4},
    "Alcohol propílico — 25 °C":          {"sg": 0.802, "rho": 802.0,   "mu": 1.92e-3},
    # Mott 7e lists aqueous ammonia (25%) without viscosity in this table.
    "Amoniaco acuoso 25% — 25 °C":        {"sg": 0.910, "rho": 910.0,   "mu": None},
    "Benceno — 25 °C":                    {"sg": 0.876, "rho": 876.0,   "mu": 6.03e-4},
    "Tetracloruro de carbono — 25 °C":    {"sg": 1.590, "rho": 1590.0,  "mu": 9.10e-4},
    "Aceite de ricino — 25 °C":           {"sg": 0.960, "rho": 960.0,   "mu": 6.51e-1},
    "Etilenglicol — 25 °C":               {"sg": 1.100, "rho": 1100.0,  "mu": 1.62e-2},
    "Gasolina — 25 °C":                   {"sg": 0.680, "rho": 680.0,   "mu": 2.87e-4},
    "Glicerina — 25 °C":                  {"sg": 1.258, "rho": 1258.0,  "mu": 9.60e-1},
    "Queroseno — 25 °C":                  {"sg": 0.823, "rho": 823.0,   "mu": 1.64e-3},
    "Aceite de linaza — 25 °C":           {"sg": 0.930, "rho": 930.0,   "mu": 3.31e-2},
    "Mercurio — 25 °C":                   {"sg": 13.54, "rho": 13540.0, "mu": 1.53e-3},
    "Propano líquido — 25 °C":            {"sg": 0.495, "rho": 495.0,   "mu": 1.10e-4},
    "Agua de mar — 25 °C":                {"sg": 1.030, "rho": 1030.0,  "mu": 1.03e-3},
    "Trementina — 25 °C":                 {"sg": 0.870, "rho": 870.0,   "mu": 1.37e-3},
    "Aceite de petróleo medio — 25 °C":   {"sg": 0.852, "rho": 852.0,   "mu": 2.99e-3},
    "Aceite de petróleo pesado — 25 °C":  {"sg": 0.906, "rho": 906.0,   "mu": 1.07e-1},
}


LIQUIDOS_MOTT = {}
for nombre, datos in _LIQUIDOS_MOTT_BASE.items():
    copia = dict(datos)
    copia["nu"] = None if copia["mu"] is None else copia["mu"] / copia["rho"]
    copia["tipo"] = "liquido_mott_25c"
    copia["temperatura_c"] = 25.0
    copia["fuente"] = "Mott 7e — Apéndice B"
    LIQUIDOS_MOTT[nombre] = copia


# ============================================================
# DATOS NATURALES/BIOLÓGICOS — APÉNDICE B (APROXIMADOS)
# Mott advierte que pueden variar significativamente con la composición.
# Se incluyen para que el catálogo refleje lo mostrado en la bibliografía,
# pero la app debe advertir que el motor Darcy/Colebrook supone fluido
# newtoniano con viscosidad representativa constante.
# ============================================================

_NATURALES_BIO_MOTT_BASE = {
    "Aceite de oliva — 20 °C [aprox.]": {"sg": 0.92, "rho": 920.0, "mu": 8.5e-2, "nu": 9.24e-5, "temperatura_c": 20.0},
    "Miel — 21 °C [aprox.]": {"sg": 1.42, "rho": 1420.0, "mu": 10.0, "nu": 7.04e-3, "temperatura_c": 21.0},
    "Ketchup — 21 °C [aprox.]": {"sg": 1.48, "rho": 1480.0, "mu": 50.0, "nu": 3.38e-2, "temperatura_c": 21.0},
    "Mantequilla de maní — 21 °C [aprox.]": {"sg": 1.30, "rho": 1300.0, "mu": 250.0, "nu": 1.92e-1, "temperatura_c": 21.0},
    "Sangre — 10 °C [aprox.]": {"sg": 1.06, "rho": 1060.0, "mu": 1.00e-2, "nu": 9.43e-6, "temperatura_c": 10.0},
    "Sangre — 37 °C [aprox.]": {"sg": 1.06, "rho": 1060.0, "mu": 3.50e-3, "nu": 3.30e-6, "temperatura_c": 37.0},
}

NATURALES_BIO_MOTT = {}
for nombre, datos in _NATURALES_BIO_MOTT_BASE.items():
    NATURALES_BIO_MOTT[nombre] = {
        **datos,
        "tipo": "liquido_mott_aprox_composicion",
        "fuente": "Mott 7e — Apéndice B (datos aproximados)",
        "advertencia": (
            "Mott indica que estos datos varían significativamente con la composición. "
            "Además, algunos de estos materiales pueden presentar comportamiento no newtoniano. "
            "Use el cálculo de tuberías solo cuando el enunciado autorice tratar la viscosidad tabulada como representativa."
        ),
    }


# ============================================================
# ACEITES LUBRICANTES DE PETRÓLEO — APÉNDICE C
# Valores aproximados que Mott proporciona para resolución de problemas.
# rho se obtiene de sg×1000 kg/m³ y mu = rho×nu.
# ============================================================

_ACEITES_C_MOTT_BASE = {
    # Sistema hidráulico automotriz
    "Aceite hidráulico automotriz — 40 °C": {"sg": 0.887, "nu": 3.99e-5, "temperatura_c": 40.0},
    "Aceite hidráulico automotriz — 100 °C": {"sg": 0.887, "nu": 7.29e-6, "temperatura_c": 100.0},

    # Aceites de motor: la tabla especifica viscosidad cinemática a 100 °C
    "Aceite de motor — grado de viscosidad 20 — 100 °C": {"sg": 0.880, "nu": 5.60e-6, "temperatura_c": 100.0},
    "Aceite de motor — grado de viscosidad 40 — 100 °C": {"sg": 0.882, "nu": 1.25e-5, "temperatura_c": 100.0},
    "Aceite de motor — grado de viscosidad 60 — 100 °C": {"sg": 0.883, "nu": 2.19e-5, "temperatura_c": 100.0},

    # Lubricantes de engranajes: tabla a 100 °C
    "Lubricante de engranajes — grado de viscosidad 80 — 100 °C": {"sg": 0.890, "nu": 7.00e-6, "temperatura_c": 100.0},
    "Lubricante de engranajes — grado de viscosidad 140 — 100 °C": {"sg": 0.892, "nu": 2.40e-5, "temperatura_c": 100.0},

    # Sistemas hidráulicos de máquinas-herramienta
    "Aceite hidráulico de máquina-herramienta — ligero — 40 °C": {"sg": 0.887, "nu": 3.20e-5, "temperatura_c": 40.0},
    "Aceite hidráulico de máquina-herramienta — ligero — 100 °C": {"sg": 0.887, "nu": 4.79e-6, "temperatura_c": 100.0},
    "Aceite hidráulico de máquina-herramienta — medio — 40 °C": {"sg": 0.895, "nu": 6.70e-5, "temperatura_c": 40.0},
    "Aceite hidráulico de máquina-herramienta — medio — 100 °C": {"sg": 0.895, "nu": 7.29e-6, "temperatura_c": 100.0},
    "Aceite hidráulico de máquina-herramienta — pesado — 40 °C": {"sg": 0.901, "nu": 1.96e-4, "temperatura_c": 40.0},
    "Aceite hidráulico de máquina-herramienta — pesado — 100 °C": {"sg": 0.901, "nu": 1.40e-5, "temperatura_c": 100.0},
    "Aceite hidráulico de máquina-herramienta — baja temperatura — 40 °C": {"sg": 0.844, "nu": 1.40e-5, "temperatura_c": 40.0},
    "Aceite hidráulico de máquina-herramienta — baja temperatura — 100 °C": {"sg": 0.844, "nu": 5.20e-6, "temperatura_c": 100.0},

    # Aceites lubricantes de máquinas-herramienta
    "Aceite lubricante de máquina-herramienta — ligero — 40 °C": {"sg": 0.881, "nu": 2.20e-5, "temperatura_c": 40.0},
    "Aceite lubricante de máquina-herramienta — ligero — 100 °C": {"sg": 0.881, "nu": 3.90e-6, "temperatura_c": 100.0},
    "Aceite lubricante de máquina-herramienta — medio — 40 °C": {"sg": 0.915, "nu": 6.60e-5, "temperatura_c": 40.0},
    "Aceite lubricante de máquina-herramienta — medio — 100 °C": {"sg": 0.915, "nu": 7.00e-6, "temperatura_c": 100.0},
    "Aceite lubricante de máquina-herramienta — pesado — 40 °C": {"sg": 0.890, "nu": 2.00e-4, "temperatura_c": 40.0},
    "Aceite lubricante de máquina-herramienta — pesado — 100 °C": {"sg": 0.890, "nu": 1.55e-5, "temperatura_c": 100.0},
}

ACEITES_MOTT = {}
for nombre, datos in _ACEITES_C_MOTT_BASE.items():
    rho = float(datos["sg"]) * 1000.0
    nu = float(datos["nu"])
    ACEITES_MOTT[nombre] = {
        **datos,
        "rho": rho,
        "mu": rho * nu,
        "tipo": "aceite_mott_apendice_c",
        "fuente": "Mott 7e — Apéndice C",
        "advertencia": "Mott indica que los valores del Apéndice C son aproximados para resolver problemas del libro.",
    }


# ============================================================
# CATÁLOGO UNIFICADO DE FLUIDOS PARA LA APP
# ============================================================

FLUIDOS = {}

for T, datos in AGUA_MOTT.items():
    nombre = f"Agua a {T} °C"
    FLUIDOS[nombre] = {
        **datos,
        "tipo": "agua_tabla",
        "temperatura_c": float(T),
        "fuente": "Mott 7e — Apéndice A",
    }

FLUIDOS["Agua — interpolar temperatura"] = {
    "tipo": "agua_interpolar",
    "fuente": "Mott 7e — Apéndice A (interpolación lineal)",
}

FLUIDOS.update(LIQUIDOS_MOTT)
FLUIDOS.update(ACEITES_MOTT)
FLUIDOS.update(NATURALES_BIO_MOTT)

FLUIDOS["Personalizado"] = {
    "tipo": "personalizado",
    "fuente": "Usuario",
}


# ============================================================
# INTERPOLACIÓN LINEAL PARA AGUA ENTRE 0 Y 100 °C
# ============================================================

def propiedades_agua_interpoladas(temperatura_c):
    T = float(temperatura_c)

    if T < min(AGUA_MOTT) or T > max(AGUA_MOTT):
        raise ValueError(
            "La tabla de agua de Mott incluida cubre de 0 a 100 °C. "
            "Fuera de ese intervalo use Fluido personalizado."
        )

    if T in AGUA_MOTT:
        return dict(AGUA_MOTT[int(T)])

    temperaturas = sorted(AGUA_MOTT)
    t_inf = max(t for t in temperaturas if t < T)
    t_sup = min(t for t in temperaturas if t > T)
    fraccion = (T - t_inf) / (t_sup - t_inf)

    resultado = {}
    for clave in ("gamma_kN_m3", "rho", "mu", "nu"):
        y1 = AGUA_MOTT[t_inf][clave]
        y2 = AGUA_MOTT[t_sup][clave]
        resultado[clave] = y1 + fraccion * (y2 - y1)

    return resultado


# ============================================================
# TABLA 10.5 — fT PARA TUBERÍA DE ACERO COMERCIAL SCH 40
# ============================================================

_FT_MOTT = [
    (15, 0.026),
    (20, 0.024),
    (25, 0.022),
    (32, 0.021),
    (40, 0.020),
    (50, 0.019),
    (65, 0.018),
    (80, 0.017),
    (90, 0.017),
    (100, 0.016),
    (125, 0.015),
    (150, 0.015),
    (200, 0.014),
    (250, 0.013),
    (300, 0.013),
    (350, 0.013),
    (400, 0.012),
    (450, 0.012),
    (500, 0.012),
    (550, 0.012),
    (600, 0.011),
    (700, 0.011),
    (800, 0.011),
    (900, 0.011),
]


def ft_mott_por_diametro(diametro_m):
    """
    Infiere automáticamente el DN más cercano a partir del diámetro introducido.
    Mott Table 10.5 está definida por tamaño nominal de acero comercial Sch 40.
    """
    D_mm = float(diametro_m) * 1000.0
    dn, ft = min(_FT_MOTT, key=lambda item: abs(item[0] - D_mm))
    return {
        "dn": dn,
        "ft": ft,
        "diferencia_mm": abs(dn - D_mm),
    }


# ============================================================
# PÉRDIDAS MENORES — MOTT 7a ED., CAPÍTULO 10
#
# Tabla 10.4: K = f_T (Le/D)
# Figura 10.14: coeficientes K de entrada.
# Sección 10.4: salida a depósito grande, K = 1.0.
# ============================================================

ACCESORIOS = {
    # Válvulas — Mott 7e, Tabla 10.4
    "Válvula de globo — totalmente abierta": {"modelo": "mott_le_d", "le_d": 340.0, "fuente": "Mott 7e — Tabla 10.4"},
    "Válvula angular — totalmente abierta": {"modelo": "mott_le_d", "le_d": 150.0, "fuente": "Mott 7e — Tabla 10.4"},
    "Válvula de compuerta — totalmente abierta": {"modelo": "mott_le_d", "le_d": 8.0, "fuente": "Mott 7e — Tabla 10.4"},
    "Válvula de compuerta — 3/4 abierta": {"modelo": "mott_le_d", "le_d": 35.0, "fuente": "Mott 7e — Tabla 10.4"},
    "Válvula de compuerta — 1/2 abierta": {"modelo": "mott_le_d", "le_d": 160.0, "fuente": "Mott 7e — Tabla 10.4"},
    "Válvula de compuerta — 1/4 abierta": {"modelo": "mott_le_d", "le_d": 900.0, "fuente": "Mott 7e — Tabla 10.4"},
    "Válvula de retención — tipo columpio": {"modelo": "mott_le_d", "le_d": 100.0, "fuente": "Mott 7e — Tabla 10.4"},
    "Válvula de retención — tipo bola": {"modelo": "mott_le_d", "le_d": 150.0, "fuente": "Mott 7e — Tabla 10.4"},
    "Válvula mariposa — totalmente abierta": {"modelo": "mott_butterfly", "fuente": "Mott 7e — Tabla 10.4"},
    "Válvula de pie con colador — disco obturador": {"modelo": "mott_le_d", "le_d": 420.0, "fuente": "Mott 7e — Tabla 10.4"},
    "Válvula de pie con colador — disco articulado": {"modelo": "mott_le_d", "le_d": 75.0, "fuente": "Mott 7e — Tabla 10.4"},

    # Accesorios — Mott 7e, Tabla 10.4
    "Codo 90° estándar": {"modelo": "mott_le_d", "le_d": 30.0, "fuente": "Mott 7e — Tabla 10.4"},
    "Codo 90° radio largo": {"modelo": "mott_le_d", "le_d": 20.0, "fuente": "Mott 7e — Tabla 10.4"},
    "Codo 90° tipo street": {"modelo": "mott_le_d", "le_d": 50.0, "fuente": "Mott 7e — Tabla 10.4"},
    "Codo 45° estándar": {"modelo": "mott_le_d", "le_d": 16.0, "fuente": "Mott 7e — Tabla 10.4"},
    "Codo 45° tipo street": {"modelo": "mott_le_d", "le_d": 26.0, "fuente": "Mott 7e — Tabla 10.4"},
    "Retorno cerrado 180°": {"modelo": "mott_le_d", "le_d": 50.0, "fuente": "Mott 7e — Tabla 10.4"},
    "Tee estándar — paso recto": {"modelo": "mott_le_d", "le_d": 20.0, "fuente": "Mott 7e — Tabla 10.4"},
    "Tee estándar — flujo por ramal": {"modelo": "mott_le_d", "le_d": 60.0, "fuente": "Mott 7e — Tabla 10.4"},

    # Entradas — Mott 7e, Figura 10.14
    "Entrada — tubería proyectada hacia el depósito": {"modelo": "k_fijo", "k": 0.78, "fuente": "Mott 7e — Figura 10.14"},
    "Entrada — borde cuadrado/agudo": {"modelo": "k_fijo", "k": 0.50, "fuente": "Mott 7e — Figura 10.14"},
    "Entrada — achaflanada": {"modelo": "k_fijo", "k": 0.25, "fuente": "Mott 7e — Figura 10.14"},
    "Entrada redondeada — r/D = 0.02": {"modelo": "k_fijo", "k": 0.28, "fuente": "Mott 7e — Figura 10.14"},
    "Entrada redondeada — r/D = 0.04": {"modelo": "k_fijo", "k": 0.24, "fuente": "Mott 7e — Figura 10.14"},
    "Entrada redondeada — r/D = 0.06": {"modelo": "k_fijo", "k": 0.15, "fuente": "Mott 7e — Figura 10.14"},
    "Entrada redondeada — r/D = 0.10": {"modelo": "k_fijo", "k": 0.09, "fuente": "Mott 7e — Figura 10.14"},
    "Entrada bien redondeada — r/D > 0.15": {"modelo": "k_fijo", "k": 0.04, "fuente": "Mott 7e — Figura 10.14"},

    # Salida — Mott 7e, sección 10.4
    "Salida hacia depósito grande": {"modelo": "k_fijo", "k": 1.00, "fuente": "Mott 7e — Sección 10.4"},

    # Auxiliares, mantenidos de forma explícita fuera de la Tabla 10.4
    "Válvula de bola — completamente abierta [auxiliar]": {"modelo": "k_fijo", "k": 0.20, "fuente": "Valor auxiliar; no atribuido a Tabla 10.4 de Mott"},
    "Válvula de diafragma — completamente abierta [auxiliar]": {"modelo": "k_fijo", "k": 2.30, "fuente": "Valor auxiliar; no atribuido a Tabla 10.4 de Mott"},
}


def _le_d_mariposa_por_dn(dn):
    if 50 <= dn <= 200:      # 2–8 in
        return 45.0, "2–8 in"
    if 250 <= dn <= 350:     # 10–14 in
        return 35.0, "10–14 in"
    if 400 <= dn <= 600:     # 16–24 in
        return 25.0, "16–24 in"
    return None, None


def _material_canonico(material):
    if material is None:
        return None
    return ALIASES_MATERIALES.get(material, material)


def _ft_turbulencia_completa(diametro_m, epsilon_m):
    D = float(diametro_m)
    eps = float(epsilon_m)
    if D <= 0:
        raise ValueError("El diámetro debe ser mayor que cero.")
    if eps <= 0:
        return None
    rr = eps / D
    return 1.0 / (-2.0 * math.log10(rr / 3.7)) ** 2


def calcular_ft_mott(diametro_m, material=None):
    """
    Procedimiento de Mott para f_T en K=f_T(Le/D).

    Acero comercial o soldado:
        Tabla 10.5 (tubería nueva, limpia, Schedule 40).

    Otros materiales:
        ε de Tabla 8.2 y f_T en la zona de turbulencia completa
        del diagrama de Moody.
    """
    D = float(diametro_m)
    material = _material_canonico(material)

    if material in (None, "Acero comercial o soldado"):
        info = ft_mott_por_diametro(D)
        return {
            "ft": info["ft"],
            "dn": info["dn"],
            "metodo": "tabla_10_5",
            "fuente": "Mott 7e — Tabla 10.5",
            "advertencia": (
                "fT se seleccionó con el DN más cercano al diámetro interior introducido. "
                "La Tabla 10.5 corresponde a tubería nueva y limpia de acero comercial Schedule 40."
            ),
        }

    epsilon = MATERIALES.get(material)
    if epsilon is None:
        raise ValueError(
            "Para material personalizado, introduzca el K del accesorio manualmente "
            "o seleccione un material de la Tabla 8.2."
        )

    ft = _ft_turbulencia_completa(D, epsilon)

    if ft is None:
        info = ft_mott_por_diametro(D)
        return {
            "ft": info["ft"],
            "dn": info["dn"],
            "metodo": "aproximacion_vidrio",
            "fuente": "Mott 7e — Tablas 8.2 y 10.5",
            "advertencia": (
                "Mott clasifica el vidrio como liso. Para estimar K mediante Le/D "
                "se usó fT de la Tabla 10.5 como aproximación. Si el enunciado proporciona "
                "un K específico, use ese valor."
            ),
        }

    return {
        "ft": ft,
        "dn": None,
        "metodo": "moody_turbulencia_completa",
        "fuente": "Mott 7e — Tabla 8.2 + procedimiento de Tabla 10.4",
        "advertencia": (
            f"Para {material}, fT se obtuvo con ε={epsilon:.3e} m "
            "en la zona de turbulencia completa del diagrama de Moody."
        ),
    }


def calcular_k_accesorio(nombre, diametro_m, material=None):
    """
    Devuelve K unitario según el modelo correspondiente de Mott.
    """
    if nombre not in ACCESORIOS:
        raise KeyError(f"Accesorio no reconocido: {nombre}")

    datos = ACCESORIOS[nombre]
    modelo = datos["modelo"]

    if modelo == "k_fijo":
        return {
            "k": float(datos["k"]),
            "modelo": modelo,
            "fuente": datos["fuente"],
            "descripcion": f"K fijo = {float(datos['k']):.4g}",
            "advertencia": None,
        }

    ft_info = calcular_ft_mott(diametro_m, material)
    ft = float(ft_info["ft"])
    dn = ft_info.get("dn")

    if modelo == "mott_le_d":
        le_d = float(datos["le_d"])
        k = le_d * ft
        detalle_ft = f"fT={ft:.4f}" if dn is None else f"fT={ft:.3f} (DN aprox. {dn})"
        return {
            "k": k,
            "modelo": modelo,
            "fuente": datos["fuente"],
            "le_d": le_d,
            "ft": ft,
            "dn": dn,
            "descripcion": f"Le/D={le_d:g}; {detalle_ft} → K={k:.4g}",
            "advertencia": ft_info.get("advertencia"),
        }

    if modelo == "mott_butterfly":
        dn_info = ft_mott_por_diametro(diametro_m)
        dn_mariposa = dn_info["dn"]
        le_d, rango = _le_d_mariposa_por_dn(dn_mariposa)

        if le_d is None:
            raise ValueError(
                "La Tabla 10.4 de Mott para válvula mariposa totalmente abierta "
                "cubre aproximadamente 2 a 24 in (DN 50 a DN 600). "
                "Para otro tamaño use un K adicional/manual."
            )

        k = le_d * ft
        return {
            "k": k,
            "modelo": modelo,
            "fuente": datos["fuente"],
            "le_d": le_d,
            "ft": ft,
            "dn": dn_mariposa,
            "descripcion": f"Mariposa {rango}; Le/D={le_d:g}; fT={ft:.4f} → K={k:.4g}",
            "advertencia": (
                (ft_info.get("advertencia") or "")
                + " El rango de la mariposa se seleccionó con el DN más cercano."
            ).strip(),
        }

    raise ValueError(f"Modelo de accesorio no implementado: {modelo}")


# ============================================================
# TRANSICIONES DE DIÁMETRO — MOTT 7a ED., CAPÍTULO 10
# ============================================================

_ANGULOS_ENSANCHAMIENTO = [2, 6, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60]
_TABLA_ENSANCHAMIENTO_GRADUAL = {
    1.1: [0.01, 0.01, 0.03, 0.05, 0.10, 0.13, 0.16, 0.18, 0.19, 0.20, 0.21, 0.23],
    1.2: [0.02, 0.02, 0.04, 0.09, 0.16, 0.21, 0.25, 0.29, 0.31, 0.33, 0.35, 0.37],
    1.4: [0.02, 0.03, 0.06, 0.12, 0.23, 0.30, 0.36, 0.41, 0.44, 0.47, 0.50, 0.53],
    1.6: [0.03, 0.04, 0.07, 0.14, 0.26, 0.35, 0.42, 0.47, 0.51, 0.54, 0.57, 0.61],
    1.8: [0.03, 0.04, 0.07, 0.15, 0.28, 0.37, 0.44, 0.50, 0.54, 0.58, 0.61, 0.65],
    2.0: [0.03, 0.04, 0.07, 0.16, 0.29, 0.38, 0.46, 0.52, 0.56, 0.60, 0.63, 0.68],
    2.5: [0.03, 0.04, 0.08, 0.16, 0.30, 0.39, 0.48, 0.54, 0.58, 0.62, 0.65, 0.70],
    3.0: [0.03, 0.04, 0.08, 0.16, 0.31, 0.40, 0.48, 0.55, 0.59, 0.63, 0.66, 0.71],
    4.0: [0.03, 0.05, 0.08, 0.16, 0.31, 0.40, 0.49, 0.56, 0.60, 0.64, 0.67, 0.72],
}


def _interp_1d(x, xs, ys):
    if x <= xs[0]:
        return float(ys[0])
    if x >= xs[-1]:
        return float(ys[-1])
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            t = (x - xs[i]) / (xs[i + 1] - xs[i])
            return float(ys[i] + t * (ys[i + 1] - ys[i]))
    return float(ys[-1])


def k_ensanchamiento_subito(D1, D2):
    D1 = float(D1)
    D2 = float(D2)
    if D1 <= 0 or D2 <= 0 or D2 <= D1:
        raise ValueError("Para un ensanchamiento súbito debe cumplirse D2 > D1 > 0.")
    return (1.0 - (D1 / D2) ** 2) ** 2


def k_ensanchamiento_gradual(D1, D2, angulo_grados):
    D1 = float(D1)
    D2 = float(D2)
    theta = float(angulo_grados)
    if D1 <= 0 or D2 <= 0 or D2 <= D1:
        raise ValueError("Para un ensanchamiento gradual debe cumplirse D2 > D1 > 0.")
    if not (2.0 <= theta <= 60.0):
        raise ValueError("La Tabla 10.2 incluida cubre ángulos de 2° a 60°.")

    ratio = D2 / D1
    ratios = sorted(_TABLA_ENSANCHAMIENTO_GRADUAL)
    ratio_eval = min(max(ratio, ratios[0]), ratios[-1])

    valores_por_ratio = [
        _interp_1d(theta, _ANGULOS_ENSANCHAMIENTO, _TABLA_ENSANCHAMIENTO_GRADUAL[r])
        for r in ratios
    ]
    return _interp_1d(ratio_eval, ratios, valores_por_ratio)

# ============================================================
# SINÓNIMOS DE FLUIDOS PARA EL AUTOLLENADO
# ============================================================

SINONIMOS_FLUIDOS = [
    (["acetona"], "Acetona — 25 °C"),
    (["alcohol etilico", "etanol", "ethyl alcohol"], "Alcohol etílico (etanol) — 25 °C"),
    (["alcohol metilico", "metanol", "methyl alcohol"], "Alcohol metílico (metanol) — 25 °C"),
    (["alcohol propilico", "propanol", "propyl alcohol"], "Alcohol propílico — 25 °C"),
    (["amoniaco acuoso", "aqua ammonia"], "Amoniaco acuoso 25% — 25 °C"),
    (["benceno", "benzene"], "Benceno — 25 °C"),
    (["tetracloruro de carbono", "carbon tetrachloride"], "Tetracloruro de carbono — 25 °C"),
    (["aceite de ricino", "castor oil"], "Aceite de ricino — 25 °C"),
    (["etilenglicol", "ethylene glycol"], "Etilenglicol — 25 °C"),
    (["gasolina", "gasoline"], "Gasolina — 25 °C"),
    (["glicerina", "glycerin", "glycerol"], "Glicerina — 25 °C"),
    (["queroseno", "kerosene"], "Queroseno — 25 °C"),
    (["aceite de linaza", "linseed oil"], "Aceite de linaza — 25 °C"),
    (["mercurio", "mercury"], "Mercurio — 25 °C"),
    (["propano liquido", "liquid propane"], "Propano líquido — 25 °C"),
    (["agua de mar", "seawater"], "Agua de mar — 25 °C"),
    (["trementina", "turpentine"], "Trementina — 25 °C"),
    (["aceite de petroleo medio", "fuel oil medium", "fuel oil, medium"], "Aceite de petróleo medio — 25 °C"),
    (["aceite de petroleo pesado", "fuel oil heavy", "fuel oil, heavy"], "Aceite de petróleo pesado — 25 °C"),
    (["aceite de oliva", "olive oil"], "Aceite de oliva — 20 °C [aprox.]"),
    (["miel", "honey"], "Miel — 21 °C [aprox.]"),
    (["ketchup"], "Ketchup — 21 °C [aprox.]"),
    (["mantequilla de mani", "peanut butter"], "Mantequilla de maní — 21 °C [aprox.]"),
]


def _temperatura_catalogo_aceite(temperatura_c, disponibles):
    if temperatura_c is None:
        return disponibles[0]
    return min(disponibles, key=lambda t: abs(float(t) - float(temperatura_c)))


def _clave_aceite_desde_texto(texto, temperatura_c=None):
    """Reconoce las familias principales del Apéndice C de Mott."""
    t = texto.lower()

    if "hidraul" in t and ("automotr" in t or "automotive" in t):
        temp = _temperatura_catalogo_aceite(temperatura_c, [40, 100])
        return f"Aceite hidráulico automotriz — {temp} °C"

    if ("aceite de motor" in t or "engine oil" in t):
        for grado in (20, 40, 60):
            if re.search(rf"(?:grado(?: de viscosidad)?|grade)\s*{grado}\b", t) or re.search(rf"\bsae\s*{grado}\b", t):
                return f"Aceite de motor — grado de viscosidad {grado} — 100 °C"

    if "engranaj" in t or "gear lubricant" in t or "gear oil" in t:
        for grado in (80, 140):
            if re.search(rf"(?:grado(?: de viscosidad)?|grade)\s*{grado}\b", t) or re.search(rf"\bsae\s*{grado}\b", t):
                return f"Lubricante de engranajes — grado de viscosidad {grado} — 100 °C"

    if ("maquina-herramienta" in t or "maquina herramienta" in t or "machine tool" in t):
        temp = _temperatura_catalogo_aceite(temperatura_c, [40, 100])
        nivel = None
        if any(x in t for x in ("baja temperatura", "low temperature")):
            nivel = "baja temperatura"
        elif any(x in t for x in ("ligero", "light")):
            nivel = "ligero"
        elif any(x in t for x in ("medio", "medium")):
            nivel = "medio"
        elif any(x in t for x in ("pesado", "heavy")):
            nivel = "pesado"

        if nivel:
            if "hidraul" in t:
                return f"Aceite hidráulico de máquina-herramienta — {nivel} — {temp} °C"
            if "lubric" in t or "oil" in t or "aceite" in t:
                if nivel != "baja temperatura":
                    return f"Aceite lubricante de máquina-herramienta — {nivel} — {temp} °C"

    return None


def clave_fluido_desde_texto(texto_normalizado, temperatura_c=None):
    texto = texto_normalizado.lower()

    # Primero aceites del Apéndice C, porque contienen la palabra aceite.
    clave_aceite = _clave_aceite_desde_texto(texto, temperatura_c)
    if clave_aceite in ACEITES_MOTT:
        return clave_aceite

    # Sangre tiene dos temperaturas tabuladas.
    if "sangre" in texto or "blood" in texto:
        temp = _temperatura_catalogo_aceite(temperatura_c, [10, 37])
        return f"Sangre — {temp} °C [aprox.]"

    # Agua de mar y líquidos específicos deben revisarse antes que agua.
    for expresiones, clave in SINONIMOS_FLUIDOS:
        if any(expresion in texto for expresion in expresiones):
            return clave

    if "agua" in texto or "water" in texto:
        if temperatura_c is None:
            return "Agua a 20 °C"

        for T in AGUA_MOTT:
            if abs(float(temperatura_c) - float(T)) < 1e-9:
                return f"Agua a {T} °C"

        return "Agua — interpolar temperatura"

    return None
