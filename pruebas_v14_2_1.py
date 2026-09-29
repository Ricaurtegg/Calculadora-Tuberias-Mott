from vfisicas import detectar_atmosfera_y_conflictos, hay_bloqueantes


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)


def codigos(diags):
    return {d.get("codigo") for d in diags}


print('[1/5] Caso real V14.2: deposito 1 presurizado -> deposito 2 abierto...')
texto = (
    'Agua a 20 C fluye desde un deposito 1 presurizado hasta un deposito 2 '
    'abierto a la atmosfera a traves de una sola tuberia. '
    'P1 = 85 kPa manometricos. P2 = 0 kPa manometricos.'
)
d = detectar_atmosfera_y_conflictos(texto, {'P1_kpa': 85.0, 'P2_kpa': 0.0})
ok('P1_ATMOSFERA_CONTRADICCION' not in codigos(d), f'Falso positivo en P1: {d}')
ok('P2_ATMOSFERA' in codigos(d), f'No reconocio P2 abierto: {d}')
ok(not hay_bloqueantes(d), f'El caso correcto no debe bloquear: {d}')
print('  OK')

print('[2/5] Contradiccion real en P2 sigue bloqueandose...')
d = detectar_atmosfera_y_conflictos(
    'El segundo deposito esta abierto a la atmosfera y P2 = 35 kPa manometricos.',
    {'P2_kpa': 35.0},
)
ok('P2_ATMOSFERA_CONTRADICCION' in codigos(d), f'No detecto contradiccion P2: {d}')
ok(hay_bloqueantes(d), 'Una contradiccion real P2 debe bloquear.')
print('  OK')

print('[3/5] Contradiccion real en P1 sigue bloqueandose...')
d = detectar_atmosfera_y_conflictos(
    'El deposito 1 esta abierto a la atmosfera. P1 = 85 kPa manometricos.',
    {'P1_kpa': 85.0},
)
ok('P1_ATMOSFERA_CONTRADICCION' in codigos(d), f'No detecto contradiccion P1: {d}')
ok(hay_bloqueantes(d), 'Una contradiccion real P1 debe bloquear.')
print('  OK')

print('[4/5] Ambos depositos abiertos se asignan correctamente...')
d = detectar_atmosfera_y_conflictos(
    'El deposito 1 esta abierto a la atmosfera y el deposito 2 tambien esta abierto a la atmosfera. P1=0 kPa y P2=0 kPa.',
    {'P1_kpa': 0.0, 'P2_kpa': 0.0},
)
c = codigos(d)
ok('P1_ATMOSFERA' in c and 'P2_ATMOSFERA' in c, f'No detecto ambos extremos: {d}')
ok(not hay_bloqueantes(d), 'Ambos abiertos con P=0 no deben bloquear.')
print('  OK')

print('[5/5] Forma inversa: abierto a la atmosfera -> deposito 2...')
d = detectar_atmosfera_y_conflictos(
    'Abierto a la atmosfera se encuentra el deposito 2; el deposito 1 esta presurizado a 85 kPa.',
    {'P1_kpa': 85.0, 'P2_kpa': 0.0},
)
c = codigos(d)
ok('P2_ATMOSFERA' in c, f'No detecto P2 en forma inversa: {d}')
ok('P1_ATMOSFERA_CONTRADICCION' not in c, f'Falso positivo P1 en forma inversa: {d}')
print('  OK')

print('\nTODAS LAS PRUEBAS V14.2.1 DE COHERENCIA DE EXTREMOS PASARON.')
