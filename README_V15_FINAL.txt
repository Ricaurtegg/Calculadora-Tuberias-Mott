CALCULADORA DE SISTEMAS DE TUBERÍAS EN SERIE — MOTT 7a EDICIÓN
V15.0 FINAL

OBJETIVO
Versión consolidada para resolver y auditar problemas de sistemas de tuberías en serie con el esquema de clases usado en el proyecto:
- Clase I
- Clase II-A
- Clase II-B
- Clase II-C
- Clase III-A
- Clase III-B

INCLUYE
- Identificación automática / asistida / clase conocida.
- TXT, DOCX, PDF seleccionable, imágenes y PDF escaneado con OCR.
- Propiedades explícitas rho, SG, mu y nu.
- Unidades SI/US y NPS/DN/Schedule.
- Accesorios y transiciones Mott.
- Flujo automático supervisado V14.10.
- Confianza por dato V14.11.
- Auditoría matemática V14.8.3 y física V14.16.
- Visión geométrica V14.14.
- Diagramas/LE-LAM/pérdidas V14.15.
- Banco maestro V14.17.
- Reporte técnico Word/PDF V14.18.
- Procedimiento Mott V14.19.
- Comparador de escenarios V14.20.

VALIDACIÓN OFICIAL V15
La carpeta EJEMPLOS_MOTT_V15 contiene seis archivos TXT, uno por cada clase/subclase exigida. Están escritos con todos los datos necesarios para que el flujo automático no tenga que preguntar información adicional.

Ejecutar:
  python pruebas_v15_final.py
  python pruebas_mott_cap11.py
  python pruebas_v14_17.py
  streamlit run app.py

NOTA SOBRE OCR
El OCR ayuda a recuperar texto de fotografías/PDF escaneados, pero exponentes, superíndices y datos dibujados dentro de diagramas pueden requerir revisión humana. Para una comprobación objetiva del motor use los seis TXT patrón incluidos.

V15.0 FINAL no inventa datos ausentes: si una imagen no permite recuperar una magnitud con seguridad, solicita confirmación.
