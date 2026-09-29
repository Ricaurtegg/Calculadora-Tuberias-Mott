# Banco maestro de regresión — V14.17

**Estado:** OK · **OK:** 50/50 · **Fallos:** 0

| ID | Categoría | Estado | Caso |
|---|---|---|---|
| M-I_11_1 | Mott dorado | OK | Mott 7e — Ejemplo 11.1 — Clase I |
| M-IIA_11_2 | Mott dorado | OK | Mott 7e — Ejemplo 11.2 — Clase II-A |
| M-IIB_11_3 | Mott dorado | OK | Mott 7e — Ejemplo 11.3 — Clase II-B |
| M-IIC_11_4 | Mott dorado | OK | Mott 7e — Ejemplo 11.4 — Clase II-C |
| M-IIIA_11_5 | Mott dorado | OK | Mott 7e — Ejemplo 11.5 — Clase III-A |
| M-IIIB_11_6 | Mott dorado | OK | Mott 7e — Ejemplo 11.6 — Clase III-B |
| C-I-01 | Clasificación | OK | Dado Q=0.010 m3/s, L=50 m y D=80 mm, determine P2. |
| C-I-02 | Clasificación | OK | Por una tubería circulan 18 L/s. Determine la carga de la bomba hA. |
| C-IIA-01 | Clasificación | OK | Determine el caudal Q entre dos depósitos abiertos unidos por una tubería de 100 m y 100 mm. Desprecie pérdidas menores. |
| C-IIA-02 | Clasificación | OK | Calcule Q en una tubería recta de 250 ft NPS 4 Schedule 40. Desprecie las pérdidas menores. |
| C-IIB-01 | Clasificación | OK | Determine el caudal Q en una tubería de 120 m y 100 mm con dos codos y una válvula; considere las pérdidas menores relativamente pequeñas como corrección. |
| C-IIB-02 | Clasificación | OK | Halle el caudal Q si la línea tiene L=90 m, D=75 mm y K=3.2; trate las pérdidas menores como una pequeña corrección. |
| C-IIC-01 | Clasificación | OK | Dos depósitos están conectados por dos tramos en serie de 100 mm y 75 mm con una contracción súbita y una válvula. Determine Q. |
| C-IIC-02 | Clasificación | OK | Determine el caudal entre dos depósitos a través de tres tuberías en serie de distintos diámetros, con codos, válvula y cambio de sección. |
| C-IIIA-01 | Clasificación | OK | Para Q=0.010 m3/s determine el diámetro mínimo D de una tubería de 50 m si hL permitida es 3 m. |
| C-IIIA-02 | Clasificación | OK | Determine el diámetro requerido de una tubería para transportar 850 gpm con una pérdida de carga máxima especificada. |
| C-IIIB-01 | Clasificación | OK | Se seleccionó una tubería comercial de D=80 mm para Q=0.010 m3/s. Verifique la presión P2 disponible. |
| C-IIIB-02 | Clasificación | OK | Verifique si la tubería comercial NPS 4 Schedule 40 con caudal conocido cumple la presión mínima de 100 psig en la salida. |
| C-MOTT112 | Clasificación | OK | Aceite lubricante en tubería horizontal DN 150 cédula 40 con caída de presión máxima de 60 kPa por cada 100 m. Determine la rapidez del flujo volumétrico máximo permisible. |
| C-MOTT113 | Clasificación | OK | Aceite lubricante en línea horizontal DN 150 Schedule 40 de 30 m + 40 m + 30 m, dos codos estándar y válvula mariposa totalmente abierta. Determine la rapidez del flujo volumétrico máxima permisible. |
| C-SPRINKLER | Clasificación | OK | Determine el tamaño más pequeño permisible de tubería estándar Calibre 40 para alimentar 0.50 pies^3/s de agua a 60 °F con presión mínima requerida en B. |
| P-01 | Parser/unidades | OK | Q=850 gpm |
| P-02 | Parser/unidades | OK | Q=1.5 ft3/s |
| P-03 | Parser/unidades | OK | P1=35 psig |
| P-04 | Parser/unidades | OK | z1=120 ft |
| P-05 | Parser/unidades | OK | Tramo 1: tubería NPS 4 Schedule 40, L=100 m |
| P-06 | Parser/unidades | OK | Tramo 1: DN100 cédula 80, L=100 m |
| P-07 | Parser/unidades | OK | Agua a 68 °F |
| P-08 | Parser/unidades | OK | nu = 1.30 cSt y rho = 998 kg/m3 |
| P-09 | Parser/unidades | OK | gravedad específica de 0.88 y viscosidad dinámica de 9.5 x 10^-3 Pa.s |
| P-10 | Parser/unidades | OK | presión en el punto B debe ser de al menos 60 lb/pulg^2 relativas |
| P-11 | Parser/unidades | OK | Q = 0.50 pies^3/s |
| P-12 | Parser/unidades | OK | La tubería tiene 600 pies de longitud y el punto B está 25 pies por encima de A. |
| P-13 | Parser/unidades | OK | Aceite lubricante con gravedad específica de 0.88 y viscosidad dinámica de 9.5 x 10° Pa.s |
| A-01 | Accesorios/transiciones | OK | En el tramo 2 hay dos codos de 90 grados de radio largo. |
| A-02 | Accesorios/transiciones | OK | El tramo 1 contiene una válvula de compuerta abierta al 50 %. |
| A-03 | Accesorios/transiciones | OK | Hay una válvula de compuerta 75 % abierta en el tramo 1. |
| A-04 | Accesorios/transiciones | OK | Existe una válvula mariposa completamente abierta en el tramo 2. |
| A-05 | Accesorios/transiciones | OK | Existe una válvula mariposa en el tramo 1. |
| A-06 | Accesorios/transiciones | OK | En el tramo 2 existe una tee con flujo por el ramal. |
| T-01 | Accesorios/transiciones | OK | Tramo 1 D=100 mm. Tramo 2 D=75 mm. Entre ambos hay una reducción súbita. |
| T-02 | Accesorios/transiciones | OK | Tramo 1 D=75 mm. Tramo 2 D=100 mm. La unión es una expansión cónica gradual de 20 grados. |
| F-I | Flujo end-to-end | OK | Determine P2 |
| F-IIA | Flujo end-to-end | OK | Determine Q |
| F-IIB | Flujo end-to-end | OK | Determine Q con pérdidas menores |
| F-IIC | Flujo end-to-end | OK | Determine Q en dos tramos |
| F-IIIA | Flujo end-to-end | OK | Determine D mínimo |
| F-IIIB | Flujo end-to-end | OK | Verifique D y P2 |
| G-01 | Guardrail | OK | NPS sin Schedule no inventa diámetro |
| G-02 | Guardrail | OK | Atmósfera + P2 no nula genera conflicto |