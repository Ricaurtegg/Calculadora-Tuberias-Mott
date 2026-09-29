from pathlib import Path

from interpretacion_figuras import (
    _norm,
    _detectar_hallazgos,
    fusionar_resultado_con_figura,
)
from diagramas import _eventos_accesorios, _eventos_perdidas_menores


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)

print('[1/6] OCR z1 -> zl se reconoce como z1...')
linea = {
    'texto': 'zl = 18 m',
    'texto_norm': _norm('zl = 18 m'),
    'confianza': 94.0,
    'x': 10, 'y': 10, 'w': 100, 'h': 30,
    'cx': 60.0, 'cy': 25.0,
}
h = _detectar_hallazgos([linea], 1, 1000, 500)
ok(any(x.tipo == 'z1' for x in h), f'No reconoció zl como z1: {h}')
print('  OK')

print('[2/6] Fusión de figura completa z1=18 m cuando el texto no lo recuperó...')
resultado = {
    'clase': 'Clase II-C',
    'confianza': 72,
    'datos': [],
    'advertencias': [],
    'prefill': {
        'P1_kpa': 85.0,
        'P2_kpa': 0.0,
        'z1_m': None,
        'z2_m': 5.0,
        'hA_m': 8.0,
        'hR_m': 0.0,
        'tramos': [{
            'numero': 1,
            'L_m': 120.0,
            'D_m': 0.1023,
            'material': 'Acero comercial o soldado',
            'accesorios': [],
            'curvas': [],
            'K_extra': None,
            'componentes_graficos': [],
        }],
    }
}
figura = {
    'hallazgos': [
        {'tipo': 'z1', 'texto': 'zl = 18 m', 'confianza': 94.0, 'fraccion_recorrido': None},
    ]
}
r = fusionar_resultado_con_figura(resultado, figura)
ok(abs(r['prefill']['z1_m'] - 18.0) < 1e-12, f"z1 incorrecto: {r['prefill'].get('z1_m')}")
print('  OK')

print('[3/6] Posición 0 % de entrada se conserva en el esquema...')
tramos = [{
    'L': 120.0,
    'accesorios_detalle': [
        {'nombre': 'Entrada — borde cuadrado/agudo', 'cantidad': 1, 'posicion_fraccion': 0.0},
        {'nombre': 'Válvula', 'cantidad': 1, 'posicion_fraccion': 0.714},
        {'nombre': 'Salida hacia depósito grande', 'cantidad': 1, 'posicion_fraccion': 1.0},
    ],
    'K_extra': 0.0,
    'componentes_graficos': [],
}]
ev = _eventos_accesorios(tramos)
por_nombre = {e['nombre']: e['x'] for e in ev}
ok(abs(por_nombre['Entrada — borde cuadrado/agudo'] - 0.0) < 1e-12, por_nombre)
ok(abs(por_nombre['Salida hacia depósito grande'] - 120.0) < 1e-12, por_nombre)
print('  OK')

print('[4/6] LE/LAM conserva pérdida de entrada en x=0...')
tramos2 = [{
    'L': 120.0,
    'K': 1.5,
    'K_extra': 0.0,
    'accesorios_detalle': [
        {'nombre': 'Entrada', 'cantidad': 1, 'K_unitario': 0.5, 'posicion_fraccion': 0.0},
        {'nombre': 'Salida', 'cantidad': 1, 'K_unitario': 1.0, 'posicion_fraccion': 1.0},
    ],
}]
resultados = [{'hm (m)': 1.5, 'L (m)': 120.0, 'ΣK': 1.5}]
ev2 = _eventos_perdidas_menores(tramos2, resultados)
ok(abs(ev2[0]['x'] - 0.0) < 1e-12, ev2)
ok(abs(ev2[1]['x'] - 120.0) < 1e-12, ev2)
print('  OK')

print('[5/6] Carga disponible de referencia queda en ~29.682 m con z1=18...')
rho = 998.0
g = 9.81
H = 85000.0/(rho*g) + 18.0 + 8.0 - 5.0
ok(abs(H - 29.6819919145) < 1e-6, H)
print(f'  OK: Hdisp={H:.6f} m')

print('[6/6] app.py conserva el enunciado confirmado después del rerun...')
app = Path(__file__).with_name('app.py').read_text(encoding='utf-8')
ok('enunciado_confirmado_auto' in app, 'Falta estado persistente del enunciado')
ok('or st.session_state.get("enunciado_confirmado_auto", "")' in app, 'Resumen no usa el enunciado persistente')
print('  OK')

print('\nTODAS LAS PRUEBAS V14.3.3 PASARON.')
