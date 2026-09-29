"""Pruebas V11: sistema SI / US Customary."""
from unidades import (
    SISTEMA_SI, SISTEMA_US, CAUDAL_US_GPM, CAUDAL_US_FT3S,
    a_interno, desde_interno, unidad,
)


def cerca(a,b,tol=1e-9):
    if abs(a-b)>tol:
        raise AssertionError(f"{a} != {b} (tol={tol})")

print('[1/6] Longitud m ↔ ft...')
cerca(desde_interno(1.0,'longitud',SISTEMA_US), 3.280839895013123, 1e-12)
cerca(a_interno(3.280839895013123,'longitud',SISTEMA_US), 1.0, 1e-12)
print('  OK')

print('[2/6] Diámetro m ↔ in...')
cerca(desde_interno(0.1023,'diametro',SISTEMA_US), 4.0275590551, 1e-9)
cerca(a_interno(desde_interno(0.1023,'diametro',SISTEMA_US),'diametro',SISTEMA_US), 0.1023, 1e-12)
print('  OK')

print('[3/6] Presión kPa ↔ psi...')
cerca(desde_interno(100.0,'presion',SISTEMA_US), 14.503773773, 1e-9)
cerca(a_interno(desde_interno(100.0,'presion',SISTEMA_US),'presion',SISTEMA_US),100.0,1e-10)
print('  OK')

print('[4/6] Caudal m³/s ↔ gal/min y ft³/s...')
q=0.01
gpm=desde_interno(q,'caudal',SISTEMA_US,CAUDAL_US_GPM)
ft3s=desde_interno(q,'caudal',SISTEMA_US,CAUDAL_US_FT3S)
cerca(gpm,158.50323141489,1e-9)
cerca(ft3s,0.3531466672148859,1e-12)
cerca(a_interno(gpm,'caudal',SISTEMA_US,CAUDAL_US_GPM),q,1e-12)
cerca(a_interno(ft3s,'caudal',SISTEMA_US,CAUDAL_US_FT3S),q,1e-12)
print('  OK')

print('[5/6] Temperatura °C ↔ °F...')
cerca(desde_interno(20.0,'temperatura',SISTEMA_US),68.0,1e-12)
cerca(a_interno(68.0,'temperatura',SISTEMA_US),20.0,1e-12)
print('  OK')

print('[6/6] SI es identidad y etiquetas correctas...')
cerca(desde_interno(12.34,'longitud',SISTEMA_SI),12.34,1e-12)
assert unidad('presion',SISTEMA_US)=='psi'
assert unidad('diametro',SISTEMA_US)=='in'
assert unidad('caudal',SISTEMA_US,CAUDAL_US_GPM)=='gal/min'
print('  OK')

print('\nTodas las pruebas V11 de unidades pasaron correctamente.')
