from vfisicas import (
    validar_clase_ii_previa,
    validar_clase_iii_a_previa,
    validar_clase_iii_b_previa,
    validar_resultados_hidraulicos,
    detectar_atmosfera_y_conflictos,
    hay_bloqueantes,
)
from auditoria_datos import construir_auditoria_datos, hay_conflictos_bloqueantes


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


def main():
    print('[1/6] II-A detecta pérdidas menores configuradas...')
    tramos=[{'L':50.0,'D':0.1,'epsilon':4.6e-5,'K':1.2,'K_extra':0.0}]
    d=validar_clase_ii_previa('II-A',tramos,[],1.02e-6,9790.0,0,0,10,0,0,0,'deposito','deposito')
    assert_true(any(x['codigo']=='IIA_CON_MENORES' for x in d),'No detectó pérdidas menores en II-A')
    print('  OK')

    print('[2/6] Carga disponible no positiva bloquea Clase II...')
    d=validar_clase_ii_previa('II-C',[{'L':10.0,'D':0.1,'epsilon':4.6e-5,'K':1.0}],[],1.02e-6,9790.0,0,0,0,10,0,0,'deposito','deposito')
    assert_true(hay_bloqueantes(d),'Debió bloquear por carga disponible no positiva')
    print('  OK')

    print('[3/6] Región de transición de Reynolds produce advertencia...')
    d=validar_resultados_hidraulicos([{'Re':3000,'f Darcy':0.04,'V (m/s)':1.0}],residual=1e-10)
    assert_true(any(x['codigo']=='RE_TRANSICION_1' for x in d),'No detectó Re de transición')
    assert_true(any(x['codigo']=='RESIDUAL_OK' for x in d),'No validó residual')
    print('  OK')

    print('[4/6] III-B bloquea diámetro menor que Dmín...')
    d=validar_clase_iii_b_previa(0.09,0.01,50,4.6e-5,1e-6,D_minimo_previo=0.0983)
    assert_true(hay_bloqueantes(d),'III-B debió bloquear D<Dmín')
    print('  OK')

    print('[5/6] Depósito abierto con presión manométrica no nula se detecta...')
    pref={'P2_kpa':35.0}
    d=detectar_atmosfera_y_conflictos('El segundo depósito está abierto a la atmósfera y P2 = 35 kPa.',pref)
    assert_true(hay_bloqueantes(d),'No detectó contradicción atmósfera/P2')
    print('  OK')

    print('[6/6] Auditoría marca datos faltantes y conflictos...')
    pref={
        'Q_m3s':0.01,'P1_kpa':10.0,'P2_kpa':0.0,'z1_m':0.0,'z2_m':5.0,
        'fluido_detectado':'agua','temperatura_c':20.0,
        'geometria_vertical_eventos':[], 'advertencias':[],
        'tramos':[{'L_m':50.0,'D_m':None,'material':'Acero comercial','accesorios':[],'componentes_graficos':[]}],
        'transiciones':[]
    }
    filas=construir_auditoria_datos(pref,'P1=10 kPa y luego P1=20 kPa.')
    assert_true(any(f['Estado']=='⚠️ Confirmar' and 'D' in f['Dato'] for f in filas),'No marcó D faltante')
    assert_true(hay_conflictos_bloqueantes(filas),'No detectó conflicto explícito P1')
    print('  OK')

    print('\nTodas las pruebas V10 pasaron correctamente.')

if __name__=='__main__':
    main()
