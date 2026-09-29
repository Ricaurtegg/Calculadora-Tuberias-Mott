# Comparador de escenarios hidráulicos — V14.20

- Clase: **Clase II-C**
- Escenarios alternativos: **4**
- Firma base: `40f62b06ee36`

| Escenario | Estado | Resultado | Δ resultado | Q (m³/s) | hL (m) | V máx (m/s) |
|---|---|---:|---:|---:|---:|---:|
| Base | OK | 0.0246035 m³/s | 0 % | 0.0246035 | 36.589 | 5.5691 |
| D1 = 110 mm | OK | 0.0255669 m³/s | 3.9154 % | 0.0255669 | 36.589 | 5.78716 |
| Tramo 1 plástico | OK | 0.0251659 m³/s | 2.2858 % | 0.0251659 | 36.589 | 5.6964 |
| Válvula de globo | OK | 0.0233683 m³/s | -5.0204 % | 0.0233683 | 36.589 | 5.28951 |
| Bomba +5 m | OK | 0.026366 m³/s | 7.1635 % | 0.026366 | 41.589 | 5.96805 |

## Cambios por escenario

### D1 = 110 mm
- `D_m` · tramo 1: `0.1` → `0.11`

### Tramo 1 plástico
- `material` · tramo 1: `Acero comercial o soldado` → `Plástico`

### Válvula de globo
- `accesorio_reemplazar` · tramo 2: `{'nombre': 'Válvula de compuerta — totalmente abierta', 'cantidad': 1}` → `Válvula de globo — totalmente abierta`

### Bomba +5 m
- `hA_m`: `0.0` → `5.0`

> V14.20 compara variantes explícitas. No modifica el escenario base ni cambia silenciosamente la clase hidráulica.