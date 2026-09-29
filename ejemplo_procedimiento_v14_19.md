# Procedimiento Mott - Clase II-C

**Versión:** V14.19
**Método:** Solver iterativo completo II-C

## 1. Datos y clasificación
El expediente confirmado V14.7 clasifica el problema como Clase II-C. Se usan únicamente datos confirmados y propiedades efectivas del solver.

**Sustitución:** ρ=998 kg/m³; ν=1.02000e-06 m²/s; γ=9790.38 N/m³; P1=135 kPa; P2=0 kPa; z1=31.2 m; z2=8.4 m.

**Resultado:** Método seleccionado: Solver iterativo completo II-C.

## 2. Ecuación general de energía y carga disponible
Se establece el balance entre los puntos 1 y 2 antes de introducir las pérdidas del sistema.

**Ecuación:** `P1/γ + z1 + V1²/(2g) + hA - hR - hL = P2/γ + z2 + V2²/(2g)`

**Sustitución:** H1=135000/9790.38+31.2+0=44.98905 m; H2=0/9790.38+8.4+0=8.4 m; carga neta=H1+hA-hR-H2=36.58905 m.

**Resultado:** Carga neta disponible = 36.58905 m.

## 3. Estimación inicial y solución iterativa
Se parte de la estimación II-A cuando está disponible y se corrige hasta cerrar la ecuación de energía con las pérdidas correspondientes a la clase.

**Ecuación:** `R(Q)=P1/γ+z1+V1²/(2g)+hA-hR-hL(Q)-P2/γ-z2-V2²/(2g) → 0`

**Sustitución:** Q inicial II-A=0.02562437 m³/s; iteraciones internas reportadas=66; registros conservados en historial=28.

**Resultado:** Q final=0.02460353 m³/s; residual=-2.85514e-11 m; convergencia=True.

## 4. Cálculo hidráulico del tramo 1
Tramo 1: se evalúan geometría, velocidad, Reynolds, fricción de Darcy y pérdidas con los valores realmente usados por el solver.

**Ecuación:** `A=πD²/4; V=Q/A; Re=VD/ν; hf=f(L/D)(V²/2g); hm=K(V²/2g)`

**Sustitución:** A=π(0.1)²/4=0.007853982 m²; V=0.02460353/0.007853982=3.132619 m/s; Re=(3.132619)(0.1)/1.02000e-06=307119.5; ε/D=4.60000e-05/0.1=0.00046; f=0.01794908; V²/(2g)=0.5001683 m; hf=(0.01794908)(68.5/0.1)(0.5001683)=6.14963 m; hm=(1.46)(0.5001683)=0.7302458 m.

**Resultado:** Tramo 1: hf=6.14963 m; hm=0.7302458 m; régimen=Turbulento.

## 5. Cálculo hidráulico del tramo 2
Tramo 2: se evalúan geometría, velocidad, Reynolds, fricción de Darcy y pérdidas con los valores realmente usados por el solver.

**Ecuación:** `A=πD²/4; V=Q/A; Re=VD/ν; hf=f(L/D)(V²/2g); hm=K(V²/2g)`

**Sustitución:** A=π(0.075)²/4=0.004417865 m²; V=0.02460353/0.004417865=5.569101 m/s; Re=(5.569101)(0.075)/1.02000e-06=409492.7; ε/D=3.00000e-07/0.075=4.00000e-06; f=0.01369842; V²/(2g)=1.580779 m; hf=(0.01369842)(96.3/0.075)(1.580779)=27.80397 m; hm=(1.056188)(1.580779)=1.6696 m.

**Resultado:** Tramo 2: hf=27.80397 m; hm=1.6696 m; régimen=Turbulento.

## 6. Suma de pérdidas y comprobación
Se suman pérdidas distribuidas, accesorios y transiciones usando exactamente los totales del solver.

**Ecuación:** `hL,total = Σhf + Σhm,accesorios + Σhm,transiciones`

**Sustitución:** Σhf=33.9536 m; Σhm,acc=2.399845 m; Σhm,trans=0.2356032 m.

**Resultado:** hL,total=36.58905 m; residual=-2.85514e-11 m.

## 7. Respuesta final y verificación
El valor reportado es exactamente el producido por el solver; V14.19 no vuelve a resolver ni redondea internamente el problema.

**Sustitución:** Auditoría matemática=OK.

**Resultado:** Q = 0.02460353 m³/s

## Historial de iteración

