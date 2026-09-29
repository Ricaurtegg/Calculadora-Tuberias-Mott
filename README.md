# Calculadora de Sistemas de Tuberías en Serie — Mott V15.0 FINAL

Aplicación académica desarrollada en Python + Streamlit para Mecánica de Fluidos II, basada principalmente en los métodos de Mott.

## Capacidades
- Clasificación de problemas: Clase I, II-A, II-B, II-C, III-A y III-B.
- Cálculo de velocidad, Reynolds, régimen, factor de fricción, pérdidas mayores y menores.
- Métodos de Mott, Darcy-Weisbach y Colebrook.
- Interpretación de texto, TXT, DOCX, PDF seleccionable e imágenes/PDF escaneados con OCR.
- Normalización de unidades SI/US.
- Accesorios, transiciones, materiales, bombas y turbinas.
- Auditoría matemática y física.
- Esquema hidráulico, LE/EGL, LAM/HGL y pérdidas acumuladas.
- Procedimiento Mott paso a paso.
- Reporte técnico en Word/PDF.
- Comparador de escenarios.
- Banco maestro de regresión y ejemplos patrón de Mott.

## Estructura principal
```text
app.py
requirements.txt
packages.txt
calculos/
  __init__.py
  hidraulica.py
EJEMPLOS_MOTT_V15/
  01_Mott_11_1_Clase_I.txt
  02_Mott_11_2_Clase_II_A.txt
  03_Mott_11_3_Clase_II_B.txt
  04_Mott_11_4_Clase_II_C.txt
  05_Mott_11_5_Clase_III_A.txt
  06_Mott_11_6_Clase_III_B.txt
```

## Ejecutar localmente
```bash
pip install -r requirements.txt
streamlit run app.py
```

Para OCR local también debe estar instalado el ejecutable Tesseract. En Streamlit Community Cloud, `packages.txt` instala Tesseract automáticamente.

## Validación oficial V15
```bash
python pruebas_v15_final.py
python pruebas_mott_cap11.py
python pruebas_v14_17.py
```

Resultados de referencia de cierre:
- Casos patrón V15: 6/6.
- Casos dorados Mott capítulo 11: 6/6.
- Banco maestro V14.17: 50/50.

## Despliegue en Streamlit Community Cloud
1. Conectar la cuenta de GitHub a Streamlit Community Cloud.
2. Seleccionar el repositorio `Ricaurtegg/Calculadora-Tuberias-Mott`.
3. Rama: `main`.
4. Archivo principal: `app.py`.
5. Desplegar la aplicación.

Las dependencias Python están declaradas en `requirements.txt` y las dependencias Linux del OCR en `packages.txt`.
