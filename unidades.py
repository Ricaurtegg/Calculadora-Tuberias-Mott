"""Conversión de unidades para la interfaz.

El motor hidráulico del proyecto permanece en SI. Este módulo convierte solamente
la entrada/salida de la interfaz para admitir SI y US Customary sin duplicar las
ecuaciones hidráulicas.
"""

M_TO_FT = 3.280839895013123
M_TO_IN = 39.37007874015748
M3S_TO_GPM = 15850.323141489
M3S_TO_FT3S = 35.31466672148859
MS_TO_FTS = 3.280839895013123
KPA_TO_PSI = 0.14503773773020923
KG_M3_TO_LBM_FT3 = 0.062427960576145
M2S_TO_FT2S = 10.763910416709722
PA_S_TO_LBM_FT_S = 0.6719689751395068
N_M3_TO_LBF_FT3 = 0.006365880353829584
W_TO_HP = 0.0013410220895950277

SISTEMA_SI = "SI"
SISTEMA_US = "US Customary"
CAUDAL_US_GPM = "gal/min"
CAUDAL_US_FT3S = "ft³/s"


def es_us(sistema):
    return str(sistema).strip().lower().startswith("us")


def unidad(kind, sistema=SISTEMA_SI, unidad_caudal_us=CAUDAL_US_GPM):
    if not es_us(sistema):
        return {
            "longitud": "m",
            "carga": "m",
            "diametro": "m",
            "rugosidad": "m",
            "presion": "kPa",
            "caudal": "m³/s",
            "velocidad": "m/s",
            "temperatura": "°C",
            "densidad": "kg/m³",
            "nu": "m²/s",
            "mu": "Pa·s",
            "gamma": "N/m³",
            "potencia": "kW",
        }.get(kind, "")
    return {
        "longitud": "ft",
        "carga": "ft",
        "diametro": "in",
        "rugosidad": "in",
        "presion": "psi",
        "caudal": unidad_caudal_us,
        "velocidad": "ft/s",
        "temperatura": "°F",
        "densidad": "lbm/ft³",
        "nu": "ft²/s",
        "mu": "lbm/(ft·s)",
        "gamma": "lbf/ft³",
        "potencia": "hp",
    }.get(kind, "")


def desde_interno(valor, kind, sistema=SISTEMA_SI, unidad_caudal_us=CAUDAL_US_GPM):
    """Convierte del sistema interno actual de app.py a unidad de interfaz.

    Interno: m, kPa, m³/s, m/s, °C, kg/m³, m²/s, Pa·s, N/m³ y kW.
    """
    x = float(valor)
    if not es_us(sistema):
        return x
    if kind in ("longitud", "carga"):
        return x * M_TO_FT
    if kind in ("diametro", "rugosidad"):
        return x * M_TO_IN
    if kind == "presion":
        return x * KPA_TO_PSI
    if kind == "caudal":
        return x * (M3S_TO_FT3S if unidad_caudal_us == CAUDAL_US_FT3S else M3S_TO_GPM)
    if kind == "velocidad":
        return x * MS_TO_FTS
    if kind == "temperatura":
        return x * 9.0 / 5.0 + 32.0
    if kind == "densidad":
        return x * KG_M3_TO_LBM_FT3
    if kind == "nu":
        return x * M2S_TO_FT2S
    if kind == "mu":
        return x * PA_S_TO_LBM_FT_S
    if kind == "gamma":
        return x * N_M3_TO_LBF_FT3
    if kind == "potencia":
        return x * 1000.0 * W_TO_HP  # interno kW
    return x


def a_interno(valor, kind, sistema=SISTEMA_SI, unidad_caudal_us=CAUDAL_US_GPM):
    """Convierte de la interfaz al sistema interno de app.py."""
    x = float(valor)
    if not es_us(sistema):
        return x
    if kind in ("longitud", "carga"):
        return x / M_TO_FT
    if kind in ("diametro", "rugosidad"):
        return x / M_TO_IN
    if kind == "presion":
        return x / KPA_TO_PSI
    if kind == "caudal":
        return x / (M3S_TO_FT3S if unidad_caudal_us == CAUDAL_US_FT3S else M3S_TO_GPM)
    if kind == "velocidad":
        return x / MS_TO_FTS
    if kind == "temperatura":
        return (x - 32.0) * 5.0 / 9.0
    if kind == "densidad":
        return x / KG_M3_TO_LBM_FT3
    if kind == "nu":
        return x / M2S_TO_FT2S
    if kind == "mu":
        return x / PA_S_TO_LBM_FT_S
    if kind == "gamma":
        return x / N_M3_TO_LBF_FT3
    if kind == "potencia":
        return x / (1000.0 * W_TO_HP)
    return x


def convertir_prefill_si_a_ui(valor, kind, sistema=SISTEMA_SI, unidad_caudal_us=CAUDAL_US_GPM):
    """Alias semántico para valores que vienen del parser ya normalizados a SI/app."""
    if valor is None:
        return None
    return desde_interno(valor, kind, sistema, unidad_caudal_us)
