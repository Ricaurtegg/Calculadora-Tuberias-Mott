import json
from pathlib import Path

from clasificar_problema import identificar_clase_automaticamente
from consolidacion_datos import consolidar_resultado
from transferencia_v147 import construir_previsualizacion_transferencia
from reporte_final_v149 import construir_manifiesto_ejecucion
from flujo_automatico_v1410 import resolver_flujo_confirmado
from comparador_escenarios_v1420 import _delta_pct, VERSION_COMPARADOR, REVISION_COMPARADOR


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)

T112 = '''Un aceite lubricante debe suministrarse a través de una tubería horizontal de acero DN 150 cédula 40 con una caída de presión máxima de 60 kPa por cada 100 metros de tubería. El aceite tiene gravedad específica de 0.88 y viscosidad dinámica de 9.5 x 10^-3 Pa.s. Determine la rapidez del flujo volumétrico máximo permisible para el aceite. Utilice un enfoque de prueba y error, a partir de la ecuación de Darcy-Weisbach.'''

T113 = '''Se debe suministrar un aceite lubricante a través del sistema de tuberías mostrado, con una caída máxima de presión de 60 kPa entre los puntos 1 y 2. El aceite tiene gravedad específica de 0.88 y viscosidad dinámica de 9.5 x 10^-3 Pa.s. Determine la rapidez del flujo volumétrico máxima permisible para el aceite. El sistema está en un plano horizontal. Todas las tuberías son DN 150 Schedule 40 steel. Longitudes 30 m, 40 m y 30 m. Hay dos codos estándar y una válvula mariposa totalmente abierta.'''

TSPR = '''Con la finalidad de asegurar el funcionamiento adecuado de los aspersores en el green, la presión en el punto B debe ser de al menos 60 lb/pulg^2 relativas. Determine el tamaño más pequeño permisible de tubería estándar de Calibre 40 para alimentar 0.50 pies^3/s de agua a 60 °F. La tubería tiene 600 pies de longitud y el punto B está 25 pies por encima de A.'''

print('[1/14] V14.20.1 activa y limpia ruido numérico...')
ok(VERSION_COMPARADOR == 'V14.20' and REVISION_COMPARADOR == 'V14.20.1', (VERSION_COMPARADOR,REVISION_COMPARADOR))
ok(_delta_pct(36.5890460000004, 36.589046) == 0.0, _delta_pct(36.5890460000004, 36.589046))
print('  OK')

print('[2/14] Ejemplo Mott 11.2 se clasifica como II-A...')
r112 = identificar_clase_automaticamente(T112)
ok(r112['clase'] == 'Clase II-A', r112)
print('  OK')

print('[3/14] 11.2 reconoce SG y μ=9.5e-3 Pa.s y calcula rho/nu...')
c112 = consolidar_resultado(r112, T112)
pf112 = c112['prefill']
ok(abs(pf112['rho_usuario'] - 880.0) < 1e-9, pf112)
ok(abs(pf112['mu_usuario_pa_s'] - 9.5e-3) < 1e-12, pf112)
ok(abs(pf112['nu_usuario_m2s'] - 9.5e-3/880.0) < 1e-12, pf112)
print('  OK')

print('[4/14] 11.2 interpreta ΔP, horizontal, L=100m y DN150 Sch40 sin preguntar datos extra...')
ok(abs(pf112['P1_kpa']-60.0)<1e-9 and abs(pf112['P2_kpa'])<1e-9, pf112)
ok(abs(pf112['z1_m'])<1e-12 and abs(pf112['z2_m'])<1e-12, pf112)
ok(len(pf112['tramos'])==1 and abs(pf112['tramos'][0]['L_m']-100.0)<1e-9 and abs(pf112['tramos'][0]['D_m']-0.1541)<2e-4, pf112)
ok(c112['expediente_v145']['cantidad_faltantes']==0, c112['expediente_v145'])
print('  OK')

