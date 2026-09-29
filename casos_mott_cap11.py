"""Casos dorados de regresión — Mott 7.ª edición, Capítulo 11.

Los datos se conservan en SI para alimentar el motor interno de la aplicación.
Los resultados publicados por Mott se guardan como referencia; las tolerancias
consideran redondeo y que el libro lee algunos factores f del diagrama de Moody,
mientras la aplicación usa cálculo numérico de Colebrook.
"""

FT_TO_M = 0.3048
CFS_TO_M3S = 0.028316846592
PSI_TO_PA = 6894.757293168
FT2S_TO_M2S = 0.09290304
LBF_FT3_TO_N_M3 = 4.4482216152605 / 0.028316846592

CASOS = {
    "I_11_1": {
        "nombre": "Mott 7e — Ejemplo 11.1 — Clase I",
        "clase": "Clase I",
        "Q": 54.0 / 3600.0,
        "gamma": 7.74e3,
        "nu": 5.60e-4 / 789.0,
        "eficiencia": 0.76,
        "z1": 0.0,
        "z2": 10.0,
        "P1": 0.0,
        "P2": 0.0,
        "tramos": [
            {
                "numero": 1, "L": 15.0, "D": 0.1023,
                "material": "Acero comercial o soldado",
                "epsilon": 4.6e-5,
                # Entrada de borde cuadrado K=0.5
                "K": 0.5, "K_extra": 0.0,
                "accesorios_detalle": [],
                "componentes_graficos": [],
                "K_extra_posicion_fraccion": 0.85,
            },
            {
                "numero": 2, "L": 200.0, "D": 0.0525,
                "material": "Acero comercial o soldado",
                "epsilon": 4.6e-5,
                # Mott: fT=0.019; globo Le/D=340; 2 codos std 30 c/u; salida K=1
                "K": 0.019 * (340.0 + 2.0 * 30.0) + 1.0,
                "K_extra": 0.0,
                "accesorios_detalle": [],
                "componentes_graficos": [],
                "K_extra_posicion_fraccion": 0.85,
            },
        ],
        "esperado": {
            "hL_m": 207.4,
            "hA_m": 217.4,
            "potencia_entrada_kW": 33.2,
        },
        "tolerancia_rel": 0.03,
        "nota": "Mott usa factores f leídos del diagrama de Moody; se admite diferencia numérica pequeña.",
    },

    "IIA_11_2": {
        "nombre": "Mott 7e — Ejemplo 11.2 — Clase II-A",
        "clase": "Clase II-A",
        "nu": 1.08e-5,
        "gamma": 8.63e3,
        "P1": 120e3,
        "P2": 60e3,
        "z1": 0.0,
        "z2": 0.0,
        "hA": 0.0,
        "hR": 0.0,
        "tipo_v1": "tuberia",
        "tipo_v2": "tuberia",
        "tramos": [{
            "numero": 1, "L": 100.0, "D": 0.1541,
            "material": "Acero comercial o soldado",
            "epsilon": 4.6e-5, "K": 0.0, "K_extra": 0.0,
            "accesorios_detalle": [],
            "componentes_graficos": [],
            "K_extra_posicion_fraccion": 0.85,
        }],
        "esperado": {"Q_m3s": 0.0570},
        "tolerancia_rel": 0.015,
    },

    "IIB_11_3": {
        "nombre": "Mott 7e — Ejemplo 11.3 — Clase II-B",
        "clase": "Clase II-B",
        "nu": 1.08e-5,
        "gamma": 8.63e3,
        "P1": 120e3,
        "P2": 60e3,
        "z1": 0.0,
        "z2": 0.0,
        "hA": 0.0,
        "hR": 0.0,
        "tipo_v1": "tuberia",
        "tipo_v2": "tuberia",
        "tramos": [{
            "numero": 1, "L": 100.0, "D": 0.1541,
            "material": "Acero comercial o soldado",
            "epsilon": 4.6e-5,
            # fT=0.015; dos codos estándar K=.45 c/u; mariposa K=.675
            "K": 2.0 * 0.45 + 0.675,
            "K_extra": 0.0,
            "accesorios_detalle": [],
            "componentes_graficos": [],
            "K_extra_posicion_fraccion": 0.85,
        }],
        "esperado": {"Q_m3s": 0.0538},
        "tolerancia_rel": 0.02,
    },

    "IIC_11_4": {
        "nombre": "Mott 7e — Ejemplo 11.4 — Clase II-C",
        "clase": "Clase II-C",
        "nu": 9.15e-6 * FT2S_TO_M2S,
        "gamma": 62.4 * LBF_FT3_TO_N_M3,
        "P1": 0.0,
        "P2": 0.0,
        "z1": 40.0 * FT_TO_M,
        "z2": 0.0,
        "hA": 0.0,
        "hR": 0.0,
        "tipo_v1": "deposito",
        "tipo_v2": "tuberia",
        "tramos": [{
            "numero": 1,
            "L": 330.0 * FT_TO_M,
            "D": 0.3355 * FT_TO_M,
            "material": "Acero comercial o soldado",
            "epsilon": 1.5e-4 * FT_TO_M,
            # Entrada 1.0 + codo LR 20*.016 + compuerta 1/2 160*.016 = 3.88
            "K": 3.88,
            "K_extra": 0.0,
            "accesorios_detalle": [],
            "componentes_graficos": [],
            "K_extra_posicion_fraccion": 0.85,
        }],
        "esperado": {
            "Q_m3s": 0.955 * CFS_TO_M3S,
            "Q_ft3s": 0.955,
            "f": 0.0175,
        },
        "tolerancia_rel": 0.02,
    },

    "IIIA_11_5": {
        "nombre": "Mott 7e — Ejemplo 11.5 — Clase III-A",
        "clase": "Clase III-A",
        "Q": 0.50 * CFS_TO_M3S,
        "L": 100.0 * FT_TO_M,
        "epsilon": 1.5e-4 * FT_TO_M,
        "nu": 1.21e-5 * FT2S_TO_M2S,
        "hL_permitida": 4.62 * FT_TO_M,
        "catalogo": "Acero Schedule 40 — Mott Apéndice F",
        "esperado": {
            "D_min_m": 0.309 * FT_TO_M,
            "D_min_ft": 0.309,
            "nps": "4",
            "D_comercial_m": 0.3355 * FT_TO_M,
        },
        "tolerancia_rel": 0.012,
    },

    "IIIB_11_6": {
        "nombre": "Mott 7e — Ejemplo 11.6 — Clase III-B",
        "clase": "Clase III-B",
        "D": 0.3355 * FT_TO_M,
        "Q": 0.50 * CFS_TO_M3S,
        "L": 100.0 * FT_TO_M,
        "epsilon": 1.5e-4 * FT_TO_M,
        "nu": 1.21e-5 * FT2S_TO_M2S,
        "gamma": 62.4 * LBF_FT3_TO_N_M3,
        "P1": 102.0 * PSI_TO_PA,
        "P2_deseada": 100.0 * PSI_TO_PA,
        "z1": 0.0,
        "z2": 0.0,
        "hA": 0.0,
        "hR": 0.0,
        "tipo_v1": "tuberia",
        "tipo_v2": "tuberia",
        # 2 codos radio largo: 2*(.016*20) + mariposa (.016*45) = 1.36
        "K": 1.36,
        "esperado": {
            "P2_psi": 100.48,
            "hL_ft": 3.51,
            "V_fts": 5.66,
        },
        "tolerancia_rel": 0.015,
    },
}
