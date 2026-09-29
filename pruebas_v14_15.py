from pathlib import Path
import copy
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from transferencia_v147 import construir_previsualizacion_transferencia
from reporte_final_v149 import construir_manifiesto_ejecucion
from flujo_automatico_v1410 import resolver_flujo_confirmado
from diagramas import (
    VERSION_DIAGRAMAS_AVANZADOS,
    crear_esquema_sistema,
    crear_lineas_energia,
    crear_perdidas_acumuladas_v1415,
    construir_perfil_perdidas_v1415,
)

BASE = Path(__file__).resolve().parent
APP = (BASE / 'app.py').read_text(encoding='utf-8')


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)


def iic_completo():
    return {
        'clase': 'Clase II-C', 'confianza': 96,
        'prefill': {
            'fluido_app': 'Agua a 20 °C', 'fluido_detectado': 'Agua a 20 °C',
            'P1_kpa': 135.0, 'P2_kpa': 0.0,
            'z1_m': 31.2, 'z2_m': 8.4, 'hA_m': 0.0, 'hR_m': 0.0,
            'v1_tipo': 'deposito', 'v2_tipo': 'deposito',
            'tramos': [
                {'numero': 1, 'L_m': 68.5, 'D_m': 0.100, 'material': 'Acero comercial o soldado',
                 'accesorios': [
                     {'nombre': 'Entrada — borde cuadrado/agudo', 'cantidad': 1, 'posicion_fraccion': 0.05},
                     {'nombre': 'Codo 90° estándar', 'cantidad': 2, 'posiciones_fraccion': [0.45, 0.80]},
                 ], 'componentes_graficos': []},
                {'numero': 2, 'L_m': 96.3, 'D_m': 0.075, 'material': 'Plástico',
                 'accesorios': [
                     {'nombre': 'Válvula de compuerta — totalmente abierta', 'cantidad': 1, 'posicion_fraccion': 0.32},
                     {'nombre': 'Salida hacia depósito grande', 'cantidad': 1, 'posicion_fraccion': 0.98},
                 ], 'componentes_graficos': []},
            ],
            'transiciones': [{'entre': 1, 'tipo': 'Contracción súbita', 'angulo_grados': None}],
        },
    }


def preparar(r, en='Determine el caudal Q del sistema.'):
    p = construir_previsualizacion_transferencia(r, en)
    ok(p['listo_para_transferir'], p)
    m = construir_manifiesto_ejecucion(r, en, p)
    return resolver_flujo_confirmado(r, en, p, p['firma'], m)


print('[1/12] V14.15 está activa y el flujo automático entrega contexto gráfico...')
f = preparar(iic_completo())
ctx = f.get('contexto_diagramas_v1415') or {}
ok(VERSION_DIAGRAMAS_AVANZADOS == 'V14.15', VERSION_DIAGRAMAS_AVANZADOS)
ok(ctx.get('disponible') is True, ctx)
ok(len(ctx.get('tramos') or []) == 2, ctx)
print('  OK')

print('[2/12] El contexto automático conserva exactamente el sistema resuelto...')
sis = f['resultado_solver']['sistema']
ok(abs(ctx['sistema']['hL_total'] - sis['hL_total']) < 1e-12, (ctx['sistema'], sis))
ok(abs(ctx['Q_m3s'] - f['resultado_solver']['Q_final']) < 1e-12, ctx)
print('  OK')

print('[3/12] Perfil acumulado cierra con hf + hm accesorios + hm transiciones...')
p = construir_perfil_perdidas_v1415(
    ctx['sistema']['resultados'], ctx['tramos'], ctx['transiciones'],
    ctx['hA_m'], ctx['hR_m'], ctx['posicion_bomba_m'], ctx['posicion_turbina_m'],
)
ok(abs(p['total_hf_m'] - sis['total_hf']) < 1e-9, (p, sis))
ok(abs(p['total_hm_accesorios_m'] - sis['total_hm_accesorios']) < 1e-9, (p, sis))
ok(abs(p['total_hm_transiciones_m'] - sis['total_hm_transiciones']) < 1e-9, (p, sis))
ok(abs(p['hL_total_m'] - sis['hL_total']) < 1e-9, (p, sis))
print('  OK')

print('[4/12] El perfil conserva eventos de accesorios y transición...')
grupos = [e.get('grupo') for e in p['eventos']]
ok('accesorios' in grupos, p['eventos'])
ok('transiciones' in grupos, p['eventos'])
print('  OK')

print('[5/12] Esquema avanzado admite etiquetas activadas y modo compacto...')
fig1 = crear_esquema_sistema(
    ctx['tramos'], ctx['z1_m'], ctx['z2_m'], ctx['tipo_v1'], ctx['tipo_v2'],
    ctx['hA_m'], ctx['hR_m'], ctx['posicion_bomba_m'], ctx['posicion_turbina_m'],
    ctx.get('z_nodos_m') or None, ctx['transiciones'], 'V14.15 esquema completo',
    True, True, True, True, True,
)
fig2 = crear_esquema_sistema(
    ctx['tramos'], ctx['z1_m'], ctx['z2_m'], ctx['tipo_v1'], ctx['tipo_v2'],
    ctx['hA_m'], ctx['hR_m'], ctx['posicion_bomba_m'], ctx['posicion_turbina_m'],
    ctx.get('z_nodos_m') or None, ctx['transiciones'], 'V14.15 esquema compacto',
    False, False, False, False, False,
)
ok(len(fig1.axes) == 1 and len(fig2.axes) == 1, 'Figuras inválidas')
plt.close(fig1); plt.close(fig2)
print('  OK')

