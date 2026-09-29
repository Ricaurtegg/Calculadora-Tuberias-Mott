from pathlib import Path
from clasificar_problema import identificar_clase_automaticamente, detectar_accesorios
from catalogos_mott import calcular_k_accesorio
from metodos_mott import resolver_clase_ii_mott_v9


def ok(c, m):
    if not c:
        raise AssertionError(m)

print('[1/4] Reconocimiento de "dos codos estandar de 90 grados"...')
a = detectar_accesorios('dos codos estandar de 90 grados')
item = next((x for x in a if x['nombre'] == 'Codo 90° estándar'), None)
ok(item is not None and item['cantidad'] == 2, f'Esperaba 2 codos; obtenido: {a}')
print('  OK')

print('[2/4] Enunciado de equivalencia conserva Clase II-C...')
texto = '''Agua a 20 °C fluye desde un deposito cerrado A hacia un deposito abierto B a traves de una tuberia de acero comercial de diametro interior D = 102.3 mm y longitud L = 120 m.
La superficie libre del deposito A esta a una elevacion z1 = 18.0 m y la superficie libre del deposito B esta a z2 = 5.0 m. Sobre la superficie del deposito A actua una presion manometrica P1 = 85 kPa. El deposito B esta abierto a la atmosfera, por lo que P2 = 0 kPa manometricos.
La tuberia contiene los siguientes elementos de perdida menor: una entrada de borde agudo con K = 0.50, dos codos estandar de 90 grados, una valvula de compuerta totalmente abierta y una salida a deposito grande con K = 1.00.
Desprecie las velocidades en las superficies libres de ambos depositos. Determine el caudal Q que circula por el sistema. Incluya la perdida por friccion en la tuberia y todas las perdidas menores. Utilice el procedimiento de Mott, 7a edicion.'''
r = identificar_clase_automaticamente(texto)
ok(r['clase'] == 'Clase II-C', f"Clase inesperada: {r['clase']}")
print('  OK')

print('[3/4] Prefill contiene los 2 codos además de entrada, compuerta y salida...')
acc = r['prefill']['tramos'][0]['accesorios']
counts = {x['nombre']: x['cantidad'] for x in acc}
ok(counts.get('Codo 90° estándar') == 2, f'Codos no reconocidos: {acc}')
ok(counts.get('Entrada — borde cuadrado/agudo') == 1, 'Falta entrada')
ok(counts.get('Válvula de compuerta — totalmente abierta') == 1, 'Falta compuerta')
ok(counts.get('Salida hacia depósito grande') == 1, 'Falta salida')
print('  OK')

print('[4/4] Resultado hidráulico de referencia con todos los accesorios...')
D=0.1023
mat='Acero comercial o soldado'
k_entrada=0.50
k_codo=calcular_k_accesorio('Codo 90° estándar',D,mat)['k']
k_gate=calcular_k_accesorio('Válvula de compuerta — totalmente abierta',D,mat)['k']
k_salida=1.00
K=k_entrada+2*k_codo+k_gate+k_salida
ok(abs(K-2.588)<1e-9, f'K esperado 2.588; obtenido {K}')
tr=[{'numero':1,'L':120.0,'D':D,'material':mat,'epsilon':4.6e-5,'K':K,'K_extra':0.0,'K_extra_posicion_fraccion':0.85,'accesorios_detalle':[],'componentes_graficos':[]}]
sol=resolver_clase_ii_mott_v9(metodo='II-C',tramos=tr,nu=1.02e-6,gamma=9790.0,P1=85000.0,P2=0.0,z1=18.0,z2=5.0,hA=0.0,hR=0.0,tipo_v1='deposito',tipo_v2='deposito',transiciones=[])
ok(abs(sol['Q']-0.0352705849)<2e-8, f"Q inesperado {sol['Q']}")
print(f"  OK: K={K:.3f}, Q={sol['Q']:.8f} m³/s")

print('\nTODAS LAS PRUEBAS V14.1.1 PASARON.')
