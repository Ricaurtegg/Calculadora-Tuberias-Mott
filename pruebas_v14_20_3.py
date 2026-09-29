from clasificar_problema import identificar_clase_automaticamente
from consolidacion_datos import consolidar_resultado
from completado_interactivo import aplicar_respuestas_faltantes


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)

OCR_112 = '''Problema de ejemplo 11.2 (método de solución 1): Un aceite lubricante debe suministrarse
a través de una tubería horizontal de acero DN 150 cédula 40 con una caída de presión
máxima de 60 KPa por cada 100 metros de tubería. El aceite tiene gravedad específica de
0.88 y viscosidad dinámica de 9.5 x 10° Pa.s. Determine la rapidez del flujo volumétrico
máximo permisible para el aceite.'''

print('[1/6] OCR identifica el fluido genérico aceite lubricante...')
r = identificar_clase_automaticamente(OCR_112)
p = r['prefill']
ok(r['clase'] == 'Clase II-A', r['clase'])
ok(p.get('fluido_detectado') == 'Aceite lubricante', p)
print('  OK')

print('[2/6] SG se conserva y produce rho=880 kg/m3...')
ok(abs(float(p.get('rho_usuario')) - 880.0) < 1e-9, p)
ok(abs(float(p.get('sg_usuario')) - 0.88) < 1e-12, p)
print('  OK')

print('[3/6] El exponente OCR corrupto no se inventa y queda marcado como ambiguo...')
amb = p.get('mu_ocr_ambigua_v1412')
ok(isinstance(amb, dict) and '10°' in amb.get('original',''), p)
ok(p.get('mu_usuario_pa_s') is None and p.get('nu_usuario_m2s') is None, p)
print('  OK')

print('[4/6] V14.5 pregunta solo mu, no vuelve a pedir el fluido...')
c = consolidar_resultado(r, OCR_112)
falt = c['expediente_v145']['faltantes']
claves = [x.get('clave') for x in falt]
ok(claves == ['mu_usuario_pa_s'], falt)
filas = c['expediente_v145']['filas']
fila_f = next(x for x in filas if x['Dato'] == 'Fluido')
ok(fila_f['Valor'] == 'Aceite lubricante' and 'incompletas' in fila_f['Estado'], fila_f)
fila_rho = next(x for x in filas if x['Dato'] == 'Densidad ρ')
ok('880' in fila_rho['Valor'], fila_rho)
print('  OK')

print('[5/6] Confirmar mu=0.0095 calcula nu=mu/rho y completa el expediente...')
u = aplicar_respuestas_faltantes(c, OCR_112, {'mu_usuario_pa_s': 0.0095})
pp = u['prefill']
ok(pp.get('fluido_app') == 'Personalizado', pp)
ok(pp.get('fluido_detectado') == 'Aceite lubricante', pp)
ok(abs(float(pp['nu_usuario_m2s']) - 0.0095/880.0) < 1e-12, pp)
ok(u['expediente_v145']['cantidad_faltantes'] == 0, u['expediente_v145']['faltantes'])
print('  OK')

print('[6/6] Texto limpio 9.5e-3 no requiere ninguna confirmación de fluido...')
limpio = OCR_112.replace('9.5 x 10° Pa.s', '9.5 x 10^-3 Pa.s')
r2 = consolidar_resultado(identificar_clase_automaticamente(limpio), limpio)
ok(r2['expediente_v145']['cantidad_faltantes'] == 0, r2['expediente_v145']['faltantes'])
ok(abs(float(r2['prefill']['nu_usuario_m2s']) - 0.0095/880.0) < 1e-12, r2['prefill'])
print('  OK')

print('\nTODAS LAS PRUEBAS V14.20.3 / OCR DE PROPIEDADES DE FLUIDO PASARON.')
