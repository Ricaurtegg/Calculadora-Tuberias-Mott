"""Pruebas de interfaz V12 (no modifican ni recalculan el motor hidráulico)."""
from pathlib import Path
import ast

BASE = Path(__file__).resolve().parent
APP = BASE / "app.py"


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)


src = APP.read_text(encoding="utf-8")

print("[1/6] Sintaxis de app.py...")
ast.parse(src)
print("  OK")

print("[2/6] Ruta visual de 6 pasos...")
for texto in (
    "1. Problema",
    "2. Datos interpretados",
    "3. Sistema",
    "4. Método",
    "5. Resultados",
    "6. Verificación",
):
    ok(texto in src, f"Falta la etapa: {texto}")
print("  OK")

print("[3/6] Configuración de unidades en barra lateral...")
ok("with st.sidebar:" in src, "La configuración no está en la barra lateral")
ok('key="sistema_unidades"' in src, "Se perdió el selector de unidades")
print("  OK")

print("[4/6] Identificación compacta después de elegir clase...")
ok("if st.session_state.clase_activa is None:" in src, "La identificación no se oculta al continuar")
ok('with st.expander("📄 1–2. Problema y datos interpretados", expanded=False):' in src,
   "Falta el resumen compacto del problema")
print("  OK")

print("[5/6] Detalles extensos dentro de expandibles...")
for texto in (
    '"🧮 Cálculos por tramo"',
    '"🛠️ Configurar geometría y posición de equipos"',
    '"🧩 Esquema hidráulico del sistema"',
    '"📈 LE / EGL y LAM / HGL"',
):
    ok(texto in src, f"Falta el bloque compacto: {texto}")
print("  OK")

print("[6/6] Funciones hidráulicas principales siguen conectadas...")
for texto in (
    "resolver_clase_i(",
    "resolver_clase_ii_mott_v9(",
    "resolver_clase_iii_a_mott_v9(",
    "verificar_clase_iii_b(",
):
    ok(texto in src, f"Se perdió una llamada principal: {texto}")
print("  OK")

print("\nTodas las pruebas V12 de interfaz pasaron correctamente.")
