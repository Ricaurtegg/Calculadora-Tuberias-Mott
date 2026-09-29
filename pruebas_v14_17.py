from pathlib import Path
import json

from banco_regresion_v1417 import VERSION_BANCO, ejecutar_banco_maestro, catalogo_casos

BASE=Path(__file__).resolve().parent
APP=(BASE/'app.py').read_text(encoding='utf-8')

def ok(c,msg):
    if not c: raise AssertionError(msg)

print('[1/8] V14.17 expone un banco permanente de 50 casos...')
cat=catalogo_casos(); ok(VERSION_BANCO=='V14.17',VERSION_BANCO); ok(len(cat)==50,len(cat)); print('  OK')

print('[2/8] Cobertura por categorías clave...')
cats={x['categoria'] for x in cat}
for c in {'Mott dorado','Clasificación','Parser/unidades','Accesorios/transiciones','Flujo end-to-end','Guardrail'}: ok(c in cats,c)
print('  OK')

print('[3/8] Banco maestro completo...')
r=ejecutar_banco_maestro(verbose=False)
ok(r['total']==50,r['total']); ok(r['ok']==50, json.dumps([x for x in r['resultados'] if x['estado']!='OK'],ensure_ascii=False,indent=2)); print(f"  OK: {r['ok']}/{r['total']}")

print('[4/8] Los seis casos Mott siguen presentes...')
ok(r['por_categoria']['Mott dorado']['ok']==6,r['por_categoria']); print('  OK')

print('[5/8] Las seis clases tienen cobertura end-to-end...')
ok(r['por_categoria']['Flujo end-to-end']['ok']==6,r['por_categoria']); print('  OK')

print('[6/8] Guardrails conservadores pasan...')
ok(r['por_categoria']['Guardrail']['ok']==2,r['por_categoria']); print('  OK')

print('[7/8] V14.17 integrado en Streamlit como modo prueba de profesor...')
for tok in ('banco_regresion_v1417','V14.17 — Banco maestro','EJECUTAR BANCO MAESTRO','Modo prueba de profesor'):
    ok(tok in APP,f'Falta {tok}')
print('  OK')

print('[8/8] Reportes de regresión descargables conectados...')
for tok in ('reporte_json_v1417','reporte_csv_v1417','reporte_markdown_v1417'):
    ok(tok in APP,f'Falta {tok}')
print('  OK')

print('\nTODAS LAS PRUEBAS V14.17 DEL BANCO MAESTRO PASARON.')