print('[5/14] 11.2 resuelve end-to-end contra caso dorado de Mott...')
p=construir_previsualizacion_transferencia(c112,T112); ok(p['listo_para_transferir'],p)
m=construir_manifiesto_ejecucion(c112,T112,p)
f=resolver_flujo_confirmado(c112,T112,p,p['firma'],m)
q=float(f['resultado_solver']['Q_final'])
ok(abs(q-0.0570)/0.0570 < 0.015, q)
ok(f['auditoria']['estado']=='OK', f['auditoria'])
print(f'  OK: Q={q:.8f} m3/s')

print('[6/14] Ejemplo Mott 11.3 se clasifica como II-B...')
r113=identificar_clase_automaticamente(T113)
ok(r113['clase']=='Clase II-B',r113)
print('  OK')

print('[7/14] 11.3 suma 30+40+30 m y reconoce 2 codos + mariposa...')
c113=consolidar_resultado(r113,T113); pf113=c113['prefill']
ok(len(pf113['tramos'])==1 and abs(pf113['tramos'][0]['L_m']-100.0)<1e-9,pf113['tramos'])
acc=pf113['tramos'][0].get('accesorios') or []
blob=json.dumps(acc,ensure_ascii=False)
ok('Codo 90° estándar' in blob and '"cantidad": 2' in blob,blob)
ok('Válvula mariposa — totalmente abierta' in blob,blob)
print('  OK')

print('[8/14] 11.3 resuelve end-to-end contra Mott...')
p=construir_previsualizacion_transferencia(c113,T113); ok(p['listo_para_transferir'],p)
m=construir_manifiesto_ejecucion(c113,T113,p)
f=resolver_flujo_confirmado(c113,T113,p,p['firma'],m)
q=float(f['resultado_solver']['Q_final'])
ok(abs(q-5.39e-3) > 1e-3, 'sanity: imagen publicada usa otra escala/edición; no debe confundirse con caso dorado interno')
ok(abs(q-0.0538)/0.0538 < 0.02,q)
print(f'  OK: Q={q:.8f} m3/s')

print('[9/14] Problema de aspersores identifica tamaño mínimo como III-A, no Clase I...')
rs=identificar_clase_automaticamente(TSPR)
ok(rs['clase']=='Clase III-A',rs)
print('  OK')

print('[10/14] Aspersores reconoce 0.50 pies³/s, P_B=60 psi y agua a 60F...')
cs=consolidar_resultado(rs,TSPR); pfs=cs['prefill']
ok(abs(pfs['Q_m3s']-0.5*0.028316846592)<1e-12,pfs)
ok(abs(pfs['P2_kpa']-60*6.894757293)<1e-6,pfs)
ok(abs(pfs['temperatura_c']-15.5555555556)<1e-6,pfs)
print('  OK')

print('[11/14] Aspersores no confunde pies³/s con una longitud...')
ok(len(pfs['tramos'])==1,pfs['tramos'])
ok(abs(pfs['tramos'][0]['L_m']-182.88)<1e-9,pfs['tramos'])
print('  OK')

print('[12/14] Aspersores interpreta B 25 ft sobre A como Δz=7.62 m...')
ok(abs(pfs['z1_m'])<1e-12 and abs(pfs['z2_m']-7.62)<1e-9,pfs)
print('  OK')

print('[13/14] Aspersores pide solo datos realmente ausentes del recorte...')
falt={(x.get('clave'),x.get('etiqueta')) for x in cs['expediente_v145']['faltantes']}
ok(('P1_kpa','Presión P1') in falt,falt)
ok(any(x[0]=='material' for x in falt),falt)
ok(not any(x[0] in {'Q_m3s','P2_kpa','L_m','D_m'} for x in falt),falt)
print('  OK')

print('[14/14] app.py contiene el pulido visual V14.20.1...')
app=Path('app.py').read_text(encoding='utf-8')
ok('tabla_visual' in app and 'abs() < 1e-7' in app, 'Falta formato visual del comparador')
print('  OK')

print('\nTODAS LAS PRUEBAS V14.20.1 / PULIDO PRE-V15 PASARON.')
