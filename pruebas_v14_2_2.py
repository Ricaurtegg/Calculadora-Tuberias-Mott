from vfisicas import detectar_atmosfera_y_conflictos, hay_bloqueantes


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)


def codigos(diags):
    return {d.get('codigo') for d in diags}

print('[1/6] OCR perfecto: deposito 1 presurizado -> deposito 2 abierto...')
t = ('Agua a 20 C fluye desde un deposito 1 presurizado hasta un deposito 2 abierto '
     'a la atmosfera. P1=85 kPa manometricos. P2=0 kPa manometricos.')
d = detectar_atmosfera_y_conflictos(t, {'P1_kpa':85.0,'P2_kpa':0.0})
ok('P1_ATMOSFERA_CONTRADICCION' not in codigos(d), f'Falso P1: {d}')
ok('P2_ATMOSFERA' in codigos(d), f'Falta P2: {d}')
print('  OK')

print('[2/6] OCR pierde el numero 2 del segundo deposito...')
t = ('Agua a 20 C fluye desde un deposito 1 presurizado hasta un deposito abierto '
     'a la atmosfera. P1=85 kPa manometricos. P2=0 kPa manometricos.')
d = detectar_atmosfera_y_conflictos(t, {'P1_kpa':85.0,'P2_kpa':0.0})
c = codigos(d)
ok('P1_ATMOSFERA_CONTRADICCION' not in c, f'Falso P1 con OCR degradado: {d}')
ok('P2_ATMOSFERA' in c, f'No infirio P2 con OCR degradado: {d}')
ok(not hay_bloqueantes(d), f'Caso valido no debe bloquear: {d}')
print('  OK')

print('[3/6] Intervencion de un segundo deposito generico corta asociacion con P1...')
t = ('El deposito 1 esta presurizado. El flujo va hasta un deposito abierto a la atmosfera. '
     'P1=85 kPa. P2=0 kPa.')
d = detectar_atmosfera_y_conflictos(t, {'P1_kpa':85.0,'P2_kpa':0.0})
ok('P1_ATMOSFERA_CONTRADICCION' not in codigos(d), f'Falso salto hacia P1: {d}')
print('  OK')

print('[4/6] Contradiccion real P1 se conserva...')
d = detectar_atmosfera_y_conflictos(
    'El deposito 1 esta abierto a la atmosfera. P1=85 kPa manometricos.',
    {'P1_kpa':85.0},
)
ok('P1_ATMOSFERA_CONTRADICCION' in codigos(d), f'No detecto contradiccion real P1: {d}')
ok(hay_bloqueantes(d), 'La contradiccion real P1 debe bloquear')
print('  OK')

print('[5/6] Contradiccion real P2 se conserva...')
d = detectar_atmosfera_y_conflictos(
    'El deposito 2 esta abierto a la atmosfera. P2=35 kPa manometricos.',
    {'P2_kpa':35.0},
)
ok('P2_ATMOSFERA_CONTRADICCION' in codigos(d), f'No detecto contradiccion real P2: {d}')
print('  OK')

print('[6/6] Ambos depositos abiertos con P=0 siguen siendo validos...')
d = detectar_atmosfera_y_conflictos(
    'El deposito 1 esta abierto a la atmosfera y el deposito 2 esta abierto a la atmosfera. P1=0 kPa. P2=0 kPa.',
    {'P1_kpa':0.0,'P2_kpa':0.0},
)
c=codigos(d)
ok('P1_ATMOSFERA' in c and 'P2_ATMOSFERA' in c, f'No reconocio ambos: {d}')
print('  OK')

print('\nTODAS LAS PRUEBAS V14.2.2 PASARON.')