| Iter. | Q (m³/s) | hL (m) | Residual (m) | Re mín | Re máx | f mín | f máx |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.01921828 | 23.1834 | 13.40565 | 239896.8 | 319862.4 | 0.01433325 | 0.01830704 |
| 2 | 0.02242132 | 30.81475 | 5.774297 | 279879.6 | 373172.8 | 0.01393194 | 0.01807632 |
| 3 | 0.02402285 | 35.00736 | 1.581685 | 299871 | 399828 | 0.0137579 | 0.01798099 |
| 4 | 0.02482361 | 37.19702 | -0.6079696 | 309866.7 | 413155.6 | 0.01367635 | 0.01793733 |
| 5 | 0.02442323 | 36.09443 | 0.4946136 | 304868.8 | 406491.8 | 0.0137167 | 0.01795885 |
| 6 | 0.02462342 | 36.64379 | -0.05474072 | 307367.7 | 409823.7 | 0.01369642 | 0.01794801 |
| 7 | 0.02452332 | 36.36863 | 0.220421 | 306118.3 | 408157.7 | 0.01370653 | 0.01795341 |
| 8 | 0.02457337 | 36.50608 | 0.08296123 | 306743 | 408990.7 | 0.01370147 | 0.01795071 |
| 9 | 0.02459839 | 36.57491 | 0.01414053 | 307055.4 | 409407.2 | 0.01369894 | 0.01794936 |
| 10 | 0.02461091 | 36.60934 | -0.02029252 | 307211.6 | 409615.4 | 0.01369768 | 0.01794868 |
| 11 | 0.02460465 | 36.59212 | -0.003074104 | 307133.5 | 409511.3 | 0.01369831 | 0.01794902 |
| 12 | 0.02460152 | 36.58351 | 0.005533687 | 307094.4 | 409459.2 | 0.01369863 | 0.01794919 |
| 13 | 0.02460309 | 36.58782 | 0.00122991 | 307113.9 | 409485.3 | 0.01369847 | 0.0179491 |
| 14 | 0.02460387 | 36.58997 | -0.0009220677 | 307123.7 | 409498.3 | 0.01369839 | 0.01794906 |
| 15 | 0.02460348 | 36.58889 | 0.0001539283 | 307118.8 | 409491.8 | 0.01369843 | 0.01794908 |
| 16 | 0.02460367 | 36.58943 | -0.0003840678 | 307121.3 | 409495 | 0.01369841 | 0.01794907 |
| 17 | 0.02460358 | 36.58916 | -0.0001150693 | 307120 | 409493.4 | 0.01369842 | 0.01794908 |
| 18 | 0.02460353 | 36.58903 | 1.94296e-05 | 307119.4 | 409492.6 | 0.01369842 | 0.01794908 |
| 19 | 0.02460355 | 36.58909 | -4.78198e-05 | 307119.7 | 409493 | 0.01369842 | 0.01794908 |
| 20 | 0.02460354 | 36.58906 | -1.41951e-05 | 307119.6 | 409492.8 | 0.01369842 | 0.01794908 |
| 21 | 0.02460353 | 36.58904 | 2.61728e-06 | 307119.5 | 409492.7 | 0.01369842 | 0.01794908 |
| 22 | 0.02460354 | 36.58905 | -5.78890e-06 | 307119.6 | 409492.7 | 0.01369842 | 0.01794908 |
| 23 | 0.02460353 | 36.58905 | -1.58581e-06 | 307119.5 | 409492.7 | 0.01369842 | 0.01794908 |
| 24 | 0.02460353 | 36.58905 | 5.15737e-07 | 307119.5 | 409492.7 | 0.01369842 | 0.01794908 |
| 25 | 0.02460353 | 36.58905 | -5.35035e-07 | 307119.5 | 409492.7 | 0.01369842 | 0.01794908 |
| 26 | 0.02460353 | 36.58905 | -9.64866e-09 | 307119.5 | 409492.7 | 0.01369842 | 0.01794908 |
| 27 | 0.02460353 | 36.58905 | 2.53044e-07 | 307119.5 | 409492.7 | 0.01369842 | 0.01794908 |
| 28 | 0.02460353 | 36.58905 | 1.21698e-07 | 307119.5 | 409492.7 | 0.01369842 | 0.01794908 |

## Respuesta final

**Q = 0.02460353 m³/s**

Trazabilidad: Construido a partir del snapshot V14.7 y del resultado final del solver; no recalcula el problema.