print('[6/12] LE/LAM avanzada se genera directamente desde el flujo automático...')
fig = crear_lineas_energia(
    ctx['sistema']['resultados'], ctx['gamma'], ctx['P1_pa'], ctx['z1_m'], ctx['P2_pa'], ctx['z2_m'],
    ctx['V1_ms'], ctx['V2_ms'], ctx['hA_m'], ctx['hR_m'], ctx['tramos'],
    ctx['posicion_bomba_m'], ctx['posicion_turbina_m'], ctx['transiciones'],
    titulo='V14.15 LE/LAM', mostrar_marcadores_eventos=True, mostrar_etiquetas_eventos=True,
)
ok(len(fig.axes[0].lines) >= 2, 'No generó LE/LAM')
plt.close(fig)
print('  OK')

print('[7/12] Gráfico de pérdidas acumuladas se genera y contiene cuatro series...')
fig = crear_perdidas_acumuladas_v1415(
    ctx['sistema']['resultados'], ctx['tramos'], ctx['transiciones'],
    ctx['hA_m'], ctx['hR_m'], ctx['posicion_bomba_m'], ctx['posicion_turbina_m'],
    True, 'V14.15 pérdidas',
)
ok(len(fig.axes[0].lines) >= 4, len(fig.axes[0].lines))
plt.close(fig)
print('  OK')

print('[8/12] Clase I automática produce contexto gráfico con la condición resuelta...')
r8 = {
    'clase': 'Clase I', 'confianza': 95,
    'prefill': {
        'fluido_app': 'Agua a 20 °C', 'Q_m3s': 0.010,
        'P1_kpa': 0.0, 'P2_kpa': None, 'z1_m': 10.0, 'z2_m': 0.0,
        'hA_m': 0.0, 'hR_m': 0.0, 'v1_tipo': 'deposito', 'v2_tipo': 'deposito',
        'incognita_clase_i': 'Presión P2',
        'tramos': [{'numero': 1, 'L_m': 50.0, 'D_m': 0.08, 'material': 'Acero comercial o soldado', 'accesorios': [], 'componentes_graficos': []}],
        'transiciones': [],
    },
}
f8 = preparar(r8, 'Determine la presión P2.')
ok(f8['contexto_diagramas_v1415']['disponible'], f8['contexto_diagramas_v1415'])
ok(abs(f8['contexto_diagramas_v1415']['P2_pa'] - f8['resultado_solver']['valor']) < 1e-8, f8['contexto_diagramas_v1415'])
print('  OK')

print('[9/12] III-A construye diagrama con el diámetro Mott resuelto, no con un D inventado...')
r9 = {
    'clase': 'Clase III-A', 'confianza': 95,
    'prefill': {
        'fluido_app': 'Agua a 20 °C', 'Q_m3s': 0.010,
        'P1_kpa': 100.0, 'P2_kpa': 0.0, 'z1_m': 10.0, 'z2_m': 0.0,
        'hA_m': 0.0, 'hR_m': 0.0,
        'tramos': [{'numero': 1, 'L_m': 50.0, 'D_m': None, 'material': 'Acero comercial o soldado', 'accesorios': [], 'componentes_graficos': []}],
        'transiciones': [],
    },
}
f9 = preparar(r9, 'Determine el diámetro mínimo.')
c9 = f9['contexto_diagramas_v1415']
ok(c9['disponible'], c9)
ok(abs(c9['tramos'][0]['D'] - f9['resultado_solver']['D_mott']) < 1e-12, c9)
print('  OK')

print('[10/12] III-B usa P2 calculada como frontera del diagrama...')
r10 = copy.deepcopy(r9)
r10['clase'] = 'Clase III-B'
r10['prefill']['tramos'][0]['D_m'] = 0.08
r10['prefill']['v1_tipo'] = 'deposito'; r10['prefill']['v2_tipo'] = 'deposito'
f10 = preparar(r10, 'Verifique si el diámetro satisface la presión requerida.')
c10 = f10['contexto_diagramas_v1415']
ok(c10['disponible'], c10)
ok(abs(c10['P2_pa'] - f10['resultado_solver']['P2_calculada']) < 1e-8, c10)
print('  OK')

print('[11/12] La interfaz automática llama V14.15 antes de exigir el solucionador manual...')
for token in (
    'V14.15 — Diagramas hidráulicos avanzados',
    'mostrar_diagramas_automaticos_v1415(flujo)',
    'Pérdidas acumuladas',
    'Etiquetas en gráficas',
    'crear_perdidas_acumuladas_v1415',
):
    ok(token in APP, f'Falta integración: {token}')
print('  OK')

print('[12/12] El modo manual conserva esquema/LE-LAM y añade pérdidas acumuladas...')
ok('📉 V14.15 — Distribución acumulada de pérdidas' in APP, 'Falta panel manual V14.15')
ok('mostrar_solver_manual_v1410' in APP, 'Se eliminó modo manual')
print('  OK')

print('\nTODAS LAS PRUEBAS V14.15 DE DIAGRAMAS HIDRÁULICOS AVANZADOS PASARON.')
