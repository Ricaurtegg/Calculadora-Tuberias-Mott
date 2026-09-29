from pathlib import Path
import io
import zipfile

from pypdf import PdfReader

from transferencia_v147 import construir_previsualizacion_transferencia
from reporte_final_v149 import construir_manifiesto_ejecucion, construir_reporte_final
from flujo_automatico_v1410 import resolver_flujo_confirmado
from reporte_tecnico_v2_v1418 import VERSION_REPORTE_V2, reporte_docx_v2, reporte_pdf_v2

BASE = Path(__file__).resolve().parent
APP = (BASE / 'app.py').read_text(encoding='utf-8')
REQ = (BASE / 'requirements.txt').read_text(encoding='utf-8')


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)


def caso_iic():
    return {
        'clase': 'Clase II-C', 'confianza': 96,
        'prefill': {
            'fluido_app': 'Agua a 20 °C', 'fluido_detectado': 'Agua a 20 °C',
            'P1_kpa': 135.0, 'P2_kpa': 0.0, 'z1_m': 31.2, 'z2_m': 8.4,
            'hA_m': 0.0, 'hR_m': 0.0, 'v1_tipo': 'deposito', 'v2_tipo': 'deposito',
            'tramos': [
                {'numero': 1, 'L_m': 68.5, 'D_m': 0.100, 'material': 'Acero comercial o soldado',
                 'accesorios': [
                     {'nombre': 'Entrada — borde cuadrado/agudo', 'cantidad': 1, 'posicion_fraccion': 0.05},
                     {'nombre': 'Codo 90° estándar', 'cantidad': 2, 'posiciones_fraccion': [0.45, 0.80]},
                 ], 'componentes_graficos': []},
                {'numero': 2, 'L_m': 96.3, 'D_m': 0.075, 'material': 'Plástico',
                 'accesorios': [
                     {'nombre': 'Válvula de compuerta — totalmente abierta', 'cantidad': 1, 'posicion_fraccion': 0.32},
                     {'nombre': 'Salida hacia depósito grande', 'cantidad': 1, 'posicion_fraccion': 0.98},
                 ], 'componentes_graficos': []},
            ],
            'transiciones': [{'entre': 1, 'tipo': 'Contracción súbita', 'angulo_grados': None}],
        },
    }


def preparar():
    en = 'Determine el caudal Q del sistema e incluya todas las pérdidas mayores y menores.'
    r = caso_iic()
    p = construir_previsualizacion_transferencia(r, en)
    ok(p['listo_para_transferir'], p)
    m = construir_manifiesto_ejecucion(r, en, p)
    f = resolver_flujo_confirmado(r, en, p, p['firma'], m)
    rep = construir_reporte_final(m, f['resultado_solver'], f['auditoria'], f.get('auditoria_fisica_v1416'))
    return f, rep


print('[1/12] Versión V14.18 activa...')
ok(VERSION_REPORTE_V2 == 'V14.18', VERSION_REPORTE_V2)
print('  OK')

f, rep = preparar()
ctx = f.get('contexto_diagramas_v1415') or {}

print('[2/12] V14.18 usa el mismo resultado trazable V14.9...')
ok(abs(rep['resultado']['Q_m3s'] - f['resultado_solver']['Q_final']) < 1e-12, rep['resultado'])
ok(rep['estado_matematico'] == f['auditoria']['estado'], rep)
print('  OK')

print('[3/12] Word V2 se genera como DOCX válido...')
docx = reporte_docx_v2(rep, ctx)
ok(docx[:2] == b'PK', docx[:8])
print('  OK')

print('[4/12] Word V2 incrusta las tres figuras V14.15...')
with zipfile.ZipFile(io.BytesIO(docx)) as z:
    medias = [n for n in z.namelist() if n.startswith('word/media/')]
    xml = z.read('word/document.xml').decode('utf-8', errors='ignore')
ok(len(medias) >= 3, medias)
for token in ('Resumen técnico', 'Ecuaciones y método de solución', 'Diagramas hidráulicos', 'Auditoría matemática V14.8.3', 'Auditoría física V14.16', 'Nomenclatura'):
    ok(token in xml, token)
print('  OK')

print('[5/12] PDF V2 se genera y es legible por pypdf...')
pdf = reporte_pdf_v2(rep, ctx)
ok(pdf.startswith(b'%PDF'), pdf[:10])
reader = PdfReader(io.BytesIO(pdf))
ok(len(reader.pages) >= 4, len(reader.pages))
print('  OK')

print('[6/12] PDF contiene resultado, método y auditorías...')
texto_pdf = '\n'.join((p.extract_text() or '') for p in reader.pages)
for token in ('REPORTE TÉCNICO', 'Resultados', 'Diagramas hidráulicos', 'Auditoría matemática', 'Auditoría física', 'Trazabilidad'):
    ok(token in texto_pdf, token)
print('  OK')

print('[7/12] El reporte puede generarse sin contexto gráfico sin inventar figuras...')
docx_sin = reporte_docx_v2(rep, None)
with zipfile.ZipFile(io.BytesIO(docx_sin)) as z:
    xml2 = z.read('word/document.xml').decode('utf-8', errors='ignore')
ok('No se dispuso del contexto V14.15' in xml2, 'No documentó ausencia de figuras')
print('  OK')

print('[8/12] Conserva auditoría matemática y física originales...')
ok(rep.get('auditoria_v148',{}).get('estado') == 'OK', rep.get('auditoria_v148'))
ok(rep.get('auditoria_fisica_v1416',{}).get('estado') in ('OK','REVISAR'), rep.get('auditoria_fisica_v1416'))
print('  OK')

print('[9/12] Conserva firma de trazabilidad V14.7...')
ok(rep.get('firma_transferencia_v147') == f['manifiesto_v149'].get('firma_transferencia_v147'), (rep.get('firma_transferencia_v147'), f['manifiesto_v149'].get('firma_transferencia_v147')))
print('  OK')

print('[10/12] app.py ofrece Word y PDF V14.18 y recibe contexto V14.15...')
for token in ('V14.18 — Reporte técnico V2', 'reporte_docx_v1418', 'reporte_pdf_v1418', 'flujo.get("contexto_diagramas_v1415")'):
    ok(token in APP, f'Falta integración: {token}')
print('  OK')

print('[11/12] V14.9 permanece disponible como base trazable...')
for token in ('Reporte Markdown', 'Reporte JSON', 'Reporte Word', 'construir_reporte_final'):
    ok(token in APP, f'V14.9 perdido: {token}')
print('  OK')

print('[12/12] requirements incluye reportlab para PDF V14.18...')
ok('reportlab' in REQ.lower(), REQ)
print('  OK')

print('\nTODAS LAS PRUEBAS V14.18 DE REPORTE TÉCNICO V2 PASARON.')
