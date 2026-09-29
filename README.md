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
- Banco de pruebas con ejemplos de Mott.

## Ejecutar localmente
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Ejemplos
La carpeta `EJEMPLOS_MOTT_V15` contiene seis problemas patrón de Mott, uno por cada clase/subclase principal soportada.
