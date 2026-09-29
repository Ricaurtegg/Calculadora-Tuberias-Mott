import streamlit as st
import pandas as pd
import hashlib
import copy
from numbers import Number

from calculos.hidraulica import (
    peso_especifico,
    resolver_clase_i,
    residuo_energia,
    potencia_hidraulica_bomba,
    potencia_entrada_bomba,
    calcular_sistema_para_q,
    carga_disponible_clase_iii_a,
    buscar_diametro_clase_iii_a,
    verificar_clase_iii_b,
)

from clasificar_problema import (
    identificar_clase_automaticamente,
    identificar_clase_guiada,
)

from diagramas import (
    crear_esquema_sistema,
    crear_lineas_energia,
    crear_perdidas_acumuladas_v1415,
    construir_perfil_perdidas_v1415,
    VERSION_DIAGRAMAS_AVANZADOS,
)

from catalogos_mott import (
    MATERIALES,
    MATERIALES_INFO,
    ACCESORIOS,
    FLUIDOS,
    propiedades_agua_interpoladas,
    calcular_k_accesorio,
)

from transiciones_mott import (
    TIPO_SIN,
    TIPO_EXP_SUD,
    TIPO_EXP_GRAD,
    TIPO_CON_SUD,
    TIPO_CON_GRAD,
    calcular_k_curva_tuberia,
    calcular_sistema_con_transiciones,
    resolver_clase_ii_mott_con_transiciones,
)

from metodos_mott import (
    resolver_clase_ii_mott_v9,
    resolver_clase_iii_a_mott_v9,
)

from catalogo_tuberias_mott import (
    CATALOGOS_TUBERIA,
    opciones_nps,
    buscar_tamano_por_nps,
)

from vfisicas import (
    validar_clase_ii_previa,
    validar_clase_iii_a_previa,
    validar_clase_iii_b_previa,
    validar_resultados_hidraulicos,
    detectar_atmosfera_y_conflictos,
    hay_bloqueantes,
)

from auditoria_datos import (
    construir_auditoria_datos,
    hay_conflictos_bloqueantes,
)

from unidades import (
    SISTEMA_SI,
    SISTEMA_US,
    CAUDAL_US_GPM,
    CAUDAL_US_FT3S,
    a_interno,
    desde_interno,
    unidad,
    es_us,
)

from lectura_archivos import (
    extraer_texto_archivo,
    ErrorLecturaArchivo,
    EXTENSIONES_SOPORTADAS,
)

from interpretacion_figuras import (
    interpretar_figura_archivo,
    fusionar_resultado_con_figura,
    ErrorInterpretacionFigura,
)

from vision_esquemas import (
    analizar_geometria_archivo,
    fusionar_figura_con_geometria,
    ErrorVisionEsquema,
)

from consolidacion_datos import (
    consolidar_resultado,
)

from completado_interactivo import (
    VERSION_COMPLETADO,
    ErrorRespuestaFaltante,
    identificador_pregunta,
    aplicar_respuestas_faltantes,
    opciones_transicion_para_pregunta,
)

from transferencia_v147 import (
    VERSION_TRANSFERENCIA,
    construir_previsualizacion_transferencia,
)

from auditoria_solucion_v148 import (
    VERSION_AUDITORIA,
    auditar_sistema_hidraulico,
    auditar_clase_ii_mott,
    auditar_clase_iii_a,
    auditar_clase_iii_b,
    reporte_texto as reporte_texto_v148,
    reporte_json as reporte_json_v148,
)

from auditoria_fisica_v1416 import (
    VERSION_AUDITORIA_FISICA,
    auditar_fisica,
    reporte_texto as reporte_texto_v1416,
    reporte_json as reporte_json_v1416,
)

from reporte_final_v149 import (
    VERSION_REPORTE,
    ErrorReporteV149,
    construir_manifiesto_ejecucion,
    construir_reporte_final,
    verificar_ejecucion_vs_manifiesto,
    reporte_markdown as reporte_markdown_v149,
    reporte_json as reporte_json_v149,
    reporte_docx as reporte_docx_v149,
)

from reporte_tecnico_v2_v1418 import (
    VERSION_REPORTE_V2,
    ErrorReporteV1418,
    reporte_docx_v2 as reporte_docx_v1418,
    reporte_pdf_v2 as reporte_pdf_v1418,
)

from procedimiento_mott_v1419 import (
    VERSION_PROCEDIMIENTO,
    ErrorProcedimientoV1419,
    procedimiento_markdown as procedimiento_markdown_v1419,
    procedimiento_docx as procedimiento_docx_v1419,
)

from comparador_escenarios_v1420 import (
    VERSION_COMPARADOR,
    ErrorComparadorV1420,
    extraer_prefill_base as extraer_prefill_base_v1420,
    firma_base as firma_base_v1420,
    resolver_escenario as resolver_escenario_v1420,
    construir_comparacion as construir_comparacion_v1420,
    filas_para_tabla as filas_para_tabla_v1420,
    reporte_json as reporte_json_v1420,
    reporte_csv as reporte_csv_v1420,
    reporte_markdown as reporte_markdown_v1420,
)

from flujo_automatico_v1410 import (
    VERSION_FLUJO,
    ErrorFlujoV1410,
    construir_estado_flujo,
    resolver_flujo_confirmado,
)

from confianza_datos_v1411 import (
    VERSION_CONFIANZA,
    construir_confianza_datos,
    aplicar_confirmaciones as aplicar_confirmaciones_v1411,
)

from componentes_mott_v1413 import VERSION_COMPONENTES

from banco_regresion_v1417 import (
    VERSION_BANCO,
    ejecutar_banco_maestro,
    reporte_json as reporte_json_v1417,
    reporte_csv as reporte_csv_v1417,
    reporte_markdown as reporte_markdown_v1417,
)


APP_VERSION = "V15.0 FINAL"


# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="Calculadora de Tuberías - Mott",
    page_icon="💧",
    layout="wide",
)


# ============================================================
# ESTADO
# ============================================================

VALORES_INICIALES = {
    "clase_activa": None,
    "resultado_auto": None,
    "resultado_guiado": None,
    "num_tramos": 1,
    "resultado_clase_i_sistema": None,
    "firma_clase_i": None,
    "prefill_mensaje": False,
    "sistema_unidades": SISTEMA_SI,
    "unidad_caudal_us": CAUDAL_US_GPM,
    "_sistema_unidades_prev": SISTEMA_SI,
    "_unidad_caudal_us_prev": CAUDAL_US_GPM,
    "modo_entrada_enunciado": "⌨️ Escribir o pegar",
    "archivo_enunciado_hash": None,
    "archivo_enunciado_info": None,
    "archivo_enunciado_advertencias": [],
    "texto_analizado_auto": None,
    "enunciado_confirmado_auto": "",
    "resultado_figura_v143": None,
    "texto_figura_v143": "",
    "pagina_figura_v143": 1,
    "figura_confirmada_v143": False,
    "resultado_geometria_v144": None,
    "geometria_aplicada_v144": False,
    "transferencia_v147_confirmada": None,
    "manifiesto_v149": None,
    "modo_automatico_v1410": True,
    "resultado_flujo_v1410": None,
    "error_flujo_v1410": None,
    "mostrar_solver_manual_v1410": False,
    "texto_extraido_archivo_v1411": "",
    "ocr_revisado_v1411": False,
    "v1420_firma_base": None,
    "v1420_escenarios": [],
}

for clave, valor in VALORES_INICIALES.items():
    if clave not in st.session_state:
        st.session_state[clave] = valor


# ============================================================
# FUNCIONES AUXILIARES DE INTERFAZ
# ============================================================


def _sistema_ui():
    return st.session_state.get("sistema_unidades", SISTEMA_SI)


def _unidad_caudal_ui():
    return st.session_state.get("unidad_caudal_us", CAUDAL_US_GPM)


def _u(kind):
    return unidad(kind, _sistema_ui(), _unidad_caudal_ui())


def _desde(valor, kind):
    return desde_interno(valor, kind, _sistema_ui(), _unidad_caudal_ui())


def _a_interno(valor, kind):
    return a_interno(valor, kind, _sistema_ui(), _unidad_caudal_ui())


def entrada_dimensionada(
    etiqueta, kind, *, value, key, min_value=None, max_value=None, step=None,
    format="%.4f", help=None, disabled=False
):
    """number_input mostrado en la unidad seleccionada y devuelto en unidad interna."""
    kwargs = {
        "value": _desde(value, kind),
        "key": key,
        "format": format,
        "disabled": disabled,
    }
    if min_value is not None:
        kwargs["min_value"] = _desde(min_value, kind)
    if max_value is not None:
        kwargs["max_value"] = _desde(max_value, kind)
    if step is not None:
        kwargs["step"] = _desde(step, kind)
    if help is not None:
        kwargs["help"] = help
    valor_ui = st.number_input(f"{etiqueta} ({_u(kind)})", **kwargs)
    return _a_interno(valor_ui, kind)


def fmt_u(valor, kind, dec=4):
    v = _desde(valor, kind)
    return f"{v:.{dec}f} {_u(kind)}"


def aplicar_estilo_interfaz():
    """Estilo visual compacto sin alterar la lógica hidráulica."""
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.35rem; padding-bottom: 2.5rem; max-width: 1480px;}
        h1 {letter-spacing: -0.02em;}
        h2, h3 {letter-spacing: -0.01em;}
        [data-testid="stMetric"] {
            border: 1px solid rgba(128,128,128,.22);
            border-radius: 12px;
            padding: .65rem .8rem;
            background: rgba(128,128,128,.035);
        }
        [data-testid="stExpander"] {
            border: 1px solid rgba(128,128,128,.18);
            border-radius: 12px;
        }
        .mott-stepbar {display:flex; gap:.45rem; flex-wrap:wrap; margin:.35rem 0 1.0rem 0;}
        .mott-step {
            padding:.38rem .68rem; border-radius:999px; font-size:.86rem;
            border:1px solid rgba(128,128,128,.28); opacity:.78;
        }
        .mott-step.done {opacity:1; font-weight:600;}
        .mott-step.active {opacity:1; font-weight:700; border-width:2px;}
        .mott-kicker {font-size:.88rem; opacity:.72; margin-bottom:.15rem;}
        .mott-class-card {
            border:1px solid rgba(128,128,128,.24); border-radius:14px;
            padding:.75rem 1rem; margin:.25rem 0 .85rem 0;
            background:rgba(128,128,128,.035);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def mostrar_ruta_interfaz(etapa=4):
    nombres = [
        "1. Problema",
        "2. Datos interpretados",
        "3. Sistema",
        "4. Método",
        "5. Resultados",
        "6. Verificación",
    ]
    piezas = []
    for i, nombre in enumerate(nombres, 1):
        clase = "active" if i == etapa else ("done" if i < etapa else "")
        piezas.append(f'<span class="mott-step {clase}">{nombre}</span>')
    st.markdown(
        '<div class="mott-stepbar">' + ''.join(piezas) + '</div>',
        unsafe_allow_html=True,
    )


def titulo_bloque(numero, titulo, descripcion=None):
    st.markdown(f'<div class="mott-kicker">PASO {numero}</div>', unsafe_allow_html=True)
    st.subheader(titulo)
    if descripcion:
        st.caption(descripcion)


def _reset_campos_dimensionales_por_cambio_unidades():
    """Evita reinterpretar un número ya escrito con otra unidad."""
    prefijos = ("I_", "II_", "IIIA_", "IIIB_", "graf_I", "graf_II", "graf_IIIA", "graf_IIIB")
    conservar_sufijos = ("_fluido", "_material", "_accesorios")
    for k in list(st.session_state.keys()):
        if k.startswith(prefijos) and not k.endswith(conservar_sufijos):
            st.session_state.pop(k, None)
    st.session_state.prefill_mensaje = False


def mostrar_diagnosticos(diags, titulo="Diagnóstico físico automático", expanded=False):
    diags = list(diags or [])
    if not diags:
        return False

    with st.expander(f"🩺 {titulo}", expanded=expanded):
        for d in diags:
            nivel = d.get("nivel", "info")
            mensaje = d.get("mensaje", "")
            sugerencia = d.get("sugerencia")
            texto = mensaje + (f"  \n**Sugerencia:** {sugerencia}" if sugerencia else "")
            if nivel == "error":
                st.error(texto)
            elif nivel == "warning":
                st.warning(texto)
            elif nivel == "ok":
                st.success(texto)
            else:
                st.info(texto)
    return hay_bloqueantes(diags)


def mostrar_auditoria_v148(auditoria, titulo="Auditoría independiente del resultado"):
    """Presenta la auditoría V14.8 sin modificar el resultado del solver."""
    auditoria = auditoria or {}
    estado = auditoria.get("estado", "—")
    errores = int(auditoria.get("errores", 0) or 0)
    advertencias = int(auditoria.get("advertencias", 0) or 0)
    comprobaciones = int(auditoria.get("comprobaciones", 0) or 0)

    if estado == "OK":
        st.success(
            f"✅ V14.8: auditoría independiente superada ({comprobaciones} comprobaciones)."
        )
    elif estado == "REVISAR":
        st.warning(
            f"⚠️ V14.8: resultado utilizable con {advertencias} advertencia(s); revíselas antes de entregar."
        )
    else:
        st.error(
            f"❌ V14.8: se detectaron {errores} inconsistencia(s) interna(s). No use el resultado sin revisar."
        )

    with st.expander(f"🧪 V14.8 — {titulo}", expanded=estado != "OK"):
        c1, c2, c3 = st.columns(3)
        c1.metric("Estado", estado)
        c2.metric("Comprobaciones", comprobaciones)
        c3.metric("Errores / advertencias", f"{errores} / {advertencias}")

        filas = []
        for c in auditoria.get("checks") or []:
            err = c.get("error_rel")
            filas.append({
                "Estado": str(c.get("nivel", "")).upper(),
                "Código": c.get("codigo", ""),
                "Comprobación": c.get("mensaje", ""),
                "Error relativo": None if err is None else float(err),
            })
        if filas:
            st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

        txt = reporte_texto_v148(auditoria, titulo=f"{titulo} — {VERSION_AUDITORIA}")
        js = reporte_json_v148(auditoria)
        d1, d2 = st.columns(2)
        d1.download_button(
            "⬇️ Descargar auditoría TXT",
            data=txt.encode("utf-8"),
            file_name="auditoria_resultado_v14_8.txt",
            mime="text/plain",
            use_container_width=True,
            key=f"desc_txt_v148_{titulo}",
        )
        d2.download_button(
            "⬇️ Descargar auditoría JSON",
            data=js.encode("utf-8"),
            file_name="auditoria_resultado_v14_8.json",
            mime="application/json",
            use_container_width=True,
            key=f"desc_json_v148_{titulo}",
        )



def mostrar_auditoria_fisica_v1416(auditoria, titulo="Auditoría física ampliada"):
    """Presenta V14.16 sin modificar ni recalcular la solución del solver."""
    auditoria = auditoria or {}
    if not auditoria:
        return
    estado = str(auditoria.get("estado") or "—")
    errores = int(auditoria.get("errores", 0) or 0)
    advertencias = int(auditoria.get("advertencias", 0) or 0)
    infos = int(auditoria.get("informativos", 0) or 0)
    comprobaciones = int(auditoria.get("comprobaciones", 0) or 0)

    if estado == "OK":
        st.success(f"✅ V14.16: auditoría física sin banderas de revisión ({comprobaciones} comprobaciones).")
    elif estado == "REVISAR":
        st.warning(f"⚠️ V14.16: {advertencias} advertencia(s) física(s). El resultado puede ser matemáticamente correcto, pero conviene revisar estas condiciones.")
    else:
        st.error(f"❌ V14.16: {errores} inconsistencia(s) física(s) importante(s). No use el resultado sin revisar.")

    with st.expander(f"🩺 V14.16 — {titulo}", expanded=estado != "OK"):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Estado", estado)
        c2.metric("Errores", errores)
        c3.metric("Advertencias", advertencias)
        c4.metric("Informativos", infos)
        st.caption(
            "V14.16 usa banderas de plausibilidad/revisión; no sustituye límites normativos específicos, "
            "criterios del fabricante ni condiciones particulares de diseño."
        )
        filas = []
        for c in auditoria.get("checks") or []:
            filas.append({
                "Estado": str(c.get("nivel", "")).upper(),
                "Código": c.get("codigo", ""),
                "Comprobación": c.get("mensaje", ""),
                "Valor": c.get("valor"),
                "Unidad": c.get("unidad"),
                "Criterio": c.get("criterio"),
            })
        if filas:
            st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)
        txt = reporte_texto_v1416(auditoria, titulo=f"{titulo} — {VERSION_AUDITORIA_FISICA}")
        js = reporte_json_v1416(auditoria)
        d1, d2 = st.columns(2)
        d1.download_button(
            "⬇️ Auditoría física TXT",
            data=txt.encode("utf-8"),
            file_name="auditoria_fisica_v14_16.txt",
            mime="text/plain", use_container_width=True,
            key=f"desc_txt_v1416_{titulo}",
        )
        d2.download_button(
            "⬇️ Auditoría física JSON",
            data=js.encode("utf-8"),
            file_name="auditoria_fisica_v14_16.json",
            mime="application/json", use_container_width=True,
            key=f"desc_json_v1416_{titulo}",
        )



def mostrar_manifiesto_v149(manifiesto):
    """Resume la ejecución trazable creada a partir del snapshot confirmado V14.7."""
    if not manifiesto:
        return
    with st.expander("🧾 V14.9 — Manifiesto de ejecución confirmada", expanded=False):
        c1, c2, c3 = st.columns(3)
        c1.metric("Clase", manifiesto.get("clase", "—"))
        c2.metric("Tramos", len(manifiesto.get("tramos") or []))
        c3.metric("Firma V14.7", str(manifiesto.get("firma_corta") or "—"))
        st.caption(
            "Este manifiesto conserva el snapshot confirmado y la procedencia de los datos. "
            "Si modifica un campo después del autollenado, V14.9 lo señalará en el reporte final."
        )
        filas = []
        for x in manifiesto.get("generales") or []:
            filas.append({
                "Dato": x.get("dato"),
                "Valor": x.get("valor"),
                "Unidad": x.get("unidad"),
                "Fuente": x.get("fuente"),
            })
        if filas:
            st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)


def mostrar_reporte_final_v149(manifiesto, resultado_solver, auditoria, titulo, entrada_actual=None, auditoria_fisica=None, contexto_diagramas=None):
    """Genera el reporte técnico V14.9 sin alterar el cálculo hidráulico."""
    if not manifiesto:
        st.caption(
            "V14.9: el reporte trazable completo está disponible cuando el problema proviene "
            "del flujo automático confirmado en V14.7."
        )
        return None

    try:
        coherencia = verificar_ejecucion_vs_manifiesto(
            manifiesto, entrada_actual or {}
        )
        reporte = construir_reporte_final(manifiesto, resultado_solver, auditoria, auditoria_fisica)
        reporte["coherencia_ejecucion_v149"] = coherencia
    except ErrorReporteV149 as error:
        st.error(f"V14.9 no pudo construir el reporte: {error}")
        return None

    coincide = bool(coherencia.get("coincide_snapshot_v147"))
    estado_aud = str((auditoria or {}).get("estado", "—"))
    estado_fis = str((auditoria_fisica or {}).get("estado", "NO EVALUADA"))
    estado_global = str(reporte.get("estado_final") or estado_aud)
    if coincide and estado_global == "OK":
        st.success("✅ V14.9: ejecución trazable, auditoría matemática y auditoría física conformes.")
    elif coincide:
        st.warning(
            f"⚠️ V14.9: la ejecución coincide con V14.7, pero el estado final quedó en {estado_global} "
            f"(matemática={estado_aud}; física={estado_fis})."
        )
    else:
        st.warning(
            "⚠️ V14.9 detectó cambios manuales después de la transferencia V14.7. "
            "El resultado puede ser válido, pero ya no coincide exactamente con el snapshot confirmado."
        )

    with st.expander(f"📘 V14.9 — Reporte técnico final · {titulo}", expanded=False):
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Matemática", estado_aud)
        m2.metric("Física", estado_fis)
        m3.metric("Snapshot V14.7", "COINCIDE" if coincide else "MODIFICADO")
        m4.metric("Cambios posteriores", int(coherencia.get("cantidad_diferencias", 0) or 0))

        if not coincide:
            st.dataframe(
                pd.DataFrame(coherencia.get("diferencias") or []),
                use_container_width=True,
                hide_index=True,
            )

        md = reporte_markdown_v149(reporte)
        js = reporte_json_v149(reporte)
        try:
            docx = reporte_docx_v149(reporte)
        except ErrorReporteV149 as error:
            docx = None
            st.warning(str(error))

        clave = "".join(c if c.isalnum() else "_" for c in str(titulo))
        d1, d2, d3 = st.columns(3)
        d1.download_button(
            "⬇️ Reporte Markdown",
            data=md.encode("utf-8"),
            file_name=f"reporte_tecnico_{clave}_v14_9.md",
            mime="text/markdown",
            use_container_width=True,
            key=f"v149_md_{clave}",
        )
        d2.download_button(
            "⬇️ Reporte JSON",
            data=js.encode("utf-8"),
            file_name=f"reporte_tecnico_{clave}_v14_9.json",
            mime="application/json",
            use_container_width=True,
            key=f"v149_json_{clave}",
        )
        if docx is not None:
            d3.download_button(
                "⬇️ Reporte Word",
                data=docx,
                file_name=f"reporte_tecnico_{clave}_v14_9.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                key=f"v149_docx_{clave}",
            )

    # V14.18 — capa de presentación técnica V2. Conserva V14.9 como base
    # trazable y añade portada, ecuaciones, nomenclatura y figuras V14.15.
    with st.expander(f"📚 V14.18 — Reporte técnico V2 · {titulo}", expanded=False):
        st.caption(
            "V14.18 no recalcula el problema: presenta profesionalmente el reporte trazable V14.9 "
            "e incrusta los diagramas V14.15 cuando están disponibles."
        )
        try:
            docx_v2 = reporte_docx_v1418(reporte, contexto_diagramas)
        except ErrorReporteV1418 as error:
            docx_v2 = None
            st.warning(f"Word V14.18 no disponible: {error}")
        try:
            pdf_v2 = reporte_pdf_v1418(reporte, contexto_diagramas)
        except ErrorReporteV1418 as error:
            pdf_v2 = None
            st.warning(f"PDF V14.18 no disponible: {error}")

        c1, c2, c3 = st.columns(3)
        c1.metric("Versión", VERSION_REPORTE_V2)
        c2.metric("Figuras V14.15", "3" if contexto_diagramas and contexto_diagramas.get("disponible") else "0")
        c3.metric("Estado integral", str(reporte.get("estado_final") or "—"))
        b1, b2 = st.columns(2)
        if docx_v2 is not None:
            b1.download_button(
                "⬇️ Reporte técnico V2 — Word",
                data=docx_v2,
                file_name=f"reporte_tecnico_{clave}_v14_18.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                key=f"v1418_docx_{clave}",
            )
        if pdf_v2 is not None:
            b2.download_button(
                "⬇️ Reporte técnico V2 — PDF",
                data=pdf_v2,
                file_name=f"reporte_tecnico_{clave}_v14_18.pdf",
                mime="application/pdf",
                use_container_width=True,
                key=f"v1418_pdf_{clave}",
            )
    return reporte



def mostrar_procedimiento_v1419(flujo):
    """Muestra el desarrollo académico construido con el resultado real del solver."""
    proc = (flujo or {}).get("procedimiento_v1419") or {}
    if not proc:
        return
    clase = str(proc.get("clase") or "—")
    with st.expander(f"🧾 V14.19 — Mostrar procedimiento Mott · {clase}", expanded=False):
        st.caption(
            "V14.19 no vuelve a resolver el problema: ordena los datos, ecuaciones, sustituciones, "
            "iteraciones y comprobaciones que corresponden al resultado ya validado por el solver."
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("Versión", VERSION_PROCEDIMIENTO)
        c2.metric("Pasos", len(proc.get("pasos") or []))
        c3.metric("Iteraciones registradas", len(proc.get("historial_iteracion") or []))

        for paso in proc.get("pasos") or []:
            st.markdown(f"### {paso.get('numero')}. {paso.get('titulo')}")
            if paso.get("descripcion"):
                st.write(paso.get("descripcion"))
            if paso.get("ecuacion"):
                st.markdown(f"**Ecuación:** `{paso.get('ecuacion')}`")
            if paso.get("sustitucion"):
                st.markdown(f"**Sustitución:** {paso.get('sustitucion')}")
            if paso.get("resultado"):
                st.markdown(f"**Resultado:** {paso.get('resultado')}")

        historial = proc.get("historial_iteracion") or []
        if historial:
            with st.expander("🔁 Historial iterativo completo", expanded=False):
                st.dataframe(pd.DataFrame(historial), use_container_width=True, hide_index=True)

        st.success(f"Respuesta final: {proc.get('resultado_final','—')}")
        try:
            md = procedimiento_markdown_v1419(proc)
            docx = procedimiento_docx_v1419(proc)
        except ErrorProcedimientoV1419 as error:
            st.warning(str(error))
            return
        clave = "".join(c if c.isalnum() else "_" for c in clase)
        b1, b2 = st.columns(2)
        b1.download_button(
            "⬇️ Procedimiento Mott — Markdown",
            data=md.encode("utf-8"),
            file_name=f"procedimiento_mott_{clave}_v14_19.md",
            mime="text/markdown",
            use_container_width=True,
            key=f"v1419_md_{clave}",
        )
        b2.download_button(
            "⬇️ Procedimiento Mott — Word",
            data=docx,
            file_name=f"procedimiento_mott_{clave}_v14_19.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
            key=f"v1419_docx_{clave}",
        )



def _incognita_ui_v1420(prefill):
    etiqueta = prefill.get("incognita_clase_i")
    return {
        "Presión P2": "P2_kpa", "Presión P1": "P1_kpa",
        "Carga agregada por bomba hA": "hA_m", "Carga retirada hR": "hR_m",
        "Elevación z2": "z2_m", "Elevación z1": "z1_m",
        "P2": "P2_kpa", "P1": "P1_kpa", "hA": "hA_m", "hR": "hR_m",
        "z2": "z2_m", "z1": "z1_m",
    }.get(etiqueta)


def mostrar_comparador_v1420(flujo):
    """Compara variantes explícitas sin modificar el escenario base V14.7."""
    if not flujo or not flujo.get("manifiesto_v149"):
        return
    try:
        firma = firma_base_v1420(flujo)
        prefill = extraer_prefill_base_v1420(flujo)
    except ErrorComparadorV1420 as exc:
        with st.expander("🧪 V14.20 — Comparador de escenarios", expanded=False):
            st.info(str(exc))
        return

    if st.session_state.get("v1420_firma_base") != firma:
        st.session_state["v1420_firma_base"] = firma
        st.session_state["v1420_escenarios"] = []

    clase = str(flujo.get("clase") or "")
    tramos = list(prefill.get("tramos") or [])
    escenarios = st.session_state.get("v1420_escenarios") or []
    clave_base = str(firma)[:10]

    with st.expander("🧪 V14.20 — Comparador de escenarios", expanded=False):
        st.caption(
            "El escenario Base es una copia inmutable del snapshot V14.7. Cada variante aplica únicamente "
            "el cambio que usted indique y vuelve a ejecutar el mismo solver, V14.8.3, V14.16 y V14.19. "
            "V14.20 no cambia la clase hidráulica silenciosamente."
        )

        opciones = ["Longitud de un tramo", "Material de un tramo"]
        if clase != "Clase III-A":
            opciones.insert(0, "Diámetro de un tramo")
        inc_i = _incognita_ui_v1420(prefill) if clase == "Clase I" else None
        if clase != "Clase III-A":
            if clase not in ("Clase II-A",):
                opciones += ["K adicional de un tramo"]
            if clase not in ("Clase II-A",):
                if any(t.get("accesorios") for t in tramos):
                    opciones += ["Reemplazar accesorio / válvula"]
                opciones += ["Agregar accesorio / válvula"]
        for etiqueta, campo in [
            ("Presión P1", "P1_kpa"), ("Presión P2", "P2_kpa"),
            ("Elevación z1", "z1_m"), ("Elevación z2", "z2_m"),
            ("Carga de bomba hA", "hA_m"), ("Carga de turbina hR", "hR_m"),
        ]:
            if campo != inc_i:
                opciones.append(etiqueta)
        if clase not in ("Clase II-A", "Clase II-B", "Clase II-C") and inc_i != "Q_m3s":
            opciones.append("Caudal Q")

        n_esc = len(escenarios) + 1
        cnom, ctipo = st.columns([1.1, 1.5])
        nombre = cnom.text_input("Nombre del escenario", value=f"Escenario {n_esc}", key=f"v1420_nombre_{clave_base}_{n_esc}")
        tipo = ctipo.selectbox("Cambio a evaluar", opciones, key=f"v1420_tipo_{clave_base}_{n_esc}")

        cambio = None
        if tipo in {"Diámetro de un tramo", "Longitud de un tramo", "Material de un tramo", "K adicional de un tramo", "Reemplazar accesorio / válvula", "Agregar accesorio / válvula"}:
            numeros = [int(t.get("numero", i) or i) for i, t in enumerate(tramos, 1)]
            numero = st.selectbox("Tramo", numeros, key=f"v1420_tramo_{clave_base}_{n_esc}")
            t = next(t for i, t in enumerate(tramos, 1) if int(t.get("numero", i) or i) == int(numero))
            if tipo == "Diámetro de un tramo":
                if clase == "Clase III-A":
                    st.warning("Clase III-A calcula D; no se puede imponer un diámetro como escenario sin cambiar de clase.")
                else:
                    valor = entrada_dimensionada("Nuevo diámetro", "diametro", value=float(t.get("D_m") or 0.1), min_value=1e-5, step=0.005, key=f"v1420_D_{clave_base}_{n_esc}", format="%.5f")
                    cambio = {"campo": "D_m", "tramo": numero, "valor": valor}
            elif tipo == "Longitud de un tramo":
                valor = entrada_dimensionada("Nueva longitud", "longitud", value=float(t.get("L_m") or 1.0), min_value=1e-6, step=1.0, key=f"v1420_L_{clave_base}_{n_esc}", format="%.4f")
                cambio = {"campo": "L_m", "tramo": numero, "valor": valor}
            elif tipo == "Material de un tramo":
                mats = list(MATERIALES.keys())
                actual = t.get("material") if t.get("material") in mats else mats[0]
                mat = st.selectbox("Nuevo material", mats, index=mats.index(actual), key=f"v1420_mat_{clave_base}_{n_esc}")
                cambio = {"campo": "material", "tramo": numero, "valor": mat}
                if mat == "Personalizada":
                    eps = entrada_dimensionada("Rugosidad ε", "rugosidad", value=float(t.get("epsilon_m") or 4.6e-5), min_value=0.0, step=1e-6, key=f"v1420_eps_{clave_base}_{n_esc}", format="%.8f")
                    cambio["epsilon_m"] = eps
            elif tipo == "K adicional de un tramo":
                kval = st.number_input("Nuevo K adicional", min_value=0.0, value=float(t.get("K_extra") or 0.0), step=0.1, format="%.4f", key=f"v1420_K_{clave_base}_{n_esc}")
                cambio = {"campo": "K_extra", "tramo": numero, "valor": float(kval)}
            elif tipo == "Reemplazar accesorio / válvula":
                accs = list(t.get("accesorios") or [])
                if not accs:
                    st.warning("El tramo seleccionado no tiene accesorios que reemplazar.")
                else:
                    etiquetas = [f"{i+1}. {a.get('nombre','Accesorio')} ×{int(a.get('cantidad',1) or 1)}" for i, a in enumerate(accs)]
                    sel = st.selectbox("Accesorio actual", list(range(len(accs))), format_func=lambda i: etiquetas[i], key=f"v1420_accidx_{clave_base}_{n_esc}")
                    nuevo = st.selectbox("Reemplazar por", list(ACCESORIOS.keys()), key=f"v1420_accnew_{clave_base}_{n_esc}")
                    cambio = {"campo": "accesorio_reemplazar", "tramo": numero, "indice_accesorio": int(sel), "valor": nuevo, "cantidad": int(accs[sel].get("cantidad", 1) or 1)}
            elif tipo == "Agregar accesorio / válvula":
                nuevo = st.selectbox("Accesorio a agregar", list(ACCESORIOS.keys()), key=f"v1420_accadd_{clave_base}_{n_esc}")
                cant = st.number_input("Cantidad", min_value=1, value=1, step=1, key=f"v1420_acccant_{clave_base}_{n_esc}")
                cambio = {"campo": "accesorio_agregar", "tramo": numero, "valor": nuevo, "cantidad": int(cant)}
        else:
            mapa = {
                "Presión P1": ("P1_kpa", "presion"), "Presión P2": ("P2_kpa", "presion"),
                "Elevación z1": ("z1_m", "longitud"), "Elevación z2": ("z2_m", "longitud"),
                "Carga de bomba hA": ("hA_m", "carga"), "Carga de turbina hR": ("hR_m", "carga"),
                "Caudal Q": ("Q_m3s", "caudal"),
            }
            campo, kind = mapa[tipo]
            actual = prefill.get(campo)
            actual = 0.0 if actual is None else float(actual)
            min_v = 0.0 if campo in {"hA_m", "hR_m", "Q_m3s"} else None
            valor = entrada_dimensionada(f"Nuevo valor — {tipo}", kind, value=actual, min_value=min_v, step=0.5 if kind != "caudal" else 0.001, key=f"v1420_gen_{campo}_{clave_base}_{n_esc}", format="%.6f")
            cambio = {"campo": campo, "valor": valor}

        if st.button("➕ Agregar y resolver escenario", type="primary", use_container_width=True, key=f"v1420_add_{clave_base}_{n_esc}", disabled=cambio is None):
            try:
                resuelto = resolver_escenario_v1420(flujo, [cambio], nombre.strip() or f"Escenario {n_esc}")
            except Exception as exc:
                st.error(f"V14.20 no pudo resolver el escenario: {exc}")
            else:
                st.session_state["v1420_escenarios"] = escenarios + [resuelto]
                escenarios = st.session_state["v1420_escenarios"]
                st.success(f"Escenario '{resuelto['nombre']}' resuelto sin modificar la base.")

        if escenarios:
            st.markdown("### Comparación")
            comparacion = construir_comparacion_v1420(flujo, escenarios)
            tabla = pd.DataFrame(filas_para_tabla_v1420(comparacion))
            # V14.20.1 — formato visual: conserva precisión útil y elimina ruido
            # numérico sin alterar los datos completos usados en exportaciones.
            tabla_visual = tabla.copy()
            for col in ("Resultado", "Q (m³/s)"):
                if col in tabla_visual.columns:
                    tabla_visual[col] = pd.to_numeric(tabla_visual[col], errors="coerce").round(8)
            for col in ("Δ resultado (%)", "Δ Q (%)", "Δ hL (%)", "Δ Vmáx (%)"):
                if col in tabla_visual.columns:
                    vals = pd.to_numeric(tabla_visual[col], errors="coerce")
                    vals = vals.mask(vals.abs() < 1e-7, 0.0)
                    tabla_visual[col] = vals.round(4)
            for col, dec in (("hL (m)", 6), ("V máx (m/s)", 4), ("Re mín", 1), ("Re máx", 1), ("P bomba hid. (kW)", 4), ("Margen P (kPa)", 4)):
                if col in tabla_visual.columns:
                    tabla_visual[col] = pd.to_numeric(tabla_visual[col], errors="coerce").round(dec)
            st.dataframe(tabla_visual, use_container_width=True, hide_index=True)

            graf = pd.DataFrame([{
                "Escenario": f.get("nombre"),
                "Q (m³/s)": f.get("Q_m3s"),
                "hL (m)": f.get("hL_total_m"),
                "V máx (m/s)": f.get("V_max_ms"),
            } for f in comparacion.get("filas") or []]).set_index("Escenario")
            g1, g2, g3 = st.columns(3)
            if graf["Q (m³/s)"].notna().any():
                g1.bar_chart(graf[["Q (m³/s)"]])
            if graf["hL (m)"].notna().any():
                g2.bar_chart(graf[["hL (m)"]])
            if graf["V máx (m/s)"].notna().any():
                g3.bar_chart(graf[["V máx (m/s)"]])

            with st.expander("🔎 Detalle y trazabilidad de escenarios", expanded=False):
                for idx, esc in enumerate(escenarios):
                    r = esc.get("resumen") or {}
                    st.markdown(f"**{esc.get('nombre','Escenario')}** · {r.get('estado_integral','—')}")
                    for c in esc.get("cambios") or []:
                        tramo_txt = f" · tramo {c.get('tramo')}" if c.get("tramo") else ""
                        st.write(f"• {c.get('campo')}{tramo_txt}: {c.get('anterior')} → {c.get('valor')}")
                    st.caption(f"Firma escenario: {str(esc.get('firma_escenario',''))[:12]}")

            d1, d2, d3 = st.columns(3)
            d1.download_button("⬇️ Comparación JSON", data=reporte_json_v1420(comparacion).encode("utf-8"), file_name="comparacion_escenarios_v14_20.json", mime="application/json", use_container_width=True, key=f"v1420_json_{clave_base}")
            d2.download_button("⬇️ Comparación CSV", data=reporte_csv_v1420(comparacion).encode("utf-8-sig"), file_name="comparacion_escenarios_v14_20.csv", mime="text/csv", use_container_width=True, key=f"v1420_csv_{clave_base}")
            d3.download_button("⬇️ Comparación Markdown", data=reporte_markdown_v1420(comparacion).encode("utf-8"), file_name="comparacion_escenarios_v14_20.md", mime="text/markdown", use_container_width=True, key=f"v1420_md_{clave_base}")

            if st.button("🗑️ Limpiar escenarios", use_container_width=True, key=f"v1420_clear_{clave_base}"):
                st.session_state["v1420_escenarios"] = []
                st.rerun()

        st.caption(f"{VERSION_COMPARADOR} · la comparación usa SI internamente y respeta las unidades seleccionadas en la interfaz.")


def mostrar_progreso_v1410(flujo):
    """Muestra las etapas del flujo supervisado sin ocultar las barreras humanas."""
    if not flujo:
        return
    pasos = list(flujo.get("pasos") or [])
    if not pasos:
        return
    with st.expander("⚡ V14.10 — Flujo automático supervisado", expanded=True):
        st.caption(
            "V14.10 automatiza la ejecución posterior al snapshot confirmado; V14.7 sigue siendo "
            "una revisión humana obligatoria y el modo manual permanece disponible."
        )
        filas = []
        iconos = {"OK": "✅", "PENDIENTE": "⏳", "BLOQUEADO": "⛔", "ERROR": "❌", "REVISAR": "⚠️"}
        for i, paso in enumerate(pasos, 1):
            estado = str(paso.get("estado") or "PENDIENTE")
            filas.append({
                "Etapa": i,
                "Paso": paso.get("titulo"),
                "Estado": f"{iconos.get(estado, '•')} {estado}",
            })
        st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)
        if flujo.get("firma_corta") or flujo.get("firma_v147"):
            st.caption(
                f"{VERSION_FLUJO} · snapshot V14.7: "
                f"{flujo.get('firma_corta') or str(flujo.get('firma_v147'))[:12]}"
            )



def mostrar_diagramas_automaticos_v1415(flujo):
    """Muestra V14.15 directamente después del flujo automático V14.10."""
    contexto = (flujo or {}).get("contexto_diagramas_v1415") or {}
    if not contexto:
        return
    if not contexto.get("disponible"):
        with st.expander("📊 V14.15 — Diagramas hidráulicos avanzados", expanded=False):
            st.info(f"V14.15 no puede construir los diagramas con este resultado: {contexto.get('motivo', 'datos insuficientes')}.")
        return

    firma = str((flujo or {}).get("firma_corta") or "auto")
    clave = "".join(c if c.isalnum() else "_" for c in firma)
    sistema = contexto.get("sistema") or {}
    tramos = contexto.get("tramos") or []
    resultados = sistema.get("resultados") or []
    transiciones = contexto.get("transiciones") or []

    with st.expander("📊 V14.15 — Diagramas hidráulicos avanzados", expanded=True):
        st.caption(
            "Se generan con los mismos datos que usó el solver automático. "
            "Ocultar etiquetas solo modifica la vista; no altera pérdidas ni resultados."
        )
        c1, c2, c3, c4 = st.columns(4)
        mostrar_tramos = c1.checkbox("Etiquetas de tramos", value=True, key=f"v1415_tramos_{clave}")
        mostrar_eventos = c2.checkbox("Accesorios/transiciones", value=True, key=f"v1415_eventos_{clave}")
        mostrar_equipos = c3.checkbox("Etiquetas de equipos", value=True, key=f"v1415_equipos_{clave}")
        etiquetar_le = c4.checkbox("Etiquetas en gráficas", value=False, key=f"v1415_lelabels_{clave}")

        tab_esquema, tab_energia, tab_perdidas = st.tabs([
            "🧩 Esquema hidráulico", "📈 LE / LAM", "📉 Pérdidas acumuladas"
        ])

        with tab_esquema:
            fig = crear_esquema_sistema(
                tramos=tramos,
                z1=contexto["z1_m"], z2=contexto["z2_m"],
                tipo_v1=contexto.get("tipo_v1", "tuberia"),
                tipo_v2=contexto.get("tipo_v2", "tuberia"),
                hA=contexto.get("hA_m", 0.0), hR=contexto.get("hR_m", 0.0),
                posicion_bomba=contexto.get("posicion_bomba_m"),
                posicion_turbina=contexto.get("posicion_turbina_m"),
                z_nodos=contexto.get("z_nodos_m") or None,
                transiciones=transiciones,
                titulo=f"{contexto.get('clase', 'Sistema')} — esquema V14.15",
                mostrar_etiquetas_tramos=mostrar_tramos,
                mostrar_etiquetas_accesorios=mostrar_eventos,
                mostrar_etiquetas_transiciones=mostrar_eventos,
                mostrar_etiquetas_equipos=mostrar_equipos,
                mostrar_sentido_flujo=True,
            )
            st.pyplot(fig, clear_figure=True)

        with tab_energia:
            fig = crear_lineas_energia(
                resultados=resultados,
                gamma=contexto["gamma"],
                P1=contexto["P1_pa"], z1=contexto["z1_m"],
                P2=contexto["P2_pa"], z2=contexto["z2_m"],
                V1=contexto["V1_ms"], V2=contexto["V2_ms"],
                hA=contexto.get("hA_m", 0.0), hR=contexto.get("hR_m", 0.0),
                tramos=tramos,
                posicion_bomba=contexto.get("posicion_bomba_m"),
                posicion_turbina=contexto.get("posicion_turbina_m"),
                transiciones=transiciones,
                titulo=f"{contexto.get('clase', 'Sistema')} — LE/LAM V14.15",
                mostrar_marcadores_eventos=True,
                mostrar_etiquetas_eventos=etiquetar_le,
            )
            st.pyplot(fig, clear_figure=True)
            st.caption(
                "La fricción se distribuye a lo largo de cada tramo; accesorios, "
                "transiciones, bomba y turbina aparecen en su posición hidráulica."
            )

        with tab_perdidas:
            fig = crear_perdidas_acumuladas_v1415(
                resultados=resultados, tramos=tramos, transiciones=transiciones,
                hA=contexto.get("hA_m", 0.0), hR=contexto.get("hR_m", 0.0),
                posicion_bomba=contexto.get("posicion_bomba_m"),
                posicion_turbina=contexto.get("posicion_turbina_m"),
                mostrar_etiquetas_eventos=etiquetar_le,
                titulo=f"{contexto.get('clase', 'Sistema')} — pérdidas acumuladas V14.15",
            )
            st.pyplot(fig, clear_figure=True)
            perfil = construir_perfil_perdidas_v1415(
                resultados=resultados, tramos=tramos, transiciones=transiciones,
                hA=contexto.get("hA_m", 0.0), hR=contexto.get("hR_m", 0.0),
                posicion_bomba=contexto.get("posicion_bomba_m"),
                posicion_turbina=contexto.get("posicion_turbina_m"),
            )
            cc1, cc2, cc3, cc4 = st.columns(4)
            cc1.metric("Σ hf", fmt_u(perfil["total_hf_m"], "carga", 5))
            cc2.metric("Σ hm accesorios", fmt_u(perfil["total_hm_accesorios_m"], "carga", 5))
            cc3.metric("Σ hm transiciones", fmt_u(perfil["total_hm_transiciones_m"], "carga", 5))
            cc4.metric("hL total", fmt_u(perfil["hL_total_m"], "carga", 5))

        st.caption(f"{VERSION_DIAGRAMAS_AVANZADOS} · representación derivada del snapshot V14.7 confirmado.")


def mostrar_resultado_v1410(flujo):
    """Presenta la ejecución automática y reutiliza V14.8.3/V14.9 para auditar y reportar."""
    if not flujo:
        return
    mostrar_progreso_v1410(flujo)
    estado_math_flujo = str(flujo.get("estado") or "—")
    estado = str(flujo.get("estado_integral") or estado_math_flujo)
    clase = str(flujo.get("clase") or "—")
    resultado = flujo.get("resultado_solver") or {}
    auditoria = flujo.get("auditoria") or {}
    auditoria_fisica = flujo.get("auditoria_fisica_v1416") or {}

    if estado == "OK":
        st.success("✅ V14.10 completó solver → auditoría matemática → auditoría física → reporte.")
    elif estado == "REVISAR":
        st.warning("⚠️ V14.10 terminó la ejecución, pero alguna auditoría requiere revisión.")
    else:
        st.error("❌ V14.10 ejecutó el flujo, pero una auditoría detectó una inconsistencia importante. Revise antes de usar el resultado.")

    st.subheader(f"Resultado automático — {clase}")
    if clase in ("Clase II-A", "Clase II-B", "Clase II-C"):
        sistema = resultado.get("sistema") or {}
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Caudal Q", fmt_u(float(resultado.get("Q_final", 0.0)), "caudal", 6))
        c2.metric("Iteraciones", int(resultado.get("iteraciones", 0) or 0))
        c3.metric("hL total", fmt_u(float(sistema.get("hL_total", 0.0)), "carga", 6))
        c4.metric("Residual", f"{float(resultado.get('residual', 0.0)):.3e} m")
        filas = sistema.get("resultados") or []
        if filas:
            with st.expander("🧮 Resultados por tramo", expanded=False):
                st.dataframe(formatear_dataframe_resultados(filas), use_container_width=True, hide_index=True)
    elif clase == "Clase I":
        valor = resultado.get("valor")
        unidad_res = resultado.get("unidad")
        c1, c2 = st.columns(2)
        if unidad_res == "Pa":
            c1.metric(str(resultado.get("incognita_etiqueta") or resultado.get("incognita")), fmt_u(float(valor)/1000.0, "presion", 6))
        else:
            c1.metric(str(resultado.get("incognita_etiqueta") or resultado.get("incognita")), fmt_u(float(valor), "carga", 6))
        c2.metric("Residual", f"{float(resultado.get('residual', 0.0)):.3e} m")
    elif clase == "Clase III-A":
        c1, c2, c3 = st.columns(3)
        c1.metric("D mínimo — Mott", f"{float(resultado.get('D_mott', 0.0)):.6f} m")
        c2.metric("D mínimo", f"{float(resultado.get('D_mott', 0.0))*1000:.3f} mm")
        c3.metric("Residual", f"{float(resultado.get('residual', 0.0)):.3e} m")
    elif clase == "Clase III-B":
        c1, c2, c3 = st.columns(3)
        c1.metric("P2 calculada", fmt_u(float(resultado.get("P2_calculada", 0.0))/1000.0, "presion", 4))
        c2.metric("Margen", fmt_u(float(resultado.get("margen_presion", 0.0))/1000.0, "presion", 4))
        c3.metric("Cumple", "SÍ" if bool(resultado.get("satisfactorio", resultado.get("cumple"))) else "NO")

    # V14.15: los diagramas aparecen directamente en el flujo automático;
    # ya no es necesario abrir el solucionador manual para ver LE/LAM.
    mostrar_diagramas_automaticos_v1415(flujo)
    mostrar_procedimiento_v1419(flujo)
    mostrar_comparador_v1420(flujo)

    mostrar_auditoria_v148(auditoria, f"{clase} · V14.10")
    mostrar_auditoria_fisica_v1416(auditoria_fisica, f"{clase} · V14.10")
    mostrar_reporte_final_v149(
        flujo.get("manifiesto_v149"),
        resultado,
        auditoria,
        f"{clase} automático",
        flujo.get("entrada_actual") or {},
        auditoria_fisica,
        flujo.get("contexto_diagramas_v1415") or {},
    )


def formatear_dataframe_resultados(resultados):
    df = pd.DataFrame(resultados).copy()

    # El motor entrega SI. En US Customary se convierten solo las columnas
    # mostradas; los cálculos internos permanecen intactos.
    if es_us(_sistema_ui()):
        conversiones = {
            "L (m)": ("L (ft)", "longitud"),
            "D (m)": ("D (in)", "diametro"),
            "ε (m)": ("ε (in)", "rugosidad"),
            "V (m/s)": ("V (ft/s)", "velocidad"),
            "hf (m)": ("hf (ft)", "carga"),
            "hm (m)": ("hm (ft)", "carga"),
        }
        for origen, (destino, kind) in conversiones.items():
            if origen in df.columns:
                df[destino] = pd.to_numeric(df[origen], errors="coerce").map(
                    lambda x: _desde(x, kind) if pd.notna(x) else x
                )
                df.drop(columns=[origen], inplace=True)

    columnas_redondeo = [
        "L (m)", "D (m)", "ε (m)", "A (m²)", "V (m/s)",
        "L (ft)", "D (in)", "ε (in)", "V (ft/s)",
        "ε/D", "f Darcy", "ΣK", "hf (m)", "hm (m)",
        "hf (ft)", "hm (ft)",
    ]

    for columna in columnas_redondeo:
        if columna in df.columns:
            df[columna] = pd.to_numeric(df[columna], errors="coerce").round(6)

    if "Re" in df.columns:
        df["Re"] = pd.to_numeric(df["Re"], errors="coerce").round(0)

    return df


def selector_fluido(prefijo):
    st.subheader("Propiedades del fluido")

    fluido = st.selectbox(
        "Fluido",
        list(FLUIDOS.keys()),
        key=f"{prefijo}_fluido",
    )

    datos = FLUIDOS[fluido]
    tipo = datos.get("tipo")

    if tipo == "agua_interpolar":
        temperatura = entrada_dimensionada(
            "Temperatura del agua", "temperatura",
            min_value=0.0, max_value=100.0, value=20.0, step=0.5,
            format="%.2f", key=f"{prefijo}_temperatura_agua",
            help="Se interpola linealmente entre las filas del Apéndice A de Mott.",
        )
        datos_calc = propiedades_agua_interpoladas(temperatura)
        rho = float(datos_calc["rho"])
        nu = float(datos_calc["nu"])
        mu = float(datos_calc["mu"])
        gamma = peso_especifico(rho)
        fuente = "Mott 7e — Apéndice A (interpolación lineal)"

    elif tipo in ("agua_tabla", "liquido_mott_25c", "aceite_mott_apendice_c", "liquido_mott_aprox_composicion"):
        rho = float(datos["rho"])
        mu = datos.get("mu")
        nu = datos.get("nu")
        fuente = datos.get("fuente", "Mott")

        advertencia_fluido = datos.get("advertencia")
        if advertencia_fluido:
            st.warning(advertencia_fluido)

        if nu is None:
            st.warning(
                "La tabla de Mott incluida no proporciona viscosidad para este fluido. "
                "La densidad se autocompleta, pero debe introducir ν para poder calcular Reynolds."
            )
            nu = entrada_dimensionada(
                "Viscosidad cinemática ν", "nu", min_value=1e-12,
                value=1.0e-6, format="%.10e", key=f"{prefijo}_nu_faltante",
            )
        else:
            nu = float(nu)

        gamma = peso_especifico(rho)

    else:
        c1, c2 = st.columns(2)
        with c1:
            rho = entrada_dimensionada(
                "Densidad ρ", "densidad", min_value=0.001, value=1000.0,
                format="%.4f", key=f"{prefijo}_rho",
            )
        with c2:
            nu = entrada_dimensionada(
                "Viscosidad cinemática ν", "nu", min_value=1e-12, value=1.02e-6,
                format="%.10e", key=f"{prefijo}_nu",
            )
        mu = rho * nu
        gamma = peso_especifico(rho)
        fuente = "Propiedades introducidas por el usuario"

    # V14.12 — propiedades explícitas del enunciado. Se aplican después de
    # seleccionar el fluido para que una ν/ρ entregada por el problema tenga
    # prioridad sobre la fila tabulada sin perder el nombre del fluido.
    rho_v1412 = st.session_state.get(f"{prefijo}_rho_override_v1412")
    nu_v1412 = st.session_state.get(f"{prefijo}_nu_override_v1412")
    if rho_v1412 is not None:
        try:
            if float(rho_v1412) > 0:
                rho = float(rho_v1412)
        except Exception:
            pass
    if nu_v1412 is not None:
        try:
            if float(nu_v1412) > 0:
                nu = float(nu_v1412)
        except Exception:
            pass
    if rho_v1412 is not None or nu_v1412 is not None:
        mu = float(rho) * float(nu)
        gamma = peso_especifico(float(rho))
        fuente = f"{fuente} + propiedades explícitas normalizadas por V14.12"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Densidad ρ", fmt_u(rho, "densidad", 3))
    c2.metric("Viscosidad ν", f"{_desde(nu, 'nu'):.4e} {_u('nu')}")
    c3.metric("Viscosidad μ", "—" if mu is None else f"{_desde(float(mu), 'mu'):.4e} {_u('mu')}")
    c4.metric("Peso específico γ", f"{_desde(gamma, 'gamma'):.3f} {_u('gamma')}")
    st.caption(f"Fuente de propiedades: {fuente}")

    return rho, nu, gamma

def crear_tramos(prefijo):
    st.subheader("Tramos de tubería")

    c1, c2, espacio = st.columns([1, 1, 4])

    with c1:
        if st.button(
            "➕ Agregar tramo",
            use_container_width=True,
            key=f"{prefijo}_agregar_tramo",
        ):
            st.session_state.num_tramos += 1
            st.rerun()

    with c2:
        if st.button(
            "➖ Eliminar último",
            use_container_width=True,
            key=f"{prefijo}_eliminar_tramo",
        ):
            if st.session_state.num_tramos > 1:
                st.session_state.num_tramos -= 1
                st.rerun()
            else:
                st.warning("Debe existir al menos un tramo.")

    tramos = []

    for i in range(1, st.session_state.num_tramos + 1):
        with st.expander(f"🔹 Tramo {i}", expanded=(i == 1)):
            c1, c2, c3 = st.columns(3)

            with c1:
                L = entrada_dimensionada(
                    "Longitud L", "longitud", min_value=0.01, value=50.0,
                    format="%.4f", key=f"{prefijo}_L_{i}",
                )

            with c2:
                D = entrada_dimensionada(
                    "Diámetro interno D", "diametro", min_value=0.001, value=0.100,
                    format="%.6f", key=f"{prefijo}_D_{i}",
                )

            with c3:
                material = st.selectbox(
                    "Material",
                    list(MATERIALES.keys()),
                    key=f"{prefijo}_material_{i}",
                )

            if material == "Personalizada":
                epsilon = entrada_dimensionada(
                    "Rugosidad absoluta ε", "rugosidad", min_value=0.0, value=0.000046,
                    format="%.8f", key=f"{prefijo}_epsilon_{i}",
                )
            else:
                epsilon = MATERIALES[material]
                st.info(f"ε = {fmt_u(epsilon, 'rugosidad', 8)}")
                info_material = MATERIALES_INFO.get(material)
                if info_material:
                    st.caption(f"Fuente: {info_material['fuente']} — {info_material['descripcion']}")

            st.markdown("#### Accesorios y ubicación")
            st.caption(
                "La posición solo afecta el esquema y la LE/LAM; "
                "el valor hidráulico total de la pérdida no cambia."
            )

            seleccionados = st.multiselect(
                "Seleccione los accesorios:",
                list(ACCESORIOS.keys()),
                key=f"{prefijo}_accesorios_{i}",
            )

            componentes_graficos_detectados = st.session_state.get(
                f"{prefijo}_componentes_graficos_{i}", []
            )
            if componentes_graficos_detectados:
                for componente in componentes_graficos_detectados:
                    posicion_pct = 100.0 * float(
                        componente.get("posicion_fraccion", 0.5) or 0.5
                    )
                    st.warning(
                        f"Se detectó **{componente.get('nombre', 'componente')}** "
                        f"aproximadamente al {posicion_pct:.1f}% del tramo, pero no se "
                        "puede asignar K automáticamente. Seleccione arriba el tipo correcto "
                        "o introduzca un K adicional antes de resolver."
                    )

            K_total = 0.0
            accesorios_detalle = []

            for accesorio in seleccionados:
                ac1, ac2 = st.columns([3.2, 1])

                try:
                    info_k = calcular_k_accesorio(accesorio, D, material)
                    K_unitario = float(info_k["k"])
                except ValueError as error:
                    st.error(str(error))
                    K_unitario = 0.0
                    info_k = {"descripcion": "K no disponible", "fuente": "—", "advertencia": None}

                with ac1:
                    st.write(f"**{accesorio}**")
                    st.caption(info_k["descripcion"])
                    st.caption(f"Fuente: {info_k['fuente']}")

                with ac2:
                    cantidad = st.number_input(
                        "Cantidad",
                        min_value=1,
                        value=1,
                        step=1,
                        key=f"{prefijo}_cantidad_{i}_{accesorio}",
                    )

                K_total += cantidad * K_unitario

                # Cada accesorio puede tener su propia posición.
                # Esto permite autocompletar frases como "dos codos a 10 m y 30 m"
                # sin obligar a representar ambos en el mismo punto.
                posiciones_pct = []

                if int(cantidad) == 1:
                    key_pos = f"{prefijo}_posicion_{i}_{accesorio}_1"
                    posicion_pct = st.number_input(
                        "Posición (%)",
                        min_value=0.0,
                        max_value=100.0,
                        value=70.0,
                        step=1.0,
                        format="%.1f",
                        key=key_pos,
                        help="0 % = inicio del tramo; 100 % = final del tramo.",
                    )
                    posiciones_pct.append(float(posicion_pct))

                else:
                    st.caption(
                        "Puede ubicar cada unidad por separado; esto solo cambia el esquema y LE/LAM."
                    )
                    columnas_pos = st.columns(min(4, int(cantidad)))

                    for n in range(1, int(cantidad) + 1):
                        with columnas_pos[(n - 1) % len(columnas_pos)]:
                            posicion_pct = st.number_input(
                                f"Pos. {n} (%)",
                                min_value=0.0,
                                max_value=100.0,
                                value=float(min(70.0 + 5.0 * (n - 1), 100.0)),
                                step=1.0,
                                format="%.1f",
                                key=f"{prefijo}_posicion_{i}_{accesorio}_{n}",
                            )
                            posiciones_pct.append(float(posicion_pct))

                for posicion_pct in posiciones_pct:
                    accesorios_detalle.append(
                        {
                            "nombre": accesorio,
                            "cantidad": 1,
                            "K_unitario": float(K_unitario),
                            "posicion_fraccion": float(posicion_pct) / 100.0,
                        }
                    )

            st.markdown("#### Curvas de tubería fabricadas — Mott §10.11")
            st.caption(
                "Use esta sección para curvas formadas doblando la propia tubería. "
                "No la confunda con los codos comerciales de la lista anterior."
            )

            numero_curvas = st.number_input(
                "Número de curvas geométricas",
                min_value=0,
                max_value=12,
                value=0,
                step=1,
                key=f"{prefijo}_numero_curvas_{i}",
            )

            for n_curva in range(1, int(numero_curvas) + 1):
                cc1, cc2, cc3 = st.columns(3)
                with cc1:
                    angulo_curva = st.number_input(
                        f"Ángulo curva {n_curva} (°)",
                        min_value=1.0,
                        max_value=360.0,
                        value=90.0,
                        step=5.0,
                        key=f"{prefijo}_curva_angulo_{i}_{n_curva}",
                    )
                with cc2:
                    r_D_curva = st.number_input(
                        f"r/D curva {n_curva}",
                        min_value=0.1,
                        value=3.0,
                        step=0.1,
                        format="%.3f",
                        key=f"{prefijo}_curva_rD_{i}_{n_curva}",
                    )
                with cc3:
                    pos_curva = st.number_input(
                        f"Posición curva {n_curva} (%)",
                        min_value=0.0,
                        max_value=100.0,
                        value=60.0,
                        step=1.0,
                        key=f"{prefijo}_curva_pos_{i}_{n_curva}",
                    )

                try:
                    info_curva = calcular_k_curva_tuberia(
                        D, material, r_D_curva, angulo_curva
                    )
                    K_curva = float(info_curva["k"])
                    K_total += K_curva
                    accesorios_detalle.append(
                        {
                            "nombre": f"Curva θ={angulo_curva:.1f}°, r/D={r_D_curva:.2f}",
                            "cantidad": 1,
                            "K_unitario": K_curva,
                            "posicion_fraccion": float(pos_curva) / 100.0,
                        }
                    )
                    st.caption(
                        f"Curva {n_curva}: {info_curva['descripcion']} — Fuente: {info_curva['fuente']}"
                    )
                    if info_curva.get("advertencia"):
                        st.warning(info_curva["advertencia"])
                except ValueError as error:
                    st.error(f"Curva {n_curva}: {error}")

            ke1, ke2 = st.columns([2, 1])

            with ke1:
                K_extra = st.number_input(
                    "K adicional / personalizado",
                    min_value=0.0,
                    value=0.0,
                    format="%.4f",
                    key=f"{prefijo}_Kextra_{i}",
                )

            with ke2:
                K_extra_pos_pct = st.number_input(
                    "Posición K adicional (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=85.0,
                    step=1.0,
                    format="%.1f",
                    key=f"{prefijo}_Kextra_pos_{i}",
                    disabled=K_extra <= 0,
                )

            K_total += K_extra
            st.info(f"ΣK del tramo = {K_total:.4f}")

            tramos.append(
                {
                    "numero": i,
                    "L": L,
                    "D": D,
                    "material": material,
                    "epsilon": epsilon,
                    "K": K_total,
                    "K_extra": K_extra,
                    "K_extra_posicion_fraccion": float(K_extra_pos_pct) / 100.0,
                    "accesorios_detalle": accesorios_detalle,
                    "componentes_graficos": st.session_state.get(
                        f"{prefijo}_componentes_graficos_{i}", []
                    ),
                }
            )

    return tramos

def crear_transiciones(prefijo, tramos):
    """Configura pérdidas localizadas en los cambios de diámetro entre tramos."""
    if len(tramos) < 2:
        return []

    st.subheader("Transiciones entre tramos — Mott Cap. 10")
    st.caption(
        "El cambio de diámetro no implica por sí solo una pérdida específica. "
        "Seleccione cómo se realiza físicamente la unión. Si el enunciado la reconoce, se autocompleta."
    )

    transiciones = []
    for i in range(1, len(tramos)):
        D1 = float(tramos[i - 1]["D"])
        D2 = float(tramos[i]["D"])

        if abs(D1 - D2) < 1e-12:
            st.info(f"Unión {i}→{i+1}: D1 = D2; no hay cambio de sección.")
            transiciones.append({"entre": i, "tipo": TIPO_SIN, "angulo_grados": None})
            continue

        if D2 > D1:
            opciones = [TIPO_SIN, TIPO_EXP_SUD, TIPO_EXP_GRAD]
            sentido = "ensanchamiento"
        else:
            opciones = [TIPO_SIN, TIPO_CON_SUD, TIPO_CON_GRAD]
            sentido = "contracción"

        with st.expander(
            f"🔁 Unión entre Tramo {i} y Tramo {i+1} — {sentido}",
            expanded=False,
        ):
            st.write(f"D1 = {D1:.6f} m → D2 = {D2:.6f} m")
            tipo = st.selectbox(
                "Tipo de transición",
                opciones,
                key=f"{prefijo}_transicion_{i}",
            )

            angulo = None
            if tipo == TIPO_EXP_GRAD:
                angulo = st.number_input(
                    "Ángulo incluido del cono θ (°)",
                    min_value=2.0,
                    max_value=60.0,
                    value=30.0,
                    step=1.0,
                    key=f"{prefijo}_transicion_angulo_{i}",
                    help="Mott Tabla 10.2: 2° a 60°.",
                )
                st.caption("Se interpolará automáticamente la Tabla 10.2 de Mott.")
            elif tipo == TIPO_CON_GRAD:
                angulo = st.number_input(
                    "Ángulo incluido del cono θ (°)",
                    min_value=3.0,
                    max_value=150.0,
                    value=30.0,
                    step=1.0,
                    key=f"{prefijo}_transicion_angulo_{i}",
                    help="Mott Figuras 10.11–10.12.",
                )
                st.caption(
                    "La contracción gradual se evalúa por interpolación de una digitalización de las "
                    "Figuras 10.11–10.12; la app lo marca como valor gráfico aproximado."
                )
            elif tipo == TIPO_EXP_SUD:
                st.latex(r"K=\left[1-\left(D_1/D_2\right)^2\right]^2")
                st.caption("Mott §10.3; la pérdida usa la velocidad en la tubería menor aguas arriba.")
            elif tipo == TIPO_CON_SUD:
                st.caption(
                    "K se interpola con D1/D2 y la velocidad V2 usando la Tabla 10.3B de Mott."
                )
            else:
                st.warning(
                    "No se añadirá pérdida localizada por esta unión. Úselo solo si el problema "
                    "realmente no especifica una expansión/contracción o si desea introducirla manualmente."
                )

            transiciones.append(
                {
                    "entre": i,
                    "tipo": tipo,
                    "angulo_grados": None if angulo is None else float(angulo),
                }
            )

    return transiciones


def mostrar_resumen_transiciones(sistema):
    detalles = sistema.get("transiciones_resultados") or []
    activos = [d for d in detalles if float(d.get("hL", 0.0) or 0.0) > 0]
    if not activos:
        return

    with st.expander("🔁 Pérdidas en transiciones de diámetro", expanded=False):
        filas = []
        for d in activos:
            filas.append(
                {
                    "Unión": f"{d['entre']}→{d['entre'] + 1}",
                    "Tipo": d["tipo"],
                    "D1 (m)": d["D1"],
                    "D2 (m)": d["D2"],
                    "K": d["K"],
                    "V ref. (m/s)": d["V_ref"],
                    "hL transición (m)": d["hL"],
                    "Fuente": d["fuente"],
                }
            )
            if d.get("advertencia"):
                st.warning(f"Unión {d['entre']}→{d['entre'] + 1}: {d['advertencia']}")

        df = pd.DataFrame(filas)
        for col in ("D1 (m)", "D2 (m)", "K", "V ref. (m/s)", "hL transición (m)"):
            df[col] = pd.to_numeric(df[col], errors="coerce").round(6)
        st.dataframe(df, use_container_width=True, hide_index=True)


def obtener_velocidad_extremo_clase_i(opcion, velocidad_tuberia, key):
    if opcion == "Superficie libre / depósito (V ≈ 0)":
        return 0.0

    if opcion == "Usar velocidad de la tubería":
        return velocidad_tuberia

    return entrada_dimensionada(
        "Velocidad manual", "velocidad", min_value=0.0,
        value=float(velocidad_tuberia), format="%.6f", key=key,
    )


# ============================================================
# AUTOLLENADO DESDE EL ENUNCIADO
# ============================================================

def _poner_si_existe(clave, valor):
    if valor is not None:
        st.session_state[clave] = valor


def _poner_ui_desde_interno(clave, valor, kind):
    if valor is not None:
        st.session_state[clave] = _desde(valor, kind)


def _aplicar_tramos_detectados(prefijo, tramos_detectados):
    if not tramos_detectados:
        return

    st.session_state.num_tramos = max(1, len(tramos_detectados))

    for indice, tramo in enumerate(tramos_detectados, start=1):
        _poner_ui_desde_interno(f"{prefijo}_L_{indice}", tramo.get("L_m"), "longitud")
        _poner_ui_desde_interno(f"{prefijo}_D_{indice}", tramo.get("D_m"), "diametro")

        material = tramo.get("material")
        if material in MATERIALES:
            st.session_state[f"{prefijo}_material_{indice}"] = material
            if material == "Personalizada" and tramo.get("epsilon_m") is not None:
                _poner_ui_desde_interno(
                    f"{prefijo}_epsilon_{indice}", tramo.get("epsilon_m"), "rugosidad"
                )

        accesorios = tramo.get("accesorios") or []

        if accesorios:
            nombres = [
                item["nombre"]
                for item in accesorios
                if item.get("nombre") in ACCESORIOS
            ]

            st.session_state[f"{prefijo}_accesorios_{indice}"] = nombres

            for item in accesorios:
                nombre = item.get("nombre")

                if nombre in ACCESORIOS:
                    cantidad = max(1, int(item.get("cantidad", 1)))
                    st.session_state[
                        f"{prefijo}_cantidad_{indice}_{nombre}"
                    ] = cantidad

                    posiciones = item.get("posiciones_fraccion") or []
                    if not posiciones and item.get("posicion_fraccion") is not None:
                        posiciones = [item.get("posicion_fraccion")]

                    # Si se detectaron menos posiciones que unidades, se reutiliza
                    # la última posición detectada para no perder el autollenado.
                    if posiciones:
                        posiciones = [
                            min(max(float(x), 0.0), 1.0)
                            for x in posiciones
                        ]
                        while len(posiciones) < cantidad:
                            posiciones.append(posiciones[-1])

                        for n in range(1, cantidad + 1):
                            st.session_state[
                                f"{prefijo}_posicion_{indice}_{nombre}_{n}"
                            ] = 100.0 * posiciones[n - 1]

        curvas = tramo.get("curvas") or []
        if curvas:
            st.session_state[f"{prefijo}_numero_curvas_{indice}"] = len(curvas)
            for n_curva, curva in enumerate(curvas, start=1):
                _poner_si_existe(
                    f"{prefijo}_curva_angulo_{indice}_{n_curva}",
                    curva.get("angulo_grados"),
                )
                _poner_si_existe(
                    f"{prefijo}_curva_rD_{indice}_{n_curva}",
                    curva.get("r_D"),
                )

        componentes_graficos = tramo.get("componentes_graficos") or []
        if componentes_graficos:
            st.session_state[f"{prefijo}_componentes_graficos_{indice}"] = componentes_graficos

        # Solo se coloca como K adicional si no se reconocieron accesorios,
        # para evitar contar dos veces la misma pérdida menor.
        k_detectado = tramo.get("K_extra")
        if k_detectado is not None and not accesorios:
            st.session_state[f"{prefijo}_Kextra_{indice}"] = float(k_detectado)

        if tramo.get("K_extra_posicion_fraccion") is not None:
            st.session_state[f"{prefijo}_Kextra_pos_{indice}"] = (
                100.0 * float(tramo.get("K_extra_posicion_fraccion"))
            )


def _clave_grafica_para_clase(clase):
    if clase == "Clase I":
        titulo = "Clase I"
    elif clase in ("Clase II-A", "Clase II-B", "Clase II-C"):
        titulo = clase.replace("Clase ", "")
    elif clase == "Clase III-A":
        titulo = "Clase III-A"
    elif clase == "Clase III-B":
        titulo = "Clase III-B"
    else:
        titulo = str(clase)

    return "".join(c if c.isalnum() else "_" for c in titulo)


def _aplicar_posiciones_equipos_detectadas(clase, prefill):
    clave = _clave_grafica_para_clase(clase)

    posicion_bomba = prefill.get("posicion_bomba_m")
    posicion_turbina = prefill.get("posicion_turbina_m")

    if posicion_bomba is not None:
        st.session_state[f"graf_{clave}_pos_bomba"] = float(posicion_bomba)

    if posicion_turbina is not None:
        st.session_state[f"graf_{clave}_pos_turbina"] = float(posicion_turbina)


def _aplicar_geometria_vertical_detectada(clase, prefill):
    z_nodos = prefill.get("z_nodos_m") or []
    if len(z_nodos) < 3:
        return

    clave = _clave_grafica_para_clase(clase)
    st.session_state[f"graf_{clave}_modo_perfil"] = "Definir elevación en cada unión"

    for j, z in enumerate(z_nodos[1:-1], start=1):
        if z is not None:
            st.session_state[f"graf_{clave}_z_union_{j}"] = float(z)


def _aplicar_transiciones_detectadas(prefijo, prefill):
    for transicion in prefill.get("transiciones") or []:
        i = int(transicion.get("entre", 0) or 0)
        if i <= 0:
            continue
        tipo = transicion.get("tipo")
        if tipo:
            st.session_state[f"{prefijo}_transicion_{i}"] = tipo
        if transicion.get("angulo_grados") is not None:
            st.session_state[f"{prefijo}_transicion_angulo_{i}"] = float(
                transicion["angulo_grados"]
            )


def _aplicar_propiedades_fluido_usuario(prefijo, prefill):
    """Transfiere propiedades aportadas por V14.6/V14.12 sin perder trazabilidad."""
    fluido_app = prefill.get("fluido_app")

    # Limpia overrides de un problema anterior antes de aplicar el nuevo snapshot.
    st.session_state.pop(f"{prefijo}_rho_override_v1412", None)
    st.session_state.pop(f"{prefijo}_nu_override_v1412", None)
    if prefill.get("propiedades_explicitas_v1412"):
        if prefill.get("rho_usuario") is not None:
            st.session_state[f"{prefijo}_rho_override_v1412"] = float(prefill["rho_usuario"])
        if prefill.get("nu_usuario_m2s") is not None:
            st.session_state[f"{prefijo}_nu_override_v1412"] = float(prefill["nu_usuario_m2s"])

    if fluido_app == "Personalizado":
        _poner_ui_desde_interno(f"{prefijo}_rho", prefill.get("rho_usuario"), "densidad")
        _poner_ui_desde_interno(f"{prefijo}_nu", prefill.get("nu_usuario_m2s"), "nu")
    elif fluido_app in FLUIDOS and FLUIDOS[fluido_app].get("nu") is None:
        _poner_ui_desde_interno(f"{prefijo}_nu_faltante", prefill.get("nu_usuario_m2s"), "nu")


def aplicar_autollenado(clase, prefill):
    if not prefill:
        return

    fluido_app = prefill.get("fluido_app")
    tramos = prefill.get("tramos") or []
    temperatura_c = prefill.get("temperatura_c")

    if clase == "Clase I":
        if fluido_app in FLUIDOS:
            st.session_state["I_fluido"] = fluido_app
            if fluido_app == "Agua — interpolar temperatura" and temperatura_c is not None:
                st.session_state["I_temperatura_agua"] = _desde(float(temperatura_c), "temperatura")
            _aplicar_propiedades_fluido_usuario("I", prefill)

        _poner_ui_desde_interno("I_Q", prefill.get("Q_m3s"), "caudal")
        _aplicar_tramos_detectados("I", tramos)
        _aplicar_transiciones_detectadas("I", prefill)

        _poner_ui_desde_interno("I_P1", prefill.get("P1_kpa"), "presion")
        _poner_ui_desde_interno("I_P2", prefill.get("P2_kpa"), "presion")
        _poner_ui_desde_interno("I_z1", prefill.get("z1_m"), "longitud")
        _poner_ui_desde_interno("I_z2", prefill.get("z2_m"), "longitud")
        _poner_ui_desde_interno("I_hA", prefill.get("hA_m"), "carga")
        _poner_ui_desde_interno("I_hR", prefill.get("hR_m"), "carga")

        incognita = prefill.get("incognita_clase_i")
        if incognita:
            st.session_state["I_incognita"] = incognita

        if prefill.get("v1_tipo") == "deposito":
            st.session_state["I_opcion_v1"] = "Superficie libre / depósito (V ≈ 0)"

        if prefill.get("v2_tipo") == "deposito":
            st.session_state["I_opcion_v2"] = "Superficie libre / depósito (V ≈ 0)"

    elif clase in ("Clase II-A", "Clase II-B", "Clase II-C"):
        if fluido_app in FLUIDOS:
            st.session_state["II_fluido"] = fluido_app
            if fluido_app == "Agua — interpolar temperatura" and temperatura_c is not None:
                st.session_state["II_temperatura_agua"] = _desde(float(temperatura_c), "temperatura")
            _aplicar_propiedades_fluido_usuario("II", prefill)

        _aplicar_tramos_detectados("II", tramos)
        _aplicar_transiciones_detectadas("II", prefill)

        _poner_ui_desde_interno("II_P1", prefill.get("P1_kpa"), "presion")
        _poner_ui_desde_interno("II_P2", prefill.get("P2_kpa"), "presion")
        _poner_ui_desde_interno("II_z1", prefill.get("z1_m"), "longitud")
        _poner_ui_desde_interno("II_z2", prefill.get("z2_m"), "longitud")
        _poner_ui_desde_interno("II_hA", prefill.get("hA_m"), "carga")
        _poner_ui_desde_interno("II_hR", prefill.get("hR_m"), "carga")

        if prefill.get("v1_tipo") == "deposito":
            st.session_state["II_tipo_v1"] = "Superficie libre / depósito"

        if prefill.get("v2_tipo") == "deposito":
            st.session_state["II_tipo_v2"] = "Superficie libre / depósito"

    elif clase == "Clase III-A":
        if fluido_app in FLUIDOS:
            st.session_state["IIIA_fluido"] = fluido_app
            if fluido_app == "Agua — interpolar temperatura" and temperatura_c is not None:
                st.session_state["IIIA_temperatura_agua"] = _desde(float(temperatura_c), "temperatura")
            _aplicar_propiedades_fluido_usuario("IIIA", prefill)

        _poner_ui_desde_interno("IIIA_Q", prefill.get("Q_m3s"), "caudal")

        if tramos:
            tramo = tramos[0]
            _poner_ui_desde_interno("IIIA_L", tramo.get("L_m"), "longitud")

            material = tramo.get("material")
            if material in MATERIALES:
                st.session_state["IIIA_material"] = material
                if material == "Personalizada" and tramo.get("epsilon_m") is not None:
                    _poner_ui_desde_interno("IIIA_epsilon", tramo.get("epsilon_m"), "rugosidad")

        _poner_ui_desde_interno("IIIA_P1", prefill.get("P1_kpa"), "presion")
        _poner_ui_desde_interno("IIIA_P2", prefill.get("P2_kpa"), "presion")
        _poner_ui_desde_interno("IIIA_z1", prefill.get("z1_m"), "longitud")
        _poner_ui_desde_interno("IIIA_z2", prefill.get("z2_m"), "longitud")
        _poner_ui_desde_interno("IIIA_hA", prefill.get("hA_m"), "carga")
        _poner_ui_desde_interno("IIIA_hR", prefill.get("hR_m"), "carga")

    elif clase == "Clase III-B":
        if fluido_app in FLUIDOS:
            st.session_state["IIIB_fluido"] = fluido_app
            if fluido_app == "Agua — interpolar temperatura" and temperatura_c is not None:
                st.session_state["IIIB_temperatura_agua"] = _desde(float(temperatura_c), "temperatura")
            _aplicar_propiedades_fluido_usuario("IIIB", prefill)

        _poner_ui_desde_interno("IIIB_Q", prefill.get("Q_m3s"), "caudal")

        if tramos:
            tramo = tramos[0]
            _poner_ui_desde_interno("IIIB_L", tramo.get("L_m"), "longitud")
            _poner_ui_desde_interno("IIIB_D", tramo.get("D_m"), "diametro")

            material = tramo.get("material")
            if material in MATERIALES:
                st.session_state["IIIB_material"] = material
                if material == "Personalizada" and tramo.get("epsilon_m") is not None:
                    _poner_ui_desde_interno("IIIB_epsilon", tramo.get("epsilon_m"), "rugosidad")

            accesorios = tramo.get("accesorios") or []

            if accesorios:
                nombres = [
                    item["nombre"]
                    for item in accesorios
                    if item.get("nombre") in ACCESORIOS
                ]
                st.session_state["IIIB_accesorios"] = nombres

                for item in accesorios:
                    nombre = item.get("nombre")
                    if nombre in ACCESORIOS:
                        cantidad = max(1, int(item.get("cantidad", 1)))
                        st.session_state[f"IIIB_cantidad_{nombre}"] = cantidad

                        posiciones = item.get("posiciones_fraccion") or []
                        if not posiciones and item.get("posicion_fraccion") is not None:
                            posiciones = [item.get("posicion_fraccion")]

                        if posiciones:
                            posiciones = [
                                min(max(float(x), 0.0), 1.0)
                                for x in posiciones
                            ]
                            while len(posiciones) < cantidad:
                                posiciones.append(posiciones[-1])

                            for n in range(1, cantidad + 1):
                                st.session_state[f"IIIB_posicion_{nombre}_{n}"] = (
                                    100.0 * posiciones[n - 1]
                                )

            componentes_graficos = tramo.get("componentes_graficos") or []
            if componentes_graficos:
                st.session_state["IIIB_componentes_graficos"] = componentes_graficos

            k_detectado = tramo.get("K_extra")
            if k_detectado is not None and not accesorios:
                st.session_state["IIIB_Kextra"] = float(k_detectado)

            if tramo.get("K_extra_posicion_fraccion") is not None:
                st.session_state["IIIB_Kextra_pos"] = (
                    100.0 * float(tramo.get("K_extra_posicion_fraccion"))
                )

        _poner_ui_desde_interno("IIIB_P1", prefill.get("P1_kpa"), "presion")
        _poner_ui_desde_interno("IIIB_P2", prefill.get("P2_kpa"), "presion")
        _poner_ui_desde_interno("IIIB_z1", prefill.get("z1_m"), "longitud")
        _poner_ui_desde_interno("IIIB_z2", prefill.get("z2_m"), "longitud")
        _poner_ui_desde_interno("IIIB_hA", prefill.get("hA_m"), "carga")
        _poner_ui_desde_interno("IIIB_hR", prefill.get("hR_m"), "carga")

        if prefill.get("v1_tipo") == "deposito":
            st.session_state["IIIB_tipo_v1"] = "Superficie libre / depósito"

        if prefill.get("v2_tipo") == "deposito":
            st.session_state["IIIB_tipo_v2"] = "Superficie libre / depósito"

    _aplicar_posiciones_equipos_detectadas(clase, prefill)
    _aplicar_geometria_vertical_detectada(clase, prefill)
    st.session_state.prefill_mensaje = True


def mostrar_datos_detectados(resultado_auto, enunciado=""):
    datos = resultado_auto.get("datos") or []

    if datos:
        with st.expander("📋 Datos reconocidos y convertidos a SI", expanded=True):
            for dato in datos:
                st.write(
                    f"**{dato['variable']}:** "
                    + "; ".join(dato["valores"])
                )

    auditoria = construir_auditoria_datos(
        resultado_auto.get("prefill", {}),
        enunciado,
    )
    if auditoria:
        with st.expander("🧭 Auditoría de datos: detectado / inferido / confirmar", expanded=True):
            st.caption(
                "Esta tabla no cambia los datos automáticamente. Su objetivo es mostrar qué tan "
                "directa fue cada interpretación antes de resolver, especialmente útil para el futuro OCR."
            )
            st.dataframe(pd.DataFrame(auditoria), use_container_width=True, hide_index=True)
    return auditoria


def mostrar_normalizaciones_v1412(resultado):
    """Muestra las conversiones/notaciones que V14.12 normalizó antes del solver."""
    prefill = (resultado or {}).get("prefill") or {}
    eventos = list(prefill.get("normalizaciones_v1412") or [])
    if not eventos:
        return
    with st.expander("🔄 V14.12 — Normalización de unidades y notación", expanded=False):
        st.caption(
            "Cada fila conserva el fragmento original y el valor SI usado internamente. "
            "NPS/DN solo se convierte a diámetro interior cuando también se reconoce Schedule/Cédula 40 u 80."
        )
        filas = []
        for e in eventos:
            valor = e.get("valor_si")
            if isinstance(valor, float):
                valor = f"{valor:.10g}"
            filas.append({
                "Tipo": e.get("tipo", ""),
                "Original": e.get("original", ""),
                "Valor SI": valor,
                "Unidad SI": e.get("unidad_si", ""),
                "Tramo": e.get("tramo", ""),
                "Interpretación": e.get("detalle", ""),
            })
        st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)


def mostrar_componentes_v1413(resultado):
    """Resume cómo V14.13 interpretó accesorios y cambios de sección."""
    prefill = (resultado or {}).get("prefill") or {}
    info = prefill.get("interpretacion_componentes_v1413") or {}
    eventos = list(info.get("eventos") or [])
    if not eventos and not prefill.get("componentes_pendientes_v1413"):
        return
    with st.expander("🧰 V14.13 — Accesorios y transiciones avanzadas", expanded=False):
        st.caption(
            "V14.13 asocia accesorios a tramos, documenta si Mott usa K directo o K=fT(Le/D), "
            "y obliga a confirmar todo cambio de diámetro cuyo tipo/ángulo no esté especificado."
        )
        filas = []
        for e in eventos:
            if e.get("tipo") == "transicion":
                filas.append({
                    "Elemento": f"Transición {e.get('entre')}→{int(e.get('entre',0))+1}",
                    "Tramo": "—",
                    "Método/interpretación": e.get("detalle", ""),
                    "Estado": e.get("estado", ""),
                })
            else:
                filas.append({
                    "Elemento": e.get("original", "Accesorio"),
                    "Tramo": e.get("tramo") if e.get("tramo") is not None else "Confirmar",
                    "Método/interpretación": e.get("detalle", ""),
                    "Estado": "Confirmar" if e.get("tipo") == "accesorio_pendiente" else "Detectado",
                })
        if filas:
            st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)
        for adv in info.get("advertencias") or []:
            st.warning(adv)


def mostrar_expediente_v145(resultado_auto):
    """Muestra el expediente consolidado y las únicas preguntas aún necesarias."""
    expediente = (resultado_auto or {}).get("expediente_v145") or {}
    if not expediente:
        return {}

    with st.expander("🧩 V14.5 — Expediente consolidado del problema", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Completitud", f"{float(expediente.get('completitud_pct', 0) or 0):.1f} %")
        c2.metric("Datos faltantes", int(expediente.get("cantidad_faltantes", 0) or 0))
        c3.metric("Conflictos", int(expediente.get("cantidad_conflictos", 0) or 0))
        c4.metric("Incógnitas", len(expediente.get("incognitas") or []))

        st.caption(
            "V14.5 separa datos disponibles, inferencias seguras, incógnitas propias del método "
            "y datos realmente faltantes. No modifica el solver hidráulico."
        )

        filas = expediente.get("filas") or []
        if filas:
            st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

        inferencias = expediente.get("inferencias") or []
        if inferencias:
            st.markdown("**Inferencias seguras aplicadas**")
            for item in inferencias:
                unidad = item.get("unidad", "")
                valor = item.get("valor")
                if isinstance(valor, Number) and not isinstance(valor, bool):
                    try:
                        valor_txt = f"{float(valor):g}"
                    except (TypeError, ValueError):
                        valor_txt = str(valor)
                elif valor is None:
                    valor_txt = "—"
                else:
                    valor_txt = str(valor)
                unidad_txt = f" {unidad}" if unidad else ""
                st.write(
                    f"✓ **{item.get('clave', 'Dato')} = {valor_txt}{unidad_txt}** — "
                    f"{item.get('detalle', '')}"
                )

        incognitas = expediente.get("incognitas") or []
        if incognitas:
            st.markdown("**Incógnitas del problema — no se solicitan como datos de entrada**")
            for item in incognitas:
                st.write(f"🎯 {item.get('etiqueta', item.get('clave', 'Incógnita'))}: {item.get('detalle', '')}")

        faltantes = expediente.get("faltantes") or []
        if faltantes:
            st.warning(
                "Faltan datos para que el problema quede completamente definido. "
                "Estas son las únicas preguntas que V14.5 considera necesarias antes de resolver:"
            )
            for n, item in enumerate(faltantes, 1):
                unidad = f" ({item.get('unidad')})" if item.get("unidad") else ""
                st.write(
                    f"**{n}. {item.get('pregunta', 'Complete el dato')}**{unidad}\n\n"
                    f"{item.get('motivo', '')}"
                )
        else:
            st.success("✅ El expediente contiene todos los datos de entrada necesarios para la clase detectada.")

        conflictos = expediente.get("conflictos") or []
        if conflictos:
            st.error("Hay conflictos que deben corregirse antes de una automatización completa.")

    return expediente


def _kind_pregunta_v146(clave):
    if clave == "Q_m3s":
        return "caudal"
    if clave in {"P1_kpa", "P2_kpa"}:
        return "presion"
    if clave in {"z1_m", "z2_m", "L_m"}:
        return "longitud"
    if clave == "D_m":
        return "diametro"
    if clave in {"hA_m", "hR_m"}:
        return "carga"
    if clave == "temperatura_c":
        return "temperatura"
    return None


def _numero_texto_v146(texto):
    """Convierte entrada explícita del formulario; vacío significa 'sin responder'."""
    t = str(texto or "").strip().replace(" ", "")
    if not t:
        return None
    # Acepta coma decimal habitual sin romper notación científica con punto.
    if "," in t and "." not in t:
        t = t.replace(",", ".")
    return float(t)


def mostrar_completado_v146(resultado_auto, enunciado=""):
    """Genera controles únicamente para los faltantes del expediente V14.5."""
    expediente = (resultado_auto or {}).get("expediente_v145") or {}
    faltantes = list(expediente.get("faltantes") or [])
    conflictos = list(expediente.get("conflictos") or [])

    if st.session_state.pop("v146_flash_ok", False):
        st.success("✅ Respuestas V14.6 incorporadas. El expediente fue reconsolidado.")

    if not expediente:
        return resultado_auto

    if conflictos:
        st.info(
            "V14.6 no habilita respuestas automáticas mientras existan conflictos bloqueantes. "
            "Corrija primero el enunciado o la evidencia confirmada."
        )
        return resultado_auto

    if not faltantes:
        meta = (resultado_auto or {}).get("completado_v146") or {}
        with st.expander("✅ V14.6 — Datos faltantes resueltos", expanded=False):
            st.success(
                "El expediente está completo para la clase detectada. Puede transferirse al "
                "solucionador sin pedir datos adicionales."
            )
            if meta:
                st.caption(
                    f"{VERSION_COMPLETADO}: {meta.get('respuestas_acumuladas', 0)} "
                    "respuesta(s) aportada(s) por el usuario."
                )
        return resultado_auto

    with st.expander("✍️ V14.6 — Complete únicamente los datos faltantes", expanded=True):
        st.caption(
            "Estos controles se generan desde el expediente. Los campos numéricos vacíos no se "
            "guardan ni se sustituyen por valores predeterminados. Puede responder por etapas."
        )

        respuestas = {}
        errores_ui = []
        prefill = (resultado_auto or {}).get("prefill") or {}

        with st.form("form_faltantes_v146", clear_on_submit=False):
            for n, item in enumerate(faltantes, 1):
                pid = identificador_pregunta(item)
                clave = str(item.get("clave") or "")
                st.markdown(f"**{n}. {item.get('pregunta', 'Complete el dato')}**")
                if item.get("motivo"):
                    st.caption(item["motivo"])

                if clave == "incognita_clase_i":
                    opciones = ["Seleccione..."] + list(item.get("opciones") or [])
                    v = st.selectbox("Respuesta", opciones, key=f"v146_{pid}")
                    if v != "Seleccione...":
                        respuestas[pid] = v

                elif clave == "fluido_app":
                    opciones = ["Seleccione..."] + list(FLUIDOS.keys())
                    v = st.selectbox("Fluido", opciones, key=f"v146_{pid}")
                    if v != "Seleccione...":
                        datos_f = FLUIDOS[v]
                        if v == "Personalizado":
                            rho_txt = st.text_input(
                                f"Densidad ρ ({_u('densidad')})", value="",
                                placeholder="Ej.: 998", key=f"v146_{pid}_rho",
                            )
                            nu_txt = st.text_input(
                                f"Viscosidad cinemática ν ({_u('nu')})", value="",
                                placeholder="Ej.: 1.02e-6", key=f"v146_{pid}_nu",
                            )
                            if str(rho_txt).strip() and str(nu_txt).strip():
                                try:
                                    respuestas[pid] = {
                                        "nombre": v,
                                        "rho": _a_interno(_numero_texto_v146(rho_txt), "densidad"),
                                        "nu": _a_interno(_numero_texto_v146(nu_txt), "nu"),
                                    }
                                except ValueError:
                                    errores_ui.append("Fluido personalizado: ρ y ν deben ser numéricos.")
                        elif datos_f.get("nu") is None and datos_f.get("tipo") != "agua_interpolar":
                            nu_txt = st.text_input(
                                f"Viscosidad cinemática ν ({_u('nu')})", value="",
                                placeholder="Dato no tabulado por Mott; introdúzcalo", key=f"v146_{pid}_nu",
                            )
                            if str(nu_txt).strip():
                                try:
                                    respuestas[pid] = {
                                        "nombre": v,
                                        "nu": _a_interno(_numero_texto_v146(nu_txt), "nu"),
                                    }
                                except ValueError:
                                    errores_ui.append("La viscosidad cinemática ν debe ser numérica.")
                        else:
                            respuestas[pid] = v

                elif clave == "material" and item.get("tramo") is not None:
                    opciones = ["Seleccione..."] + list(MATERIALES.keys())
                    v = st.selectbox(
                        f"Material del tramo {item.get('tramo')}",
                        opciones,
                        key=f"v146_{pid}",
                    )
                    if v == "Personalizada":
                        eps_txt = st.text_input(
                            f"Rugosidad absoluta ε ({_u('rugosidad')})",
                            value="", placeholder="Ej.: 0.000046", key=f"v146_{pid}_eps",
                        )
                        if str(eps_txt).strip():
                            try:
                                respuestas[pid] = {
                                    "nombre": v,
                                    "epsilon_m": _a_interno(_numero_texto_v146(eps_txt), "rugosidad"),
                                }
                            except ValueError:
                                errores_ui.append("La rugosidad absoluta ε debe ser numérica.")
                    elif v != "Seleccione...":
                        respuestas[pid] = v

                elif clave == "tramos":
                    respuestas[pid] = int(st.number_input(
                        "Número de tramos de tubería",
                        min_value=1,
                        max_value=20,
                        value=1,
                        step=1,
                        key=f"v146_{pid}",
                    ))

                elif clave.startswith("transicion_"):
                    opciones = opciones_transicion_para_pregunta(item, prefill)
                    tipo = st.selectbox(
                        "Tipo de transición",
                        ["Seleccione..."] + opciones,
                        key=f"v146_{pid}_tipo",
                    )
                    if tipo != "Seleccione...":
                        resp = {"tipo": tipo, "angulo_grados": None}
                        if tipo == TIPO_EXP_GRAD:
                            resp["angulo_grados"] = st.number_input(
                                "Ángulo incluido θ (°)", min_value=2.0, max_value=60.0,
                                value=30.0, step=1.0, key=f"v146_{pid}_ang",
                            )
                        elif tipo == TIPO_CON_GRAD:
                            resp["angulo_grados"] = st.number_input(
                                "Ángulo incluido θ (°)", min_value=3.0, max_value=150.0,
                                value=30.0, step=1.0, key=f"v146_{pid}_ang",
                            )
                        respuestas[pid] = resp

                elif clave.startswith("componente_grafico_") or clave.startswith("componente_texto_v1413_"):
                    es_texto_v1413 = clave.startswith("componente_texto_v1413_")
                    modo = st.selectbox(
                        "¿Cómo debe tratarse este componente?" if es_texto_v1413 else "¿Cómo debe tratarse este símbolo?",
                        [
                            "Seleccione...",
                            "Identificar como accesorio del catálogo Mott",
                            "Introducir K manual",
                            "Confirmar que no agrega pérdida menor",
                        ],
                        key=f"v146_{pid}_modo",
                    )
                    if modo == "Identificar como accesorio del catálogo Mott":
                        nombre = st.selectbox(
                            "Accesorio",
                            ["Seleccione..."] + list(ACCESORIOS.keys()),
                            key=f"v146_{pid}_acc",
                        )
                        if nombre != "Seleccione...":
                            respuestas[pid] = {"modo": "accesorio", "nombre": nombre}
                    elif modo == "Introducir K manual":
                        txt = st.text_input(
                            "K adimensional",
                            value="",
                            placeholder="Ej.: 0.35",
                            key=f"v146_{pid}_k",
                        )
                        if str(txt).strip():
                            try:
                                respuestas[pid] = {"modo": "k_manual", "K": _numero_texto_v146(txt)}
                            except ValueError:
                                errores_ui.append(f"{item.get('etiqueta', clave)}: K no es numérico.")
                    elif modo == "Confirmar que no agrega pérdida menor":
                        respuestas[pid] = {"modo": "sin_perdida"}

                else:
                    kind = _kind_pregunta_v146(clave)
                    unidad_mostrada = _u(kind) if kind else item.get("unidad")
                    etiqueta = "Valor"
                    if unidad_mostrada:
                        etiqueta += f" ({unidad_mostrada})"
                    txt = st.text_input(
                        etiqueta,
                        value="",
                        placeholder="Escriba el valor; puede usar coma o punto decimal",
                        key=f"v146_{pid}",
                    )
                    if str(txt).strip():
                        try:
                            valor_ui = _numero_texto_v146(txt)
                            respuestas[pid] = _a_interno(valor_ui, kind) if kind else valor_ui
                        except ValueError:
                            errores_ui.append(f"{item.get('etiqueta', clave)}: el valor no es numérico.")

                st.divider()

            enviar = st.form_submit_button(
                "💾 INCORPORAR RESPUESTAS Y REVISAR OTRA VEZ",
                type="primary",
                use_container_width=True,
            )

        if enviar:
            if errores_ui:
                for error in errores_ui:
                    st.error(error)
            elif not respuestas:
                st.warning("No se introdujo ninguna respuesta nueva.")
            else:
                try:
                    actualizado = aplicar_respuestas_faltantes(
                        resultado_auto,
                        enunciado,
                        respuestas,
                    )
                except ErrorRespuestaFaltante as error:
                    st.error(str(error))
                else:
                    st.session_state.resultado_auto = actualizado
                    st.session_state.texto_analizado_auto = enunciado
                    st.session_state.enunciado_confirmado_auto = enunciado
                    st.session_state.v146_flash_ok = True
                    st.rerun()

    return resultado_auto


def mostrar_confianza_v1411(resultado_auto, enunciado="", contexto_lectura=None, figura=None):
    """Evalúa confianza individual y exige confirmación solo en datos dudosos.

    Devuelve ``(resultado_enriquecido, reporte)``. Las confirmaciones quedan
    ligadas a la huella individual de cada dato: si cambia su valor, fuente o
    confianza, Streamlit genera una clave nueva y obliga a revisarlo otra vez.
    """
    reporte_base = construir_confianza_datos(
        resultado_auto, enunciado, contexto_lectura=contexto_lectura, figura=figura
    )
    confirmados = set()

    with st.expander("🎯 V14.11 — Confianza individual por dato", expanded=True):
        st.caption(
            "V14.11 prioriza la revisión humana según la procedencia de cada dato. "
            "Los porcentajes son indicadores heurísticos de revisión, no probabilidades estadísticas calibradas."
        )
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Datos", int(reporte_base.get("cantidad_datos", 0) or 0))
        c2.metric("Alta", int(reporte_base.get("altas", 0) or 0))
        c3.metric("Media", int(reporte_base.get("medias", 0) or 0))
        c4.metric("Baja", int(reporte_base.get("bajas", 0) or 0))
        c5.metric("Por confirmar", int(reporte_base.get("pendientes_confirmacion", 0) or 0))

        filas = []
        for x in reporte_base.get("entradas") or []:
            filas.append({
                "Dato": x.get("dato"),
                "Valor": x.get("valor_mostrado"),
                "Confianza": f"{float(x.get('confianza_pct', 0) or 0):.1f} %" if x.get("nivel") != "Método" else "—",
                "Nivel": x.get("nivel"),
                "Fuente": x.get("fuente"),
                "Estado": x.get("estado"),
            })
        if filas:
            st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

        pendientes = [x for x in reporte_base.get("entradas") or [] if x.get("requiere_confirmacion")]
        if pendientes:
            st.warning(
                "Los siguientes datos tienen confianza media/baja. Confírmelos individualmente antes de V14.7; "
                "si alguno es incorrecto, corrija el enunciado y vuelva a analizar."
            )
            for x in pendientes:
                huella = hashlib.sha256(
                    (str(x.get("id")) + "|" + str(x.get("valor")) + "|" + str(x.get("confianza_pct")) + "|" + str(x.get("fuente"))).encode("utf-8")
                ).hexdigest()[:12]
                key = f"v1411_confirm_{huella}"
                etiqueta = (
                    f"Confirmo **{x.get('dato')} = {x.get('valor_mostrado')}** "
                    f"({float(x.get('confianza_pct',0) or 0):.1f} %, {x.get('fuente')})"
                )
                marcado = st.checkbox(etiqueta, value=False, key=key, help=str(x.get("motivo") or ""))
                if marcado:
                    confirmados.add(str(x.get("id")))
        else:
            st.success("✅ Todos los datos disponibles tienen confianza alta o corresponden a incógnitas del método.")

        reporte = aplicar_confirmaciones_v1411(reporte_base, confirmados)
        if reporte.get("listo_para_v147"):
            st.success("✅ V14.11 listo: no quedan datos dudosos sin confirmar.")
        else:
            st.info(
                f"Faltan {int(reporte.get('pendientes_confirmacion', 0) or 0)} confirmación(es) antes de habilitar V14.7."
            )
        st.caption(
            f"{VERSION_CONFIANZA} · firma de confianza: {reporte.get('firma_corta','—')} · "
            f"mínima={reporte.get('confianza_min_pct','—')} % · media={reporte.get('confianza_media_pct','—')} %"
        )

    enriquecido = dict(resultado_auto or {})
    enriquecido["confianza_datos_v1411"] = reporte
    return enriquecido, reporte


def mostrar_previsualizacion_v147(resultado_auto, enunciado=""):
    """Muestra el snapshot exacto que V14.7 transferirá al solucionador.

    Devuelve ``(previsualizacion, confirmada)``. La confirmación queda ligada a
    la firma del snapshot: cualquier cambio en los datos genera una clave nueva
    y obliga a revisar otra vez antes de autollenar.
    """
    previsualizacion = construir_previsualizacion_transferencia(
        resultado_auto, enunciado
    )
    firma = str(previsualizacion.get("firma") or "")
    key_confirmacion = f"v147_confirmar_{firma[:16]}"

    with st.expander(
        "🔎 V14.7 — Previsualización y validación de transferencia",
        expanded=True,
    ):
        st.caption(
            "Revise esta fotografía antes de autocompletar el solucionador. "
            "V14.7 no modifica los cálculos: valida y muestra exactamente los datos "
            "que serán transferidos."
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Clase", previsualizacion.get("clase") or "—")
        c2.metric("Tramos", int(previsualizacion.get("cantidad_tramos", 0) or 0))
        c3.metric("Incógnitas", len(previsualizacion.get("incognitas") or []))
        c4.metric(
            "Estado",
            "LISTO" if previsualizacion.get("listo_para_transferir") else "REVISAR",
        )

        st.markdown("**Datos generales**")
        st.dataframe(
            pd.DataFrame(previsualizacion.get("filas_generales") or []),
            use_container_width=True,
            hide_index=True,
        )

        filas_tramos = previsualizacion.get("filas_tramos") or []
        if filas_tramos:
            st.markdown("**Tramos que se transferirán**")
            st.dataframe(
                pd.DataFrame(filas_tramos),
                use_container_width=True,
                hide_index=True,
            )

        filas_trans = previsualizacion.get("filas_transiciones") or []
        if filas_trans:
            st.markdown("**Cambios de sección / transiciones**")
            st.dataframe(
                pd.DataFrame(filas_trans),
                use_container_width=True,
                hide_index=True,
            )

        incognitas = previsualizacion.get("incognitas") or []
        if incognitas:
            texto_inc = ", ".join(str(x.get("etiqueta") or x.get("clave")) for x in incognitas)
            st.info(f"🎯 **Se calculará, no se transferirá como dato conocido:** {texto_inc}")

        for advertencia in previsualizacion.get("advertencias") or []:
            st.warning(advertencia)

        bloqueos = previsualizacion.get("bloqueos") or []
        if bloqueos:
            st.error("La transferencia automática todavía no es segura:")
            for bloqueo in bloqueos:
                st.write(f"• {bloqueo}")
            confirmada = False
        else:
            st.success(
                "✅ El expediente coincide con los requisitos de la clase y puede "
                "transferirse al solucionador."
            )
            confirmada = st.checkbox(
                "Confirmo que revisé estos datos y deseo transferirlos al solucionador.",
                value=False,
                key=key_confirmacion,
            )

        st.caption(
            f"{VERSION_TRANSFERENCIA} · firma del snapshot: "
            f"{previsualizacion.get('firma_corta', '—')}"
        )

    return previsualizacion, bool(confirmada)


@st.fragment
def mostrar_diagramas_solucion(
    tramos,
    sistema,
    gamma,
    P1,
    z1,
    P2,
    z2,
    V1,
    V2,
    hA=0.0,
    hR=0.0,
    tipo_v1="tuberia",
    tipo_v2="tuberia",
    titulo="Sistema de tuberías",
    transiciones=None,
):
    """Muestra esquema hidráulico y LE/LAM con ubicación configurable."""

    st.divider()
    st.subheader("📊 Representación gráfica automática")

    total_L = sum(float(tramo.get("L", 0.0) or 0.0) for tramo in tramos)
    clave = "".join(c if c.isalnum() else "_" for c in str(titulo))

    with st.expander(
        "🛠️ Configurar geometría y posición de equipos",
        expanded=False,
    ):
        st.caption(
            "Estas opciones modifican la representación gráfica. "
            "Las pérdidas hidráulicas ya calculadas no cambian."
        )

        g1, g2, g3, g4 = st.columns(4)
        mostrar_etq_tramos = g1.checkbox("Etiquetas de tramos", value=True, key=f"graf_{clave}_etq_tramos")
        mostrar_etq_eventos = g2.checkbox("Accesorios/transiciones", value=True, key=f"graf_{clave}_etq_eventos")
        mostrar_etq_equipos = g3.checkbox("Etiquetas de equipos", value=True, key=f"graf_{clave}_etq_equipos")
        mostrar_etq_le = g4.checkbox("Etiquetas en gráficas", value=False, key=f"graf_{clave}_etq_le")

        modo_perfil = st.radio(
            "Perfil vertical del sistema",
            [
                "Interpolar entre z1 y z2",
                "Definir elevación en cada unión",
            ],
            horizontal=True,
            key=f"graf_{clave}_modo_perfil",
        )

        z_nodos = [float(z1)]

        if len(tramos) > 1:
            if modo_perfil == "Definir elevación en cada unión":
                st.markdown("**Elevaciones de las uniones internas**")
                columnas = st.columns(min(3, len(tramos) - 1))

                for j in range(1, len(tramos)):
                    valor_default = float(z1) + (float(z2) - float(z1)) * j / len(tramos)
                    columna = columnas[(j - 1) % len(columnas)]

                    with columna:
                        z_union = entrada_dimensionada(
                            f"z en unión {j}", "longitud", value=float(valor_default),
                            format="%.4f", key=f"graf_{clave}_z_union_{j}",
                        )

                    z_nodos.append(float(z_union))
            else:
                for j in range(1, len(tramos)):
                    z_nodos.append(
                        float(z1) + (float(z2) - float(z1)) * j / len(tramos)
                    )

        z_nodos.append(float(z2))

        posicion_bomba = None
        posicion_turbina = None

        if (hA or 0.0) > 0 and total_L > 0:
            key_bomba = f"graf_{clave}_pos_bomba"
            if key_bomba not in st.session_state:
                st.session_state[key_bomba] = _desde(float(min(total_L * 0.05, total_L)), "longitud")
            else:
                st.session_state[key_bomba] = min(
                    max(float(st.session_state[key_bomba]), 0.0),
                    _desde(float(total_L), "longitud"),
                )

            posicion_bomba = entrada_dimensionada(
                "Posición de la bomba desde Punto 1", "longitud", min_value=0.0,
                max_value=float(total_L), value=float(min(total_L * 0.05, total_L)),
                format="%.4f", key=key_bomba,
                help=(
                    "Puede colocar la bomba al inicio, dentro de un tramo o en una unión. "
                    "Si el enunciado indicó su ubicación, este valor se autocompleta."
                ),
            )

        if (hR or 0.0) > 0 and total_L > 0:
            key_turbina = f"graf_{clave}_pos_turbina"
            if key_turbina not in st.session_state:
                st.session_state[key_turbina] = _desde(float(min(total_L * 0.75, total_L)), "longitud")
            else:
                st.session_state[key_turbina] = min(
                    max(float(st.session_state[key_turbina]), 0.0),
                    _desde(float(total_L), "longitud"),
                )

            posicion_turbina = entrada_dimensionada(
                "Posición de la turbina desde Punto 1", "longitud", min_value=0.0,
                max_value=float(total_L), value=float(min(total_L * 0.75, total_L)),
                format="%.4f", key=key_turbina,
                help=(
                    "Puede colocar la turbina al inicio, dentro de un tramo o en una unión. "
                    "Si el enunciado indicó su ubicación, este valor se autocompleta."
                ),
            )

        st.info(
            "La posición de cada accesorio se define dentro de su tramo con el campo "
            "'Posición (%)'. 0 % corresponde al inicio y 100 % al final del tramo."
        )

    with st.expander(
        "🧩 Esquema hidráulico del sistema",
        expanded=False,
    ):
        figura_esquema = crear_esquema_sistema(
            tramos=tramos,
            z1=z1,
            z2=z2,
            tipo_v1=tipo_v1,
            tipo_v2=tipo_v2,
            hA=hA or 0.0,
            hR=hR or 0.0,
            posicion_bomba=posicion_bomba,
            posicion_turbina=posicion_turbina,
            z_nodos=z_nodos,
            titulo=f"{titulo} — esquema hidráulico",
            transiciones=transiciones,
            mostrar_etiquetas_tramos=mostrar_etq_tramos,
            mostrar_etiquetas_accesorios=mostrar_etq_eventos,
            mostrar_etiquetas_transiciones=mostrar_etq_eventos,
            mostrar_etiquetas_equipos=mostrar_etq_equipos,
            mostrar_sentido_flujo=True,
        )
        st.pyplot(figura_esquema, clear_figure=True)
        st.caption(
            "Las distancias horizontales siguen las longitudes de los tramos. "
            "El perfil vertical utiliza z1, z2 y las elevaciones internas definidas."
        )

    with st.expander(
        "📈 LE / EGL y LAM / HGL",
        expanded=False,
    ):
        figura_energia = crear_lineas_energia(
            resultados=sistema["resultados"],
            gamma=gamma,
            P1=P1,
            z1=z1,
            P2=P2,
            z2=z2,
            V1=V1,
            V2=V2,
            hA=hA or 0.0,
            hR=hR or 0.0,
            tramos=tramos,
            posicion_bomba=posicion_bomba,
            posicion_turbina=posicion_turbina,
            titulo=f"{titulo} — líneas de energía",
            transiciones=transiciones,
            mostrar_marcadores_eventos=True,
            mostrar_etiquetas_eventos=mostrar_etq_le,
        )
        st.pyplot(figura_energia, clear_figure=True)
        st.caption(
            "La fricción se distribuye a lo largo de cada tramo. Bomba, turbina y "
            "pérdidas menores aparecen como cambios concentrados en la posición seleccionada."
        )

    with st.expander(
        "📉 V14.15 — Distribución acumulada de pérdidas",
        expanded=False,
    ):
        figura_perdidas = crear_perdidas_acumuladas_v1415(
            resultados=sistema["resultados"], tramos=tramos, transiciones=transiciones,
            hA=hA or 0.0, hR=hR or 0.0,
            posicion_bomba=posicion_bomba, posicion_turbina=posicion_turbina,
            mostrar_etiquetas_eventos=mostrar_etq_le,
            titulo=f"{titulo} — pérdidas acumuladas",
        )
        st.pyplot(figura_perdidas, clear_figure=True)
        perfil_v1415 = construir_perfil_perdidas_v1415(
            resultados=sistema["resultados"], tramos=tramos, transiciones=transiciones,
            hA=hA or 0.0, hR=hR or 0.0,
            posicion_bomba=posicion_bomba, posicion_turbina=posicion_turbina,
        )
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Σ hf", fmt_u(perfil_v1415["total_hf_m"], "carga", 5))
        c2.metric("Σ hm accesorios", fmt_u(perfil_v1415["total_hm_accesorios_m"], "carga", 5))
        c3.metric("Σ hm transiciones", fmt_u(perfil_v1415["total_hm_transiciones_m"], "carga", 5))
        c4.metric("hL total", fmt_u(perfil_v1415["hL_total_m"], "carga", 5))


# ============================================================
# SOLUCIONADOR CLASE I
# ============================================================

def render_clase_i():
    titulo_bloque(3, "Sistema y método — Clase I", "Configure el sistema; después aplique la ecuación general de energía.")
    st.write(
        "En Clase I el caudal y la geometría son conocidos. "
        "Se calculan las pérdidas y luego se aplica la ecuación general de energía."
    )

    rho, nu, gamma = selector_fluido("I")

    Q_I = entrada_dimensionada(
        "Caudal conocido Q", "caudal", min_value=0.000001, value=0.010000,
        format="%.6f", key="I_Q",
    )

    tramos_I = crear_tramos("I")
    transiciones_I = crear_transiciones("I", tramos_I)

    firma_actual = (
        round(Q_I, 12),
        round(rho, 8),
        round(nu, 15),
        tuple(
            (
                tramo["numero"],
                round(tramo["L"], 10),
                round(tramo["D"], 10),
                round(tramo["epsilon"], 12),
                round(tramo["K"], 10),
            )
            for tramo in tramos_I
        ),
        tuple(
            (t.get("entre"), t.get("tipo"), t.get("angulo_grados"))
            for t in transiciones_I
        ),
    )

    if st.button(
        "⚙️ CALCULAR PÉRDIDAS",
        type="primary",
        use_container_width=True,
        key="I_calcular_perdidas",
    ):
        try:
            sistema = calcular_sistema_con_transiciones(
                Q_I, tramos_I, nu, transiciones_I
            )
            st.session_state.resultado_clase_i_sistema = sistema
            st.session_state.firma_clase_i = firma_actual
        except Exception as error:
            st.error(f"Error: {error}")

    sistema = st.session_state.resultado_clase_i_sistema

    if sistema is None:
        return

    if st.session_state.firma_clase_i != firma_actual:
        st.warning(
            "Cambió algún dato desde el último cálculo. "
            "Pulse nuevamente CALCULAR PÉRDIDAS."
        )
        return

    with st.expander("🧮 Cálculos por tramo", expanded=False):
        st.dataframe(
            formatear_dataframe_resultados(sistema["resultados"]),
            use_container_width=True,
            hide_index=True,
        )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Σ hf", fmt_u(sistema["total_hf"], "carga", 6))
    c2.metric("Σ hm accesorios", fmt_u(sistema.get("total_hm_accesorios", sistema["total_hm"]), "carga", 6))
    c3.metric("Σ hm transiciones", fmt_u(sistema.get("total_hm_transiciones", 0.0), "carga", 6))
    c4.metric("hL total", fmt_u(sistema["hL_total"], "carga", 6))
    mostrar_resumen_transiciones(sistema)

    st.divider()
    titulo_bloque(4, "Método — ecuación general de energía")
    with st.expander("📘 Ver ecuación utilizada", expanded=False):
        st.latex(
            r"""
            \frac{P_1}{\gamma}+z_1+\frac{V_1^2}{2g}+h_A-h_R-h_L
            =
            \frac{P_2}{\gamma}+z_2+\frac{V_2^2}{2g}
            """
        )

    V_primero = sistema["resultados"][0]["V (m/s)"]
    V_ultimo = sistema["resultados"][-1]["V (m/s)"]

    e1, e2 = st.columns(2)

    with e1:
        opcion_v1 = st.selectbox(
            "Condición de velocidad en Punto 1",
            [
                "Usar velocidad de la tubería",
                "Superficie libre / depósito (V ≈ 0)",
                "Ingresar manualmente",
            ],
            key="I_opcion_v1",
        )
        V1 = obtener_velocidad_extremo_clase_i(
            opcion_v1,
            V_primero,
            "I_V1_manual",
        )

    with e2:
        opcion_v2 = st.selectbox(
            "Condición de velocidad en Punto 2",
            [
                "Usar velocidad de la tubería",
                "Superficie libre / depósito (V ≈ 0)",
                "Ingresar manualmente",
            ],
            key="I_opcion_v2",
        )
        V2 = obtener_velocidad_extremo_clase_i(
            opcion_v2,
            V_ultimo,
            "I_V2_manual",
        )

    incognita_label = st.selectbox(
        "¿Qué desea calcular?",
        [
            "Presión P2",
            "Presión P1",
            "Carga agregada por bomba hA",
            "Carga retirada hR",
            "Elevación z2",
            "Elevación z1",
        ],
        key="I_incognita",
    )

    mapa = {
        "Presión P2": "P2",
        "Presión P1": "P1",
        "Carga agregada por bomba hA": "hA",
        "Carga retirada hR": "hR",
        "Elevación z2": "z2",
        "Elevación z1": "z1",
    }

    incognita = mapa[incognita_label]

    d1, d2, d3 = st.columns(3)

    with d1:
        if incognita == "P1":
            st.text_input(
                f"P1 ({_u('presion')})",
                value="INCÓGNITA",
                disabled=True,
                key="I_P1_disabled",
            )
            P1_kpa = None
        else:
            P1_kpa = entrada_dimensionada(
                "P1 manométrica", "presion", value=0.0, format="%.4f", key="I_P1",
            )

        if incognita == "z1":
            st.text_input(
                f"z1 ({_u('longitud')})",
                value="INCÓGNITA",
                disabled=True,
                key="I_z1_disabled",
            )
            z1 = None
        else:
            z1 = entrada_dimensionada(
                "z1", "longitud", value=0.0, format="%.4f", key="I_z1",
            )

    with d2:
        if incognita == "P2":
            st.text_input(
                f"P2 ({_u('presion')})",
                value="INCÓGNITA",
                disabled=True,
                key="I_P2_disabled",
            )
            P2_kpa = None
        else:
            P2_kpa = entrada_dimensionada(
                "P2 manométrica", "presion", value=0.0, format="%.4f", key="I_P2",
            )

        if incognita == "z2":
            st.text_input(
                f"z2 ({_u('longitud')})",
                value="INCÓGNITA",
                disabled=True,
                key="I_z2_disabled",
            )
            z2 = None
        else:
            z2 = entrada_dimensionada(
                "z2", "longitud", value=0.0, format="%.4f", key="I_z2",
            )

    with d3:
        if incognita == "hA":
            st.text_input(
                f"hA ({_u('carga')})",
                value="INCÓGNITA",
                disabled=True,
                key="I_hA_disabled",
            )
            hA = None
        else:
            hA = entrada_dimensionada(
                "Carga de bomba hA", "carga", min_value=0.0, value=0.0,
                format="%.4f", key="I_hA",
            )

        if incognita == "hR":
            st.text_input(
                f"hR ({_u('carga')})",
                value="INCÓGNITA",
                disabled=True,
                key="I_hR_disabled",
            )
            hR = None
        else:
            hR = entrada_dimensionada(
                "Carga retirada hR", "carga", min_value=0.0, value=0.0,
                format="%.4f", key="I_hR",
            )

    eficiencia = st.number_input(
        "Eficiencia de bomba (%)",
        min_value=1.0,
        max_value=100.0,
        value=75.0,
        format="%.2f",
        key="I_eficiencia",
    )

    if st.button(
        "🧮 RESOLVER CLASE I",
        type="primary",
        use_container_width=True,
        key="I_resolver",
    ):
        try:
            P1 = None if P1_kpa is None else P1_kpa * 1000.0
            P2 = None if P2_kpa is None else P2_kpa * 1000.0

            valor = resolver_clase_i(
                incognita=incognita,
                P1=P1,
                P2=P2,
                z1=z1,
                z2=z2,
                V1=V1,
                V2=V2,
                hA=hA,
                hR=hR,
                hL=sistema["hL_total"],
                gamma=gamma,
            )

            P1_f, P2_f = P1, P2
            z1_f, z2_f = z1, z2
            hA_f, hR_f = hA, hR

            if incognita == "P1":
                P1_f = valor
            elif incognita == "P2":
                P2_f = valor
            elif incognita == "z1":
                z1_f = valor
            elif incognita == "z2":
                z2_f = valor
            elif incognita == "hA":
                hA_f = valor
            elif incognita == "hR":
                hR_f = valor

            residual = residuo_energia(
                P1=P1_f,
                P2=P2_f,
                z1=z1_f,
                z2=z2_f,
                V1=V1,
                V2=V2,
                hA=hA_f,
                hR=hR_f,
                hL=sistema["hL_total"],
                gamma=gamma,
            )

            mostrar_ruta_interfaz(etapa=5)
            titulo_bloque(5, "Resultados — Clase I")

            if incognita in ("P1", "P2"):
                st.metric(incognita_label, fmt_u(valor / 1000.0, "presion", 6))
            else:
                st.metric(incognita_label, fmt_u(valor, "carga", 6))

            st.metric("Residual de energía", fmt_u(residual, "carga", 10))

            if abs(residual) < 1e-7:
                st.success("✅ La ecuación de energía se satisface.")

            diagnosticos_I = validar_resultados_hidraulicos(
                sistema.get("resultados", []), residual=residual
            )
            mostrar_diagnosticos(
                diagnosticos_I,
                titulo="Verificación física y numérica — Clase I",
                expanded=any(d.get("nivel") in ("error", "warning") for d in diagnosticos_I),
            )

            auditoria_I_v148 = auditar_sistema_hidraulico(
                sistema, Q_referencia=Q_I, residual=residual, convergencia=True
            )
            mostrar_auditoria_v148(auditoria_I_v148, "Clase I")
            resultado_I_v149 = {
                "incognita": incognita,
                "valor": valor,
                "unidad": "Pa" if incognita in ("P1", "P2") else "m",
                "residual": residual,
                "Q_m3s": Q_I,
                "sistema": sistema,
            }
            contexto_I_v1416 = {
                "clase": "Clase I",
                "prefill": {
                    "fluido_app": st.session_state.get("I_fluido"),
                    "Q_m3s": Q_I, "P1_kpa": P1_kpa, "P2_kpa": P2_kpa,
                    "z1_m": z1, "z2_m": z2, "hA_m": hA, "hR_m": hR,
                    "tramos": [
                        {"L_m": t.get("L"), "D_m": t.get("D"), "material": t.get("material"), "epsilon_m": t.get("epsilon")}
                        for t in tramos_I
                    ],
                },
            }
            auditoria_I_v1416 = auditar_fisica(
                contexto_I_v1416, resultado_I_v149,
                propiedades_fluido={"nombre": st.session_state.get("I_fluido"), "rho": rho, "nu": nu, "gamma": gamma},
                auditoria_matematica=auditoria_I_v148,
            )
            mostrar_auditoria_fisica_v1416(auditoria_I_v1416, "Clase I")
            entrada_I_v149 = {
                "generales": {
                    "fluido_app": st.session_state.get("I_fluido"),
                    "Q_m3s": Q_I,
                    "P1_kpa": P1_kpa, "P2_kpa": P2_kpa,
                    "z1_m": z1, "z2_m": z2, "hA_m": hA, "hR_m": hR,
                },
                "tramos": [
                    {"L_m": t.get("L"), "D_m": t.get("D"), "material": t.get("material")}
                    for t in tramos_I
                ],
            }
            mostrar_reporte_final_v149(
                st.session_state.get("manifiesto_v149"),
                resultado_I_v149, auditoria_I_v148, "Clase I", entrada_I_v149, auditoria_I_v1416
            )

            if hA_f is not None and hA_f > 0:
                potencia_h = potencia_hidraulica_bomba(gamma, Q_I, hA_f)
                potencia_in = potencia_entrada_bomba(
                    gamma,
                    Q_I,
                    hA_f,
                    eficiencia / 100.0,
                )

                p1, p2 = st.columns(2)
                p1.metric("Potencia hidráulica", fmt_u(potencia_h / 1000.0, "potencia", 4))
                p2.metric("Potencia de entrada", fmt_u(potencia_in / 1000.0, "potencia", 4))

            mostrar_diagramas_solucion(
                tramos=tramos_I,
                sistema=sistema,
                gamma=gamma,
                P1=P1_f,
                z1=z1_f,
                P2=P2_f,
                z2=z2_f,
                V1=V1,
                V2=V2,
                hA=hA_f,
                hR=hR_f,
                tipo_v1=opcion_v1,
                tipo_v2=opcion_v2,
                titulo="Clase I",
                transiciones=sistema.get("transiciones_resultados"),
            )

        except Exception as error:
            st.error(f"Error: {error}")


# ============================================================
# SOLUCIONADOR CLASE II
# ============================================================

def render_clase_ii(clase_activa):
    metodo = clase_activa.replace("Clase ", "")
    titulo_bloque(3, f"Sistema y método — {metodo}", "Configure el sistema y ejecute el procedimiento correspondiente de Mott.")

    if metodo == "II-A":
        st.info(
            "II-A: el caudal es desconocido y las pérdidas menores se desprecian."
        )
    elif metodo == "II-B":
        st.info(
            "II-B: se parte de II-A y se corrige incorporando pérdidas menores."
        )
    else:
        st.info(
            "II-C: solución iterativa completa del caudal incluyendo pérdidas menores."
        )

    rho, nu, gamma = selector_fluido("II")
    tramos = crear_tramos("II")
    transiciones = crear_transiciones("II", tramos)

    K_sistema = sum(tramo["K"] for tramo in tramos)

    if metodo == "II-A" and any(t.get("tipo") != TIPO_SIN for t in transiciones):
        st.warning(
            "II-A desprecia pérdidas menores; las expansiones/contracciones configuradas "
            "se mostrarán, pero no se incluirán en el cálculo II-A."
        )

    if metodo == "II-A" and K_sistema > 0:
        st.warning(
            "II-A ignora los coeficientes K introducidos. "
            "Si desea incluirlos use II-B o II-C."
        )

    if metodo in ("II-B", "II-C") and K_sistema == 0:
        st.warning(
            "No hay pérdidas menores introducidas; el resultado tenderá a coincidir con II-A."
        )

    st.subheader("Condiciones en los extremos")
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### Punto 1")
        P1 = entrada_dimensionada(
            "P1 manométrica", "presion", value=0.0, format="%.4f", key="II_P1",
        )
        z1 = entrada_dimensionada(
            "z1", "longitud", value=10.0, format="%.4f", key="II_z1",
        )
        tipo_v1_label = st.selectbox(
            "Condición de velocidad",
            [
                "Superficie libre / depósito",
                "Velocidad de la tubería",
                "Velocidad manual",
            ],
            key="II_tipo_v1",
        )
        if tipo_v1_label == "Velocidad manual":
            V1_manual = entrada_dimensionada(
                "V1 manual", "velocidad", min_value=0.0, value=0.0,
                format="%.6f", key="II_V1_manual",
            )
        else:
            V1_manual = 0.0

    with c2:
        st.markdown("### Punto 2")
        P2 = entrada_dimensionada(
            "P2 manométrica", "presion", value=0.0, format="%.4f", key="II_P2",
        )
        z2 = entrada_dimensionada(
            "z2", "longitud", value=0.0, format="%.4f", key="II_z2",
        )
        tipo_v2_label = st.selectbox(
            "Condición de velocidad",
            [
                "Superficie libre / depósito",
                "Velocidad de la tubería",
                "Velocidad manual",
            ],
            key="II_tipo_v2",
        )
        if tipo_v2_label == "Velocidad manual":
            V2_manual = entrada_dimensionada(
                "V2 manual", "velocidad", min_value=0.0, value=0.0,
                format="%.6f", key="II_V2_manual",
            )
        else:
            V2_manual = 0.0

    mapa_velocidad = {
        "Superficie libre / depósito": "deposito",
        "Velocidad de la tubería": "tuberia",
        "Velocidad manual": "manual",
    }

    c1, c2 = st.columns(2)

    with c1:
        hA = entrada_dimensionada(
            "Carga agregada por bomba hA", "carga", min_value=0.0, value=0.0,
            format="%.4f", key="II_hA",
        )

    with c2:
        hR = entrada_dimensionada(
            "Carga retirada hR", "carga", min_value=0.0, value=0.0,
            format="%.4f", key="II_hR",
        )

    with st.expander("⚙️ Opciones avanzadas del solver", expanded=False):
        st.caption(
            "En modo normal el programa encuentra automáticamente un intervalo de caudal "
            "que encierre la solución. Active este modo solo si desea imponer límites manuales."
        )
        modo_avanzado_Q = st.checkbox(
            "Definir límites de Q manualmente",
            value=False,
            key="II_modo_avanzado_Q",
        )
        q1, q2 = st.columns(2)
        with q1:
            Q_min = entrada_dimensionada(
                "Q mínimo", "caudal", min_value=1e-10, value=0.000001,
                format="%.10f", key="II_Qmin", disabled=not modo_avanzado_Q,
            )
        with q2:
            Q_max = entrada_dimensionada(
                "Q máximo", "caudal", min_value=0.000001, value=1.0,
                format="%.6f", key="II_Qmax", disabled=not modo_avanzado_Q,
            )

    diagnosticos_II_pre = validar_clase_ii_previa(
        metodo=metodo,
        tramos=tramos,
        transiciones=transiciones,
        nu=nu,
        gamma=gamma,
        P1=P1 * 1000.0,
        P2=P2 * 1000.0,
        z1=z1,
        z2=z2,
        hA=hA,
        hR=hR,
        tipo_v1=mapa_velocidad[tipo_v1_label],
        tipo_v2=mapa_velocidad[tipo_v2_label],
        V1_manual=V1_manual,
        V2_manual=V2_manual,
    )
    bloqueo_II = mostrar_diagnosticos(
        diagnosticos_II_pre,
        titulo=f"Validación previa — {metodo}",
        expanded=hay_bloqueantes(diagnosticos_II_pre),
    )

    if st.button(
        f"🌊 RESOLVER {metodo}",
        type="primary",
        use_container_width=True,
        key="II_resolver",
        disabled=bloqueo_II,
    ):
        try:
            solucion = resolver_clase_ii_mott_v9(
                metodo=metodo,
                tramos=tramos,
                nu=nu,
                gamma=gamma,
                P1=P1 * 1000.0,
                P2=P2 * 1000.0,
                z1=z1,
                z2=z2,
                hA=hA,
                hR=hR,
                tipo_v1=mapa_velocidad[tipo_v1_label],
                tipo_v2=mapa_velocidad[tipo_v2_label],
                transiciones=transiciones,
                V1_manual=V1_manual,
                V2_manual=V2_manual,
                modo_avanzado=modo_avanzado_Q,
                Q_min=Q_min if modo_avanzado_Q else None,
                Q_max=Q_max if modo_avanzado_Q else None,
            )

            Q_sol = solucion["Q_final"]
            mostrar_ruta_interfaz(etapa=5)
            titulo_bloque(5, f"Resultados — {metodo}")

            r1, r2, r3 = st.columns(3)
            r1.metric("Caudal", fmt_u(Q_sol, "caudal", 6))
            r2.metric("Caudal SI", f"{Q_sol * 1000:.4f} L/s")
            r3.metric("Iteraciones", solucion["iteraciones"])

            info_mott_ii = solucion.get("mott_directo", {})
            if metodo in ("II-A", "II-B"):
                if info_mott_ii.get("aplicable"):
                    st.success(
                        "📘 Método Mott activado: la estimación II-A se obtuvo con "
                        "la Ec. (11-3) basada en Swamee–Jain."
                    )
                    m1, m2, m3 = st.columns(3)
                    m1.metric(
                        "Q por Mott Ec. 11-3",
                        fmt_u(info_mott_ii["Q"], "caudal", 6),
                    )
                    m2.metric(
                        "Q verificación numérica",
                        fmt_u(info_mott_ii["Q_numerico_verificacion"], "caudal", 6),
                    )
                    m3.metric(
                        "Diferencia",
                        f"{info_mott_ii['diferencia_porcentaje_vs_numerico']:.4f} %",
                    )
                    with st.expander("Ver cálculo directo II-A de Mott"):
                        st.write(f"**h_f disponible:** {info_mott_ii['h_f_disponible']:.8f} m")
                        st.write(f"**Área:** {info_mott_ii['A']:.8f} m²")
                        st.write(f"**Velocidad:** {fmt_u(info_mott_ii['V'], 'velocidad', 6)}")
                        st.write(f"**Re:** {info_mott_ii['Re']:,.0f}")
                        st.write(f"**Argumento del ln:** {info_mott_ii['argumento_log']:.10g}")
                        st.latex(
                            r"Q=-0.965D^2\sqrt{\frac{gDh_f}{L}}"
                            r"\ln\left[\frac{\varepsilon}{3.7D}+"
                            r"\frac{1.78\nu}{D\sqrt{gDh_f/L}}\right]"
                        )
                else:
                    st.info(
                        "📘 Ec. (11-3) no usada como solución directa en este caso: "
                        + str(info_mott_ii.get("motivo", "configuración no compatible"))
                    )

            with st.expander("🧮 Cálculos por tramo", expanded=False):
                st.dataframe(
                    formatear_dataframe_resultados(solucion["sistema"]["resultados"]),
                    use_container_width=True,
                    hide_index=True,
                )

            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Σ hf", fmt_u(solucion["sistema"]["total_hf"], "carga", 6))
            p2.metric("Σ hm accesorios", fmt_u(solucion["sistema"].get("total_hm_accesorios", solucion["sistema"]["total_hm"]), "carga", 6))
            p3.metric("Σ hm transiciones", fmt_u(solucion["sistema"].get("total_hm_transiciones", 0.0), "carga", 6))
            p4.metric("hL total", fmt_u(solucion["sistema"]["hL_total"], "carga", 6))
            mostrar_resumen_transiciones(solucion["sistema"])

            if metodo == "II-B":
                st.subheader("Proceso de corrección II-B")
                b1, b2, b3 = st.columns(3)
                b1.metric("Q inicial II-A", fmt_u(solucion["Q_IIA"], "caudal", 6))
                b2.metric("Q corregido", fmt_u(Q_sol, "caudal", 6))
                b3.metric(
                    "Corrección",
                    f"{solucion['correccion_porcentaje']:.3f} %",
                )

            if metodo == "II-A" and info_mott_ii.get("aplicable"):
                st.metric(
                    "Residual al comprobar Q de Mott con Colebrook",
                    f"{solucion['residual']:.12f} m",
                )
                diferencia = abs(info_mott_ii["diferencia_porcentaje_vs_numerico"])
                if diferencia <= 1.0:
                    st.success(
                        "✅ II-A de Mott verificado numéricamente: la diferencia con "
                        "la solución iterativa es menor o igual a 1 %."
                    )
                else:
                    st.warning(
                        "⚠️ La Ec. 11-3 y la verificación numérica difieren más de 1 %. "
                        "Revise propiedades, régimen y datos del sistema."
                    )
            else:
                st.metric("Residual de energía", fmt_u(solucion["residual"], "carga", 10))
                if abs(solucion["residual"]) < 1e-7:
                    st.success(f"✅ {metodo} convergió correctamente.")

            diagnosticos_II_post = validar_resultados_hidraulicos(
                solucion["sistema"].get("resultados", []),
                residual=solucion.get("residual"),
            )
            mostrar_diagnosticos(
                diagnosticos_II_post,
                titulo=f"Verificación física y numérica — {metodo}",
                expanded=any(d.get("nivel") in ("error", "warning") for d in diagnosticos_II_post),
            )

            auditoria_II_v148 = auditar_clase_ii_mott(solucion)
            mostrar_auditoria_v148(auditoria_II_v148, f"{metodo}")
            contexto_II_v1416 = {
                "clase": f"Clase {metodo}",
                "prefill": {
                    "fluido_app": st.session_state.get("II_fluido"),
                    "P1_kpa": P1, "P2_kpa": P2, "z1_m": z1, "z2_m": z2,
                    "hA_m": hA, "hR_m": hR,
                    "tramos": [
                        {"L_m": t.get("L"), "D_m": t.get("D"), "material": t.get("material"), "epsilon_m": t.get("epsilon"), "accesorios": t.get("accesorios_detalle") or []}
                        for t in tramos
                    ],
                    "transiciones": copy.deepcopy(transiciones or []),
                },
            }
            auditoria_II_v1416 = auditar_fisica(
                contexto_II_v1416, solucion,
                propiedades_fluido={"nombre": st.session_state.get("II_fluido"), "rho": rho, "nu": nu, "gamma": gamma},
                auditoria_matematica=auditoria_II_v148,
            )
            mostrar_auditoria_fisica_v1416(auditoria_II_v1416, f"{metodo}")
            entrada_II_v149 = {
                "generales": {
                    "fluido_app": st.session_state.get("II_fluido"),
                    "P1_kpa": P1, "P2_kpa": P2, "z1_m": z1, "z2_m": z2,
                    "hA_m": hA, "hR_m": hR,
                },
                "tramos": [
                    {"L_m": t.get("L"), "D_m": t.get("D"), "material": t.get("material")}
                    for t in tramos
                ],
            }
            mostrar_reporte_final_v149(
                st.session_state.get("manifiesto_v149"),
                solucion, auditoria_II_v148, metodo, entrada_II_v149, auditoria_II_v1416
            )

            intervalo_auto = solucion.get("intervalo_automatico")
            if intervalo_auto:
                st.caption(
                    "Intervalo usado por el solver: "
                    f"{intervalo_auto.get('Q_inf', 0):.8g} ≤ Q ≤ "
                    f"{intervalo_auto.get('Q_sup', 0):.8g} m³/s"
                )

            historial_q = solucion.get("historial_iteracion") or []
            if historial_q:
                with st.expander("📈 Ver proceso iterativo completo"):
                    st.caption(
                        "II-B incluye como iteración 0 la estimación II-A de Mott. "
                        "Las siguientes filas muestran la corrección automática hasta cerrar el residual."
                    )
                    df_hist = pd.DataFrame(historial_q)
                    st.dataframe(df_hist, use_container_width=True, hide_index=True)

            resultados_II = solucion["sistema"]["resultados"]
            V_tubo_1 = float(resultados_II[0]["V (m/s)"])
            V_tubo_2 = float(resultados_II[-1]["V (m/s)"])

            if mapa_velocidad[tipo_v1_label] == "deposito":
                V1_graf = 0.0
            elif mapa_velocidad[tipo_v1_label] == "manual":
                V1_graf = V1_manual
            else:
                V1_graf = V_tubo_1

            if mapa_velocidad[tipo_v2_label] == "deposito":
                V2_graf = 0.0
            elif mapa_velocidad[tipo_v2_label] == "manual":
                V2_graf = V2_manual
            else:
                V2_graf = V_tubo_2

            tramos_graf_II = tramos
            if metodo == "II-A":
                tramos_graf_II = [
                    {
                        **tramo,
                        "K": 0.0,
                        "accesorios_detalle": [],
                    }
                    for tramo in tramos
                ]

            mostrar_diagramas_solucion(
                tramos=tramos_graf_II,
                sistema=solucion["sistema"],
                gamma=gamma,
                P1=P1 * 1000.0,
                z1=z1,
                P2=P2 * 1000.0,
                z2=z2,
                V1=V1_graf,
                V2=V2_graf,
                hA=hA,
                hR=hR,
                tipo_v1=tipo_v1_label,
                tipo_v2=tipo_v2_label,
                titulo=metodo,
                transiciones=solucion["sistema"].get("transiciones_resultados"),
            )

        except Exception as error:
            st.error(f"Error al resolver {metodo}: {error}")


# ============================================================
# SOLUCIONADOR III-A
# ============================================================

def render_clase_iii_a():
    titulo_bloque(3, "Sistema y método — Clase III-A", "Calcule D mínimo con Mott y verifique numéricamente.")
    st.info(
        "Se calcula el diámetro hidráulico mínimo teórico. "
        "Luego se selecciona un tamaño comercial y se verifica mediante III-B."
    )

    rho, nu, gamma = selector_fluido("IIIA")

    c1, c2, c3 = st.columns(3)

    with c1:
        Q = entrada_dimensionada(
            "Caudal conocido Q", "caudal", min_value=0.000001, value=0.010000,
            format="%.6f", key="IIIA_Q",
        )

    with c2:
        L = entrada_dimensionada(
            "Longitud L", "longitud", min_value=0.01, value=50.0,
            format="%.4f", key="IIIA_L",
        )

    with c3:
        material = st.selectbox(
            "Material",
            list(MATERIALES.keys()),
            key="IIIA_material",
        )

    if material == "Personalizada":
        epsilon = entrada_dimensionada(
            "Rugosidad absoluta ε", "rugosidad", min_value=0.0, value=0.000046,
            format="%.8f", key="IIIA_epsilon",
        )
    else:
        epsilon = MATERIALES[material]
        st.info(f"ε = {fmt_u(epsilon, 'rugosidad', 8)}")
        info_material = MATERIALES_INFO.get(material)
        if info_material:
            st.caption(f"Fuente: {info_material['fuente']} — {info_material['descripcion']}")

    st.subheader("Condiciones de diseño")
    e1, e2 = st.columns(2)

    with e1:
        P1 = entrada_dimensionada(
            "P1 manométrica", "presion", value=0.0, format="%.4f", key="IIIA_P1",
        )
        z1 = entrada_dimensionada(
            "z1", "longitud", value=10.0, format="%.4f", key="IIIA_z1",
        )
        hA = entrada_dimensionada(
            "Carga de bomba hA", "carga", min_value=0.0, value=0.0,
            format="%.4f", key="IIIA_hA",
        )

    with e2:
        P2 = entrada_dimensionada(
            "P2 requerida", "presion", value=0.0, format="%.4f", key="IIIA_P2",
        )
        z2 = entrada_dimensionada(
            "z2", "longitud", value=0.0, format="%.4f", key="IIIA_z2",
        )
        hR = entrada_dimensionada(
            "Carga retirada hR", "carga", min_value=0.0, value=0.0,
            format="%.4f", key="IIIA_hR",
        )

    try:
        hL_permitida = carga_disponible_clase_iii_a(
            P1=P1 * 1000.0,
            P2=P2 * 1000.0,
            z1=z1,
            z2=z2,
            hA=hA,
            hR=hR,
            gamma=gamma,
        )

        st.metric("Carga disponible para pérdidas", fmt_u(hL_permitida, "carga", 6))

        st.subheader("Selección comercial posterior a III-A")
        catalogo_comercial = st.selectbox(
            "Catálogo para recomendar el siguiente tamaño comercial",
            ["No seleccionar automáticamente"] + list(CATALOGOS_TUBERIA.keys()),
            index=1 if material in ("Acero comercial", "Acero comercial o soldado") else 0,
            key="IIIA_catalogo_comercial",
            help=(
                "III-A calcula primero D mínimo teórico. Después se elige el primer diámetro "
                "interior real del catálogo que sea mayor o igual que Dmín."
            ),
        )

        with st.expander("⚙️ Opciones avanzadas de verificación numérica", expanded=False):
            st.caption(
                "El modo normal acota automáticamente el diámetro para la verificación con Colebrook."
            )
            modo_avanzado_D = st.checkbox(
                "Definir límites de D manualmente",
                value=False,
                key="IIIA_modo_avanzado_D",
            )
            d1, d2 = st.columns(2)
            with d1:
                D_min = entrada_dimensionada(
                    "D mínimo de búsqueda", "diametro", min_value=0.001, value=0.005,
                    format="%.5f", key="IIIA_Dmin", disabled=not modo_avanzado_D,
                )
            with d2:
                D_max = entrada_dimensionada(
                    "D máximo de búsqueda", "diametro", min_value=0.01, value=1.0,
                    format="%.4f", key="IIIA_Dmax", disabled=not modo_avanzado_D,
                )

        diagnosticos_IIIA_pre = validar_clase_iii_a_previa(
            Q=Q, L=L, epsilon=epsilon, nu=nu, hL_permitida=hL_permitida
        )
        bloqueo_IIIA = mostrar_diagnosticos(
            diagnosticos_IIIA_pre,
            titulo="Validación previa — III-A",
            expanded=hay_bloqueantes(diagnosticos_IIIA_pre),
        )

        if st.button(
            "📐 CALCULAR DIÁMETRO MÍNIMO",
            type="primary",
            use_container_width=True,
            key="IIIA_resolver",
            disabled=bloqueo_IIIA,
        ):
            resultado = resolver_clase_iii_a_mott_v9(
                Q=Q,
                L=L,
                epsilon=epsilon,
                nu=nu,
                hL_permitida=hL_permitida,
                catalogo_comercial=(
                    None if catalogo_comercial == "No seleccionar automáticamente"
                    else catalogo_comercial
                ),
                modo_avanzado=modo_avanzado_D,
                D_min=D_min if modo_avanzado_D else None,
                D_max=D_max if modo_avanzado_D else None,
            )

            st.session_state["resultado_III_A"] = resultado

            mostrar_ruta_interfaz(etapa=5)
            titulo_bloque(5, "Resultados — Clase III-A")
            st.success(
                "📘 Resultado principal calculado con el Método III-A de Mott, Ec. (11-8)."
            )

            a1, a2, a3 = st.columns(3)
            a1.metric("D mínimo — Mott", f"{resultado['D_mott']:.6f} m")
            a2.metric("D mínimo — Mott", f"{resultado['D_mott'] * 1000:.3f} mm")
            a3.metric("Velocidad con D de Mott", fmt_u(resultado["V"], "velocidad", 4))

            v1, v2, v3 = st.columns(3)
            v1.metric(
                "D por verificación numérica",
                f"{resultado['D_numerico_verificacion']:.6f} m",
            )
            v2.metric(
                "Diferencia Mott vs numérico",
                f"{resultado['diferencia_porcentaje_vs_numerico']:.4f} %",
            )
            v3.metric(
                "Iteraciones de verificación",
                resultado['iteraciones_verificacion'],
            )

            with st.expander("🧮 Detalle hidráulico con D de Mott", expanded=False):
                st.write(f"**Reynolds con D de Mott:** {resultado['Re']:,.0f}")
                st.write(f"**Régimen:** {resultado['regimen']}")
                st.write(f"**f de Darcy (verificación):** {resultado['f']:.6f}")
                st.write(f"**hf con D de Mott:** {resultado['hf']:.6f} m")
                st.write(
                    f"**Residual al comprobar D de Mott con Colebrook:** "
                    f"{resultado['residual']:.12f} m"
                )

            diagnosticos_IIIA_post = validar_resultados_hidraulicos(
                [{
                    "Re": resultado.get("Re"),
                    "f Darcy": resultado.get("f"),
                    "V (m/s)": resultado.get("V"),
                }],
                residual=resultado.get("residual"),
            )
            mostrar_diagnosticos(
                diagnosticos_IIIA_post,
                titulo="Verificación física y numérica — III-A",
                expanded=any(d.get("nivel") in ("error", "warning") for d in diagnosticos_IIIA_post),
            )

            auditoria_IIIA_v148 = auditar_clase_iii_a(resultado)
            mostrar_auditoria_v148(auditoria_IIIA_v148, "Clase III-A")
            contexto_IIIA_v1416 = {
                "clase": "Clase III-A",
                "prefill": {
                    "fluido_app": st.session_state.get("IIIA_fluido"),
                    "Q_m3s": Q, "P1_kpa": P1, "P2_kpa": P2,
                    "z1_m": z1, "z2_m": z2, "hA_m": hA, "hR_m": hR,
                    "tramos": [{"L_m": L, "D_m": None, "material": material, "epsilon_m": epsilon}],
                },
            }
            auditoria_IIIA_v1416 = auditar_fisica(
                contexto_IIIA_v1416, resultado,
                propiedades_fluido={"nombre": st.session_state.get("IIIA_fluido"), "rho": rho, "nu": nu, "gamma": gamma},
                auditoria_matematica=auditoria_IIIA_v148,
            )
            mostrar_auditoria_fisica_v1416(auditoria_IIIA_v1416, "Clase III-A")
            entrada_IIIA_v149 = {
                "generales": {
                    "fluido_app": st.session_state.get("IIIA_fluido"),
                    "Q_m3s": Q, "P1_kpa": P1, "P2_kpa": P2,
                    "z1_m": z1, "z2_m": z2, "hA_m": hA, "hR_m": hR,
                },
                "tramos": [{"L_m": L, "D_m": None, "material": material}],
            }
            mostrar_reporte_final_v149(
                st.session_state.get("manifiesto_v149"),
                resultado, auditoria_IIIA_v148, "Clase III-A", entrada_IIIA_v149, auditoria_IIIA_v1416
            )

            with st.expander("Ver términos de la Ec. (11-8) de Mott"):
                st.write(f"**L/(g·hL):** {resultado['L_sobre_ghL']:.12g}")
                st.write(f"**Término de rugosidad:** {resultado['termino_rugosidad']:.12e}")
                st.write(f"**Término de viscosidad:** {resultado['termino_viscosidad']:.12e}")
                st.write(f"**Argumento total:** {resultado['argumento']:.12e}")
                st.latex(
                    r"D=0.66\left[\varepsilon^{1.25}"
                    r"\left(\frac{LQ^2}{gh_L}\right)^{4.75}+"
                    r"\nu Q^{9.4}\left(\frac{L}{gh_L}\right)^{5.2}"
                    r"\right]^{0.04}"
                )

            if abs(resultado['diferencia_porcentaje_vs_numerico']) <= 1.0:
                st.success(
                    "✅ Método III-A de Mott verificado: la diferencia frente a la "
                    "solución iterativa con Colebrook es menor o igual a 1 %."
                )
            else:
                st.warning(
                    "⚠️ La Ec. 11-8 y la verificación numérica difieren más de 1 %. "
                    "Revise propiedades, rugosidad y régimen de flujo."
                )

            intervalo_D = resultado.get("intervalo_automatico")
            if intervalo_D:
                st.caption(
                    "Intervalo automático de verificación: "
                    f"{intervalo_D.get('D_inf', 0):.6g} ≤ D ≤ "
                    f"{intervalo_D.get('D_sup', 0):.6g} m"
                )

            historial_D = resultado.get("historial_iteracion") or []
            if historial_D:
                with st.expander("📈 Ver iteración de verificación del diámetro"):
                    st.dataframe(
                        pd.DataFrame(historial_D),
                        use_container_width=True,
                        hide_index=True,
                    )

            comercial = resultado.get("tamano_comercial")
            if comercial:
                st.subheader("Tamaño comercial recomendado")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("NPS", comercial["nps"] + ' in')
                c2.metric("DN", f"DN {comercial['dn']}")
                c3.metric("Diámetro interior real", f"{comercial['id_m']*1000:.1f} mm")
                c4.metric("Margen sobre Dmín", f"{comercial['margen_diametro_pct']:.2f} %")
                st.success(
                    "✅ Este es el primer tamaño del catálogo cuyo diámetro interior real "
                    "es mayor o igual que el diámetro mínimo de III-A."
                )
                if comercial.get("tamano_anterior"):
                    ant = comercial["tamano_anterior"]
                    st.caption(
                        f"El tamaño inmediatamente menor es NPS {ant['nps']} "
                        f"(ID={ant['id_m']*1000:.1f} mm), por lo que no alcanza Dmín."
                    )
            else:
                st.info(
                    "No se solicitó selección comercial automática. Puede elegir un catálogo "
                    "arriba o continuar a III-B con un diámetro interior conocido."
                )

            tramo_graf = {
                "numero": 1,
                "L": L,
                "D": resultado["D_minimo"],
                "material": material,
                "epsilon": epsilon,
                "K": 0.0,
                "accesorios_detalle": [],
            }

            sistema_graf = {
                "resultados": [
                    {
                        "Tramo": 1,
                        "L (m)": L,
                        "D (m)": resultado["D_minimo"],
                        "Material": material,
                        "ε (m)": epsilon,
                        "A (m²)": resultado["A"],
                        "V (m/s)": resultado["V"],
                        "Re": resultado["Re"],
                        "Régimen": resultado["regimen"],
                        "ε/D": resultado["rr"],
                        "f Darcy": resultado["f"],
                        "ΣK": 0.0,
                        "hf (m)": resultado["hf"],
                        "hm (m)": 0.0,
                    }
                ],
                "total_hf": resultado["hf"],
                "total_hm": 0.0,
                "hL_total": resultado["hf"],
            }

            mostrar_diagramas_solucion(
                tramos=[tramo_graf],
                sistema=sistema_graf,
                gamma=gamma,
                P1=P1 * 1000.0,
                z1=z1,
                P2=P2 * 1000.0,
                z2=z2,
                V1=resultado["V"],
                V2=resultado["V"],
                hA=hA,
                hR=hR,
                tipo_v1="tuberia",
                tipo_v2="tuberia",
                titulo="Clase III-A",
            )

    except Exception as error:
        st.error(f"Error III-A: {error}")


# ============================================================
# SOLUCIONADOR III-B
# ============================================================

def render_clase_iii_b():
    titulo_bloque(3, "Sistema y método — Clase III-B", "Verifique el diámetro comercial seleccionado con las pérdidas del sistema.")
    st.info(
        "Se verifica un diámetro interior comercial real, incluyendo pérdidas menores, "
        "y se comprueba la presión disponible en el punto final."
    )

    rho, nu, gamma = selector_fluido("IIIB")

    c1, c2, c3 = st.columns(3)

    with c1:
        Q = entrada_dimensionada(
            "Caudal conocido Q", "caudal", min_value=0.000001, value=0.010000,
            format="%.6f", key="IIIB_Q",
        )

    with c2:
        L = entrada_dimensionada(
            "Longitud L", "longitud", min_value=0.01, value=50.0,
            format="%.4f", key="IIIB_L",
        )

    with c3:
        material = st.selectbox(
            "Material",
            list(MATERIALES.keys()),
            key="IIIB_material",
        )

    if material == "Personalizada":
        epsilon = entrada_dimensionada(
            "Rugosidad absoluta ε", "rugosidad", min_value=0.0, value=0.000046,
            format="%.8f", key="IIIB_epsilon",
        )
    else:
        epsilon = MATERIALES[material]
        st.info(f"ε = {fmt_u(epsilon, 'rugosidad', 8)}")
        info_material = MATERIALES_INFO.get(material)
        if info_material:
            st.caption(f"Fuente: {info_material['fuente']} — {info_material['descripcion']}")

    D_default = 0.065
    D_minimo_previo = None

    if "resultado_III_A" in st.session_state:
        resultado_A = st.session_state["resultado_III_A"]
        if resultado_A:
            D_previo = float(resultado_A["D_minimo"])
            D_minimo_previo = D_previo
            comercial_previo = resultado_A.get("tamano_comercial")
            if comercial_previo:
                D_default = float(comercial_previo["id_m"])
                st.success(
                    f"III-A recomienda NPS {comercial_previo['nps']} / DN {comercial_previo['dn']} "
                    f"con diámetro interior real {D_default*1000:.1f} mm."
                )
            else:
                D_default = D_previo * 1.05
                st.info(
                    f"Último III-A: Dmín = {D_previo:.6f} m "
                    f"({D_previo * 1000:.2f} mm). No se seleccionó catálogo comercial."
                )

    modo_D_IIIB = st.radio(
        "Cómo desea definir el diámetro comercial",
        ["Usar diámetro recomendado/manual", "Elegir NPS desde catálogo de Mott"],
        horizontal=True,
        key="IIIB_modo_D",
    )

    if modo_D_IIIB == "Elegir NPS desde catálogo de Mott":
        cat_IIIB = st.selectbox(
            "Catálogo comercial",
            list(CATALOGOS_TUBERIA.keys()),
            key="IIIB_catalogo",
        )
        nps_opciones = opciones_nps(cat_IIIB)
        nps_default = 0
        comercial_previo = None
        if "resultado_III_A" in st.session_state and st.session_state["resultado_III_A"]:
            comercial_previo = st.session_state["resultado_III_A"].get("tamano_comercial")
        if comercial_previo and comercial_previo.get("catalogo") == cat_IIIB:
            try:
                nps_default = nps_opciones.index(comercial_previo["nps"])
            except ValueError:
                nps_default = 0
        nps_sel = st.selectbox(
            "Tamaño nominal NPS",
            nps_opciones,
            index=nps_default,
            key="IIIB_NPS",
        )
        fila_D = buscar_tamano_por_nps(cat_IIIB, nps_sel)
        D = float(fila_D["id_m"])
        st.info(
            f"NPS {fila_D['nps']} / DN {fila_D['dn']} → "
            f"diámetro interior real = {D*1000:.1f} mm; "
            f"OD = {fila_D['od_m']*1000:.1f} mm."
        )
    else:
        D = entrada_dimensionada(
            "Diámetro interior comercial real", "diametro", min_value=0.001,
            value=float(D_default), format="%.6f", key="IIIB_D",
        )

    if D_minimo_previo is not None:
        if D + 1e-12 < D_minimo_previo:
            st.error(
                f"❌ El diámetro seleccionado ({D*1000:.2f} mm) es menor que "
                f"Dmín de III-A ({D_minimo_previo*1000:.2f} mm). "
                "No debe recomendarse como tamaño comercial."
            )
        else:
            st.caption(
                f"✅ D seleccionado ≥ Dmín de III-A ({D_minimo_previo*1000:.2f} mm)."
            )

    st.subheader("Pérdidas menores")

    accesorios = st.multiselect(
        "Seleccione accesorios:",
        list(ACCESORIOS.keys()),
        key="IIIB_accesorios",
    )

    K_total = 0.0
    accesorios_detalle_IIIB = []

    st.caption(
        "Indique también la posición de cada accesorio para ubicarlo "
        "correctamente en el esquema y en la LE/LAM."
    )

    componentes_graficos_IIIB = st.session_state.get(
        "IIIB_componentes_graficos", []
    )
    if componentes_graficos_IIIB:
        for componente in componentes_graficos_IIIB:
            posicion_pct = 100.0 * float(
                componente.get("posicion_fraccion", 0.5) or 0.5
            )
            st.warning(
                f"Se detectó **{componente.get('nombre', 'componente')}** al "
                f"{posicion_pct:.1f}% de la tubería, pero su K no puede asignarse "
                "sin conocer el tipo. Seleccione el accesorio correcto o introduzca K adicional."
            )

    for accesorio in accesorios:
        ac1, ac2 = st.columns([3.2, 1])

        try:
            info_k = calcular_k_accesorio(accesorio, D, material)
            K_unitario = float(info_k["k"])
        except ValueError as error:
            st.error(str(error))
            K_unitario = 0.0
            info_k = {"descripcion": "K no disponible", "fuente": "—", "advertencia": None}

        with ac1:
            st.write(f"**{accesorio}**")
            st.caption(info_k["descripcion"])
            st.caption(f"Fuente: {info_k['fuente']}")

        with ac2:
            cantidad = st.number_input(
                "Cantidad",
                min_value=1,
                value=1,
                step=1,
                key=f"IIIB_cantidad_{accesorio}",
            )

        K_total += cantidad * K_unitario

        posiciones_pct = []
        if int(cantidad) == 1:
            posicion_pct = st.number_input(
                "Posición (%)",
                min_value=0.0,
                max_value=100.0,
                value=70.0,
                step=1.0,
                format="%.1f",
                key=f"IIIB_posicion_{accesorio}_1",
                help="0 % = inicio de la tubería; 100 % = final.",
            )
            posiciones_pct.append(float(posicion_pct))
        else:
            columnas_pos = st.columns(min(4, int(cantidad)))
            for n in range(1, int(cantidad) + 1):
                with columnas_pos[(n - 1) % len(columnas_pos)]:
                    posicion_pct = st.number_input(
                        f"Pos. {n} (%)",
                        min_value=0.0,
                        max_value=100.0,
                        value=float(min(70.0 + 5.0 * (n - 1), 100.0)),
                        step=1.0,
                        format="%.1f",
                        key=f"IIIB_posicion_{accesorio}_{n}",
                    )
                    posiciones_pct.append(float(posicion_pct))

        for posicion_pct in posiciones_pct:
            accesorios_detalle_IIIB.append(
                {
                    "nombre": accesorio,
                    "cantidad": 1,
                    "K_unitario": float(K_unitario),
                    "posicion_fraccion": float(posicion_pct) / 100.0,
                }
            )

    ke1, ke2 = st.columns([2, 1])

    with ke1:
        K_extra = st.number_input(
            "K adicional",
            min_value=0.0,
            value=0.0,
            format="%.4f",
            key="IIIB_Kextra",
        )

    with ke2:
        K_extra_pos_pct = st.number_input(
            "Posición K adicional (%)",
            min_value=0.0,
            max_value=100.0,
            value=85.0,
            step=1.0,
            format="%.1f",
            key="IIIB_Kextra_pos",
            disabled=K_extra <= 0,
        )

    K_total += K_extra

    st.metric("ΣK", f"{K_total:.4f}")

    st.subheader("Condiciones de diseño")
    e1, e2 = st.columns(2)

    with e1:
        P1 = entrada_dimensionada(
            "P1 manométrica", "presion", value=0.0, format="%.4f", key="IIIB_P1",
        )
        z1 = entrada_dimensionada(
            "z1", "longitud", value=10.0, format="%.4f", key="IIIB_z1",
        )
        hA = entrada_dimensionada(
            "Carga de bomba hA", "carga", min_value=0.0, value=0.0,
            format="%.4f", key="IIIB_hA",
        )

    with e2:
        P2_requerida = entrada_dimensionada(
            "P2 mínima requerida", "presion", value=0.0, format="%.4f", key="IIIB_P2",
        )
        z2 = entrada_dimensionada(
            "z2", "longitud", value=0.0, format="%.4f", key="IIIB_z2",
        )
        hR = entrada_dimensionada(
            "Carga retirada hR", "carga", min_value=0.0, value=0.0,
            format="%.4f", key="IIIB_hR",
        )

    v1c, v2c = st.columns(2)

    with v1c:
        tipo_v1_label = st.selectbox(
            "Velocidad en Punto 1",
            [
                "Velocidad de la tubería",
                "Superficie libre / depósito",
                "Velocidad manual",
            ],
            key="IIIB_tipo_v1",
        )

    with v2c:
        tipo_v2_label = st.selectbox(
            "Velocidad en Punto 2",
            [
                "Velocidad de la tubería",
                "Superficie libre / depósito",
                "Velocidad manual",
            ],
            key="IIIB_tipo_v2",
        )

    mapa = {
        "Velocidad de la tubería": "tuberia",
        "Superficie libre / depósito": "deposito",
        "Velocidad manual": "manual",
    }

    V1_manual = 0.0
    V2_manual = 0.0

    if tipo_v1_label == "Velocidad manual":
        V1_manual = entrada_dimensionada(
            "V1 manual", "velocidad", min_value=0.0, value=0.0,
            format="%.6f", key="IIIB_V1_manual",
        )

    if tipo_v2_label == "Velocidad manual":
        V2_manual = entrada_dimensionada(
            "V2 manual", "velocidad", min_value=0.0, value=0.0,
            format="%.6f", key="IIIB_V2_manual",
        )

    diagnosticos_IIIB_pre = validar_clase_iii_b_previa(
        D=D, Q=Q, L=L, epsilon=epsilon, nu=nu, D_minimo_previo=D_minimo_previo
    )
    bloqueo_IIIB = mostrar_diagnosticos(
        diagnosticos_IIIB_pre,
        titulo="Validación previa — III-B",
        expanded=hay_bloqueantes(diagnosticos_IIIB_pre),
    )

    if st.button(
        "✅ VERIFICAR DIÁMETRO III-B",
        type="primary",
        use_container_width=True,
        key="IIIB_resolver",
        disabled=bloqueo_IIIB,
    ):
        try:
            resultado = verificar_clase_iii_b(
                D_actual=D,
                Q=Q,
                L=L,
                epsilon=epsilon,
                nu=nu,
                K=K_total,
                gamma=gamma,
                P1=P1 * 1000.0,
                P2_deseada=P2_requerida * 1000.0,
                z1=z1,
                z2=z2,
                hA=hA,
                hR=hR,
                tipo_v1=mapa[tipo_v1_label],
                tipo_v2=mapa[tipo_v2_label],
                V1_manual=V1_manual,
                V2_manual=V2_manual,
            )

            mostrar_ruta_interfaz(etapa=5)
            titulo_bloque(5, "Resultados — Clase III-B")
            b1, b2, b3 = st.columns(3)
            b1.metric("P2 calculada", fmt_u(resultado["P2_calculada"] / 1000.0, "presion", 4))
            b2.metric("P2 mínima requerida", fmt_u(P2_requerida, "presion", 4))
            b3.metric("Margen de presión", fmt_u(resultado["margen_presion"] / 1000.0, "presion", 4))

            with st.expander("🧮 Detalle hidráulico de III-B", expanded=False):
                st.write(f"**Velocidad:** {fmt_u(resultado['V'], 'velocidad', 4)}")
                st.write(f"**Reynolds:** {resultado['Re']:,.0f}")
                st.write(f"**Régimen:** {resultado['regimen']}")
                st.write(f"**f de Darcy:** {resultado['f']:.6f}")
                st.write(f"**hf:** {fmt_u(resultado['hf'], 'carga', 6)}")
                st.write(f"**hm:** {fmt_u(resultado['hm'], 'carga', 6)}")
                st.write(f"**hL total:** {fmt_u(resultado['hL'], 'carga', 6)}")

            diagnosticos_IIIB_post = validar_resultados_hidraulicos(
                [{
                    "Re": resultado.get("Re"),
                    "f Darcy": resultado.get("f"),
                    "V (m/s)": resultado.get("V"),
                }],
                residual=None,
            )
            mostrar_diagnosticos(
                diagnosticos_IIIB_post,
                titulo="Verificación física — III-B",
                expanded=any(d.get("nivel") in ("error", "warning") for d in diagnosticos_IIIB_post),
            )

            auditoria_IIIB_v148 = auditar_clase_iii_b(
                resultado, P2_requerida_pa=P2_requerida * 1000.0
            )
            mostrar_auditoria_v148(auditoria_IIIB_v148, "Clase III-B")
            contexto_IIIB_v1416 = {
                "clase": "Clase III-B",
                "prefill": {
                    "fluido_app": st.session_state.get("IIIB_fluido"),
                    "Q_m3s": Q, "P1_kpa": P1, "P2_kpa": P2_requerida,
                    "z1_m": z1, "z2_m": z2, "hA_m": hA, "hR_m": hR,
                    "tramos": [{"L_m": L, "D_m": D, "material": material, "epsilon_m": epsilon}],
                },
            }
            auditoria_IIIB_v1416 = auditar_fisica(
                contexto_IIIB_v1416, resultado,
                propiedades_fluido={"nombre": st.session_state.get("IIIB_fluido"), "rho": rho, "nu": nu, "gamma": gamma},
                auditoria_matematica=auditoria_IIIB_v148,
            )
            mostrar_auditoria_fisica_v1416(auditoria_IIIB_v1416, "Clase III-B")
            entrada_IIIB_v149 = {
                "generales": {
                    "fluido_app": st.session_state.get("IIIB_fluido"),
                    "Q_m3s": Q, "P1_kpa": P1, "P2_kpa": P2_requerida,
                    "z1_m": z1, "z2_m": z2, "hA_m": hA, "hR_m": hR,
                },
                "tramos": [{"L_m": L, "D_m": D, "material": material}],
            }
            mostrar_reporte_final_v149(
                st.session_state.get("manifiesto_v149"),
                resultado, auditoria_IIIB_v148, "Clase III-B", entrada_IIIB_v149, auditoria_IIIB_v1416
            )

            if resultado["satisfactorio"]:
                st.success("✅ El diámetro comercial seleccionado cumple.")
            else:
                st.error(
                    "❌ El diámetro seleccionado no satisface la presión requerida. "
                    "Seleccione un tamaño comercial mayor."
                )

            if mapa[tipo_v1_label] == "deposito":
                V1_graf = 0.0
            elif mapa[tipo_v1_label] == "manual":
                V1_graf = V1_manual
            else:
                V1_graf = resultado["V"]

            if mapa[tipo_v2_label] == "deposito":
                V2_graf = 0.0
            elif mapa[tipo_v2_label] == "manual":
                V2_graf = V2_manual
            else:
                V2_graf = resultado["V"]

            tramo_graf = {
                "numero": 1,
                "L": L,
                "D": D,
                "material": material,
                "epsilon": epsilon,
                "K": K_total,
                "K_extra": K_extra,
                "K_extra_posicion_fraccion": float(K_extra_pos_pct) / 100.0,
                "accesorios_detalle": accesorios_detalle_IIIB,
                "componentes_graficos": componentes_graficos_IIIB,
            }

            sistema_graf = {
                "resultados": [
                    {
                        "Tramo": 1,
                        "L (m)": L,
                        "D (m)": D,
                        "Material": material,
                        "ε (m)": epsilon,
                        "A (m²)": resultado["A"],
                        "V (m/s)": resultado["V"],
                        "Re": resultado["Re"],
                        "Régimen": resultado["regimen"],
                        "ε/D": resultado["rr"],
                        "f Darcy": resultado["f"],
                        "ΣK": K_total,
                        "hf (m)": resultado["hf"],
                        "hm (m)": resultado["hm"],
                    }
                ],
                "total_hf": resultado["hf"],
                "total_hm": resultado["hm"],
                "hL_total": resultado["hL"],
            }

            mostrar_diagramas_solucion(
                tramos=[tramo_graf],
                sistema=sistema_graf,
                gamma=gamma,
                P1=P1 * 1000.0,
                z1=z1,
                P2=resultado["P2_calculada"],
                z2=z2,
                V1=V1_graf,
                V2=V2_graf,
                hA=hA,
                hR=hR,
                tipo_v1=tipo_v1_label,
                tipo_v2=tipo_v2_label,
                titulo="Clase III-B",
            )

        except Exception as error:
            st.error(f"Error III-B: {error}")


# ============================================================
# ENCABEZADO
# ============================================================

aplicar_estilo_interfaz()

st.title("💧 Calculadora de Sistemas de Tuberías en Serie")
st.caption(f"{APP_VERSION} · Mott 7.ª edición · flujo automático, auditorías, diagramas, reportes, procedimiento y comparador integrados.")
st.caption("Mecánica de Fluidos II · Robert L. Mott, 7.ª edición")
st.write(
    "Herramienta automatizada para identificar, interpretar, resolver y verificar "
    "sistemas de tuberías en serie con trazabilidad del método utilizado."
)

with st.sidebar:
    st.header("⚙️ Configuración")
    sistema_unidades = st.radio(
        "Sistema de unidades",
        [SISTEMA_SI, SISTEMA_US],
        horizontal=False,
        key="sistema_unidades",
        help="El motor hidráulico siempre calcula internamente en SI.",
    )
    if sistema_unidades == SISTEMA_US:
        unidad_caudal_us = st.selectbox(
            "Unidad de caudal US",
            [CAUDAL_US_GPM, CAUDAL_US_FT3S],
            key="unidad_caudal_us",
        )
    else:
        unidad_caudal_us = CAUDAL_US_GPM

    st.caption("Motor interno: SI · conversión automática de entrada y salida.")
    st.divider()
    if st.session_state.get("clase_activa"):
        st.markdown("**Clase activa**")
        st.success(st.session_state["clase_activa"])

prev_sistema = st.session_state.get("_sistema_unidades_prev", sistema_unidades)
prev_q_us = st.session_state.get("_unidad_caudal_us_prev", unidad_caudal_us)
if prev_sistema != sistema_unidades or (sistema_unidades == SISTEMA_US and prev_q_us != unidad_caudal_us):
    _reset_campos_dimensionales_por_cambio_unidades()
    st.session_state["_sistema_unidades_prev"] = sistema_unidades
    st.session_state["_unidad_caudal_us_prev"] = unidad_caudal_us
    st.info("Se reiniciaron los campos numéricos para evitar interpretar valores antiguos con unidades nuevas.")
else:
    st.session_state["_sistema_unidades_prev"] = sistema_unidades
    st.session_state["_unidad_caudal_us_prev"] = unidad_caudal_us

st.divider()


# ============================================================
# IDENTIFICACIÓN DEL PROBLEMA
# ============================================================

if st.session_state.clase_activa is None:
    mostrar_ruta_interfaz(etapa=1)
    titulo_bloque(1, "Problema e identificación", "Seleccione cómo desea identificar la clase hidráulica.")

    modo = st.radio(
        "¿Cómo desea identificar la clase?",
        [
            "🔍 Identificar automáticamente",
            "🧭 Ayúdame a identificarla",
            "✏️ Ya conozco la clase",
        ],
        key="modo_clasificacion",
    )

    if modo == "🔍 Identificar automáticamente":
        forma_entrada = st.radio(
            "¿Cómo desea ingresar el enunciado?",
            ["⌨️ Escribir o pegar", "📎 Subir archivo"],
            horizontal=True,
            key="modo_entrada_enunciado",
            help="V14.14 mantiene TXT, DOCX, PDF, PNG, JPG y JPEG. Para imágenes y PDF combina OCR espacial V14.3 con visión geométrica 2.0: recorrido poligonal, niveles relativos, perspectiva y símbolos, siempre sin convertir píxeles a magnitudes físicas.",
        )

        if forma_entrada == "📎 Subir archivo":
            archivo = st.file_uploader(
                "Suba el archivo del problema",
                type=[ext.lstrip(".") for ext in EXTENSIONES_SOPORTADAS],
                accept_multiple_files=False,
                key="archivo_enunciado",
                help="Formatos: TXT, DOCX, PDF, PNG, JPG y JPEG. En imágenes y PDF escaneados se aplica OCR automáticamente; V14.3 interpreta etiquetas/posiciones y V14.14 puede reconstruir geometría 2D del esquema con OpenCV. Límite interno: 20 MB.",
            )

            if archivo is not None:
                datos_archivo = archivo.getvalue()
                firma_archivo = hashlib.sha256(datos_archivo).hexdigest()

                if firma_archivo != st.session_state.get("archivo_enunciado_hash"):
                    try:
                        lectura = extraer_texto_archivo(archivo.name, datos_archivo)
                        st.session_state["archivo_enunciado_hash"] = firma_archivo
                        st.session_state["archivo_enunciado_info"] = lectura.como_dict()
                        st.session_state["archivo_enunciado_advertencias"] = list(lectura.advertencias or [])
                        st.session_state["enunciado_automatico"] = lectura.texto
                        st.session_state["texto_extraido_archivo_v1411"] = lectura.texto
                        st.session_state["ocr_revisado_v1411"] = False
                        st.session_state["resultado_auto"] = None
                        st.session_state["texto_analizado_auto"] = None
                        st.session_state["resultado_figura_v143"] = None
                        st.session_state["texto_figura_v143"] = ""
                        st.session_state["pagina_figura_v143"] = 1
                        st.session_state["figura_confirmada_v143"] = False
                        st.session_state["resultado_geometria_v144"] = None
                        st.session_state["geometria_aplicada_v144"] = False
                    except ErrorLecturaArchivo as error:
                        st.session_state["archivo_enunciado_hash"] = firma_archivo
                        st.session_state["archivo_enunciado_info"] = None
                        st.session_state["archivo_enunciado_advertencias"] = []
                        st.session_state["texto_extraido_archivo_v1411"] = ""
                        st.session_state["ocr_revisado_v1411"] = False
                        st.error(str(error))

                info_archivo = st.session_state.get("archivo_enunciado_info")
                if info_archivo:
                    columnas_info = st.columns(4)
                    columnas_info[0].metric("Archivo", info_archivo.get("nombre", "—"))
                    columnas_info[1].metric("Formato", str(info_archivo.get("extension", "—")).upper().lstrip("."))
                    columnas_info[2].metric("Caracteres", f"{info_archivo.get('caracteres', 0):,}")
                    paginas = info_archivo.get("paginas")
                    columnas_info[3].metric("Páginas", paginas if paginas is not None else "—")
                    st.caption(f"Método de lectura: {info_archivo.get('metodo', '—')}")
                    if info_archivo.get("ocr_aplicado"):
                        st.info("🔎 Se aplicó OCR. Revise cuidadosamente números, unidades y símbolos antes de analizar.")
                        st.session_state["ocr_revisado_v1411"] = st.checkbox(
                            "✅ He revisado completamente el texto OCR (números, unidades y símbolos)",
                            value=bool(st.session_state.get("ocr_revisado_v1411", False)),
                            key="ocr_revisado_control_v1411",
                            help="Márquelo solo después de comparar el texto extraído con la imagen/PDF original.",
                        )

                    for advertencia_archivo in st.session_state.get("archivo_enunciado_advertencias", []):
                        st.warning(advertencia_archivo)

                    if not str(info_archivo.get("caracteres", 0)).strip() or int(info_archivo.get("caracteres", 0) or 0) == 0:
                        st.error(
                            "No se obtuvo texto utilizable del archivo. "
                            "Si es una imagen o un PDF escaneado, revise si está borroso, inclinado o con poca resolución, "
                            "porque el OCR podría no reconocerlo correctamente."
                        )

                    # ----------------------------------------------------
                    # V14.3 — interpretación espacial opcional de figura
                    # ----------------------------------------------------
                    ext_fig = str(info_archivo.get("extension", "")).lower()
                    if ext_fig in (".png", ".jpg", ".jpeg", ".pdf"):
                        with st.expander("🧭 V14.3 — Interpretar figura / esquema hidráulico", expanded=False):
                            st.caption(
                                "Use esta opción cuando el archivo contenga un esquema hidráulico. "
                                "La app analiza etiquetas y posiciones relativas, pero no convierte píxeles a metros ni impone inferencias sin confirmación."
                            )

                            pagina_fig = 1
                            total_pag = int(info_archivo.get("paginas") or 1)
                            if ext_fig == ".pdf" and total_pag > 1:
                                pagina_fig = st.number_input(
                                    "Página del PDF que contiene el esquema",
                                    min_value=1,
                                    max_value=total_pag,
                                    value=min(int(st.session_state.get("pagina_figura_v143", 1)), total_pag),
                                    step=1,
                                    key="pagina_figura_selector_v143",
                                )
                            st.session_state["pagina_figura_v143"] = int(pagina_fig)

                            if st.button(
                                "🧭 ANALIZAR FIGURA / ESQUEMA",
                                key="analizar_figura_v143",
                                use_container_width=True,
                            ):
                                try:
                                    rf_obj = interpretar_figura_archivo(
                                        archivo.name,
                                        datos_archivo,
                                        pagina_pdf=int(pagina_fig),
                                    )
                                    st.session_state["resultado_figura_v143"] = rf_obj.como_dict()
                                    st.session_state["texto_figura_v143"] = rf_obj.texto_sugerido
                                    st.session_state["figura_confirmada_v143"] = False
                                except ErrorInterpretacionFigura as e:
                                    st.session_state["resultado_figura_v143"] = None
                                    st.session_state["texto_figura_v143"] = ""
                                    st.error(str(e))

                            rf = st.session_state.get("resultado_figura_v143")
                            if rf:
                                c1, c2, c3 = st.columns(3)
                                c1.metric("Página analizada", rf.get("pagina", "—"))
                                c2.metric("Hallazgos", len(rf.get("hallazgos", [])))
                                c3.metric("Confianza OCR espacial", f"{rf.get('confianza_global', 0):.1f} %")
                                if rf.get("orientacion"):
                                    st.info(f"Recorrido gráfico inferido: **{rf['orientacion']}**")

                                if st.session_state.get("figura_confirmada_v143"):
                                    st.success(
                                        "✅ Figura confirmada para V14.3.2. Sus datos estructurados se fusionarán "
                                        "al pulsar ANALIZAR PROBLEMA."
                                    )

                                for adv_fig in rf.get("advertencias", []):
                                    st.warning(adv_fig)

                                hall = rf.get("hallazgos", [])
                                if hall:
                                    filas_fig = []
                                    for h in hall:
                                        frac = h.get("fraccion_recorrido")
                                        filas_fig.append({
                                            "Tipo": h.get("tipo", ""),
                                            "Texto detectado": h.get("texto", ""),
                                            "Estado": h.get("estado", ""),
                                            "Confianza OCR (%)": round(float(h.get("confianza", 0)), 1),
                                            "x relativo": round(float(h.get("x_rel", 0)), 3),
                                            "y relativo": round(float(h.get("y_rel", 0)), 3),
                                            "% recorrido": (round(100.0 * float(frac), 1) if frac is not None else None),
                                        })
                                    st.dataframe(pd.DataFrame(filas_fig), use_container_width=True, hide_index=True)

                                texto_fig = st.text_area(
                                    "Interpretación sugerida por la figura — revise antes de agregar",
                                    value=st.session_state.get("texto_figura_v143", ""),
                                    height=180,
                                    key="texto_figura_editor_v143",
                                    help="Este texto NO se usa para calcular hasta que usted lo agregue explícitamente al enunciado.",
                                )
                                st.session_state["texto_figura_v143"] = texto_fig

                                if texto_fig.strip() and st.button(
                                    "➕ AGREGAR INTERPRETACIÓN DE FIGURA AL ENUNCIADO",
                                    key="agregar_figura_enunciado_v143",
                                    use_container_width=True,
                                ):
                                    # V14.3.2: se confirma la evidencia visual de forma estructurada.
                                    # No se duplica L/D/P/z dentro del texto OCR, evitando crear tramos
                                    # ficticios por repetir etiquetas que ya estaban en la imagen.
                                    st.session_state["texto_figura_v143"] = texto_fig.strip()
                                    st.session_state["figura_confirmada_v143"] = True
                                    st.session_state["resultado_auto"] = None
                                    st.session_state["texto_analizado_auto"] = None
                                    st.success(
                                        "Interpretación de figura confirmada. Al pulsar ANALIZAR PROBLEMA, "
                                        "V14.3.2 completará datos faltantes y posiciones gráficas sin duplicar tramos."
                                    )

                            # ----------------------------------------------------
                            # V14.4 — Reconocimiento geométrico del esquema (compatibilidad histórica)
                            # Token histórico: USAR GEOMETRÍA PARA REFINAR V14.3
                            # V14.14 — Visión geométrica 2.0
                            # ----------------------------------------------------
                            st.divider()
                            st.markdown("#### 🔷 V14.14 — Visión geométrica 2.0")
                            st.caption(
                                "Complementa V14.3 analizando la figura misma con OpenCV. "
                                "Busca el trazado principal, depósitos y símbolos simples como bomba o válvula. "
                                "No convierte píxeles a metros ni crea diámetros, longitudes, cotas o pérdidas."
                            )

                            if st.button(
                                "🔷 ANALIZAR VISIÓN GEOMÉTRICA 2.0",
                                key="analizar_geometria_v144",
                                use_container_width=True,
                            ):
                                try:
                                    rg_obj = analizar_geometria_archivo(
                                        archivo.name,
                                        datos_archivo,
                                        pagina_pdf=int(pagina_fig),
                                    )
                                    st.session_state["resultado_geometria_v144"] = rg_obj.como_dict()
                                    st.session_state["geometria_aplicada_v144"] = False
                                except ErrorVisionEsquema as e:
                                    st.session_state["resultado_geometria_v144"] = None
                                    st.session_state["geometria_aplicada_v144"] = False
                                    st.error(str(e))

                            rg = st.session_state.get("resultado_geometria_v144")
                            if rg:
                                tub = rg.get("tuberia_principal") or {}
                                dep_geo = list(rg.get("depositos") or [])
                                eq_geo = list(rg.get("equipos") or [])
                                camb_geo = list(rg.get("cambios_seccion") or [])

                                g1, g2, g3, g4 = st.columns(4)
                                g1.metric("Confianza geométrica", f"{float(rg.get('confianza_global', 0) or 0):.1f} %")
                                g2.metric("Depósitos candidatos", len(dep_geo))
                                g3.metric("Equipos candidatos", len(eq_geo))
                                g4.metric("Cambios de sección", len(camb_geo))

                                recorrido_v1414 = rg.get("recorrido_polilinea") or {}
                                perspectiva_v1414 = rg.get("perspectiva") or {}
                                calidad_v1414 = rg.get("calidad_imagen") or {}
                                niveles_v1414 = list(rg.get("niveles_relativos") or [])
                                cambios_nivel_v1414 = list(rg.get("cambios_nivel") or [])

                                if perspectiva_v1414.get("aplicada"):
                                    st.success(
                                        "📐 Perspectiva corregida antes del análisis · "
                                        f"confianza {float(perspectiva_v1414.get('confianza', 0) or 0):.1f}%"
                                    )
                                if calidad_v1414:
                                    st.caption(
                                        "Calidad visual heurística: "
                                        f"**{calidad_v1414.get('nivel', '—')}** · "
                                        f"nitidez={float(calidad_v1414.get('nitidez_laplaciana', 0) or 0):.1f} · "
                                        f"contraste={float(calidad_v1414.get('contraste_std', 0) or 0):.1f}"
                                    )

                                if recorrido_v1414:
                                    segs_v1414 = list(recorrido_v1414.get("segmentos") or [])
                                    st.info(
                                        "Recorrido poligonal V14.14: "
                                        f"**{len(segs_v1414)} segmento(s)**, "
                                        f"confianza **{float(recorrido_v1414.get('confianza', 0) or 0):.1f}%**. "
                                        "Las longitudes mostradas en píxeles sirven solo para geometría relativa."
                                    )
                                    if segs_v1414:
                                        st.dataframe(pd.DataFrame([{
                                            "Segmento": x.get("indice"),
                                            "Orientación": x.get("orientacion"),
                                            "Ángulo (°)": x.get("angulo_deg"),
                                            "% inicio": round(100*float(x.get("fraccion_inicio", 0) or 0), 1),
                                            "% fin": round(100*float(x.get("fraccion_fin", 0) or 0), 1),
                                            "Longitud geométrica (px)": x.get("longitud_px"),
                                        } for x in segs_v1414]), use_container_width=True, hide_index=True)

                                if niveles_v1414 or cambios_nivel_v1414:
                                    with st.expander("↕️ Niveles y cambios verticales relativos V14.14", expanded=False):
                                        if niveles_v1414:
                                            st.dataframe(pd.DataFrame(niveles_v1414), use_container_width=True, hide_index=True)
                                        if cambios_nivel_v1414:
                                            st.dataframe(pd.DataFrame(cambios_nivel_v1414), use_container_width=True, hide_index=True)
                                        st.caption("Estos niveles son relativos al dibujo. No sustituyen z1, z2 ni otras cotas físicas.")

                                if tub:
                                    st.info(
                                        "Trazado principal detectado: "
                                        f"ángulo **{float(tub.get('angulo_deg', 0) or 0):.2f}°**, "
                                        f"confianza **{float(tub.get('confianza', 0) or 0):.1f}%**. "
                                        "La línea representa orientación/recorrido, no una longitud física."
                                    )

                                if rg.get("orden"):
                                    st.write(
                                        "**Orden geométrico sugerido:** "
                                        + " → ".join(str(x).replace("_", " ").title() for x in rg.get("orden", []))
                                    )

                                img_anotada = rg.get("imagen_anotada_png")
                                if img_anotada:
                                    st.image(
                                        img_anotada,
                                        caption="V14.14 — recorrido y detecciones geométricas para revisión",
                                        use_container_width=True,
                                    )

                                filas_geo = []
                                for item in dep_geo + eq_geo:
                                    frac = item.get("fraccion_recorrido")
                                    filas_geo.append({
                                        "Tipo": item.get("tipo", ""),
                                        "Estado": item.get("estado", "Confirmar"),
                                        "Confianza (%)": round(float(item.get("confianza", 0) or 0), 1),
                                        "x relativo": round(float(item.get("x_rel", 0) or 0), 3),
                                        "y relativo": round(float(item.get("y_rel", 0) or 0), 3),
                                        "% recorrido": round(100.0 * float(frac), 1) if frac is not None else None,
                                        "Detalle": item.get("detalle", ""),
                                    })
                                for item in camb_geo:
                                    frac = item.get("fraccion_recorrido")
                                    filas_geo.append({
                                        "Tipo": "cambio_seccion",
                                        "Estado": item.get("estado", "Confirmar"),
                                        "Confianza (%)": round(float(item.get("confianza", 0) or 0), 1),
                                        "x relativo": None,
                                        "y relativo": None,
                                        "% recorrido": round(100.0 * float(frac), 1) if frac is not None else None,
                                        "Detalle": item.get("detalle", ""),
                                    })
                                if filas_geo:
                                    st.dataframe(pd.DataFrame(filas_geo), use_container_width=True, hide_index=True)

                                for adv_geo in rg.get("advertencias", []):
                                    st.warning(adv_geo)

                                if st.session_state.get("geometria_aplicada_v144"):
                                    st.success(
                                        "✅ La geometría V14.14 ya fue fusionada con la evidencia V14.3. "
                                        "Al analizar el problema se usarán únicamente esos hallazgos confirmados, "
                                        "sin convertir píxeles a magnitudes físicas."
                                    )

                                if st.button(
                                    "✅ USAR V14.14 PARA REFINAR V14.3",
                                    key="usar_geometria_refinar_v143",
                                    use_container_width=True,
                                ):
                                    figura_base = st.session_state.get("resultado_figura_v143") or {
                                        "nombre": archivo.name,
                                        "pagina": int(pagina_fig),
                                        "ancho": int(rg.get("ancho", 0) or 0),
                                        "alto": int(rg.get("alto", 0) or 0),
                                        "hallazgos": [],
                                        "orientacion": None,
                                        "confianza_global": 0.0,
                                        "texto_sugerido": "",
                                        "advertencias": [],
                                        "lineas_ocr": [],
                                    }
                                    figura_refinada = fusionar_figura_con_geometria(figura_base, rg)
                                    st.session_state["resultado_figura_v143"] = figura_refinada
                                    # El clic constituye una confirmación explícita para usar la evidencia
                                    # geométrica como complemento estructurado. Los valores físicos siguen
                                    # dependiendo del OCR/texto y nunca se derivan de píxeles.
                                    st.session_state["figura_confirmada_v143"] = True
                                    st.session_state["geometria_aplicada_v144"] = True
                                    st.session_state["resultado_auto"] = None
                                    st.session_state["texto_analizado_auto"] = None
                                    st.success(
                                        "Geometría V14.14 fusionada con V14.3. Pulse ANALIZAR PROBLEMA para "
                                        "recalcular la interpretación con la evidencia confirmada."
                                    )
            else:
                st.caption("Seleccione un TXT, DOCX, PDF, PNG, JPG o JPEG. V14.14 permite combinar OCR espacial y visión geométrica 2.0 opcional en imágenes/PDF.")

        enunciado = st.text_area(
            "Texto del problema — revise y edite antes de analizar:",
            height=260,
            placeholder=(
                "Ejemplo: Agua a 20 °C fluye desde un depósito por una tubería "
                "de acero comercial de 80 m de longitud y 75 mm de diámetro. "
                "Determine el caudal. Desprecie las pérdidas menores."
            ),
            key="enunciado_automatico",
            help="El clasificador analiza exactamente el texto que aparece en este cuadro. Puede corregir cualquier símbolo, número o unidad antes de continuar.",
        )

        if st.button(
            "🔍 ANALIZAR PROBLEMA",
            type="primary",
            use_container_width=True,
            key="analizar_auto",
        ):
            if not enunciado.strip():
                st.error("Escriba, pegue o cargue un enunciado antes de analizar.")
                st.session_state.resultado_auto = None
                st.session_state.texto_analizado_auto = None
            else:
                resultado_nuevo = identificar_clase_automaticamente(enunciado)

                # V14.3.2: si el usuario confirmó la figura, la evidencia espacial
                # completa únicamente los datos que el OCR textual no pudo recuperar.
                # No reemplaza silenciosamente valores explícitos en conflicto.
                if (
                    st.session_state.get("figura_confirmada_v143")
                    and st.session_state.get("resultado_figura_v143")
                ):
                    resultado_nuevo = fusionar_resultado_con_figura(
                        resultado_nuevo,
                        st.session_state.get("resultado_figura_v143"),
                    )

                # V14.5 — expediente único después de texto/OCR/figura/geometría.
                # Aplica solo inferencias físicas inequívocas y genera la lista exacta
                # de datos que todavía faltan para la clase detectada.
                resultado_nuevo = consolidar_resultado(resultado_nuevo, enunciado)

                st.session_state.resultado_auto = resultado_nuevo
                st.session_state.texto_analizado_auto = enunciado
                st.session_state.enunciado_confirmado_auto = enunciado
                st.session_state.resultado_flujo_v1410 = None
                st.session_state.error_flujo_v1410 = None
                st.session_state.manifiesto_v149 = None
                st.session_state.transferencia_v147_confirmada = None

        resultado = st.session_state.resultado_auto
        if resultado is not None and st.session_state.get("texto_analizado_auto") != enunciado:
            st.info(
                "El texto cambió después del último análisis. Pulse **ANALIZAR PROBLEMA** nuevamente "
                "para actualizar la clasificación y los datos detectados."
            )
            resultado = None

        if resultado is not None:
            if resultado.get("clase"):
                st.success(f"Clase sugerida: **{resultado['clase']}**")
                st.progress(
                    min(max(resultado["confianza"], 0), 100) / 100.0
                )
                st.write(f"Confianza estimada: **{resultado['confianza']} %**")

                for razon in resultado.get("razones", []):
                    st.write(f"✓ {razon}")

                for advertencia in resultado.get("advertencias", []):
                    # Las advertencias específicas de autollenado también
                    # aparecen dentro del resumen, pero es preferible que sean visibles.
                    st.warning(advertencia)

                auditoria_auto = mostrar_datos_detectados(resultado, enunciado)
                mostrar_normalizaciones_v1412(resultado)
                mostrar_componentes_v1413(resultado)
                expediente_auto = mostrar_expediente_v145(resultado)
                resultado = mostrar_completado_v146(resultado, enunciado)
                expediente_auto = (resultado or {}).get("expediente_v145") or expediente_auto

                # V14.11 — confianza heurística individual por dato. El origen del
                # texto importa: OCR sin revisión requiere confirmación dirigida,
                # mientras que respuestas V14.6 e inferencias seguras quedan trazadas
                # con confianza alta.
                contexto_v1411 = {
                    "modo_entrada": forma_entrada,
                    "archivo_info": st.session_state.get("archivo_enunciado_info") if forma_entrada == "📎 Subir archivo" else None,
                    "texto_extraido_original": st.session_state.get("texto_extraido_archivo_v1411", "") if forma_entrada == "📎 Subir archivo" else "",
                    "ocr_revisado_explicito": bool(st.session_state.get("ocr_revisado_v1411", False)) if forma_entrada == "📎 Subir archivo" else False,
                }
                figura_v1411 = (
                    st.session_state.get("resultado_figura_v143")
                    if st.session_state.get("figura_confirmada_v143") else None
                )
                resultado, confianza_v1411 = mostrar_confianza_v1411(
                    resultado, enunciado, contexto_lectura=contexto_v1411, figura=figura_v1411
                )
                st.session_state.resultado_auto = resultado

                diagnosticos_texto = detectar_atmosfera_y_conflictos(
                    enunciado, resultado.get("prefill", {})
                )
                bloqueo_texto = mostrar_diagnosticos(
                    diagnosticos_texto,
                    titulo="Coherencia física del enunciado",
                    expanded=hay_bloqueantes(diagnosticos_texto),
                )
                bloqueo_auditoria = hay_conflictos_bloqueantes(auditoria_auto)
                if bloqueo_auditoria:
                    st.error(
                        "❌ Se detectaron valores explícitos incompatibles para una misma variable. "
                        "Corrija o confirme el enunciado antes de autocompletar."
                    )

                usar_prefill = st.checkbox(
                    "Autocompletar los campos con los datos detectados",
                    value=True,
                    key="usar_prefill_auto",
                    help=(
                        "Los valores detectados y las respuestas V14.6 se colocan en el "
                        "solucionador. Revise siempre los campos antes de calcular."
                    ),
                )

                faltan_v146 = bool((expediente_auto or {}).get("cantidad_faltantes", 0))
                bloqueo_confianza_v1411 = bool(
                    usar_prefill and not bool((confianza_v1411 or {}).get("listo_para_v147"))
                )
                # Compatibilidad de regresión V14.6: (usar_prefill and faltan_v146)
                preview_v147 = None
                confirmada_v147 = False

                if usar_prefill and faltan_v146:
                    st.info(
                        "Complete las preguntas V14.6 para transferir automáticamente el expediente. "
                        "Si prefiere completar el solucionador manualmente, desactive el autollenado."
                    )
                elif usar_prefill and bloqueo_confianza_v1411:
                    st.info(
                        "Confirme los datos de confianza media/baja marcados por V14.11 antes de abrir V14.7."
                    )
                elif usar_prefill and not (bloqueo_texto or bloqueo_auditoria):
                    preview_v147, confirmada_v147 = mostrar_previsualizacion_v147(
                        resultado, enunciado
                    )

                bloquear_v147 = bool(
                    usar_prefill
                    and (
                        faltan_v146
                        or bloqueo_confianza_v1411
                        or not preview_v147
                        or not preview_v147.get("listo_para_transferir")
                        or not confirmada_v147
                    )
                )

                if usar_prefill and preview_v147 and preview_v147.get("listo_para_transferir") and not confirmada_v147:
                    st.info(
                        "Revise V14.7 y marque la confirmación antes de transferir los datos al solucionador."
                    )

                modo_auto_v1410 = st.checkbox(
                    "⚡ V14.10 — Después de confirmar, resolver → auditar → generar reporte automáticamente",
                    key="modo_automatico_v1410",
                    disabled=not usar_prefill,
                    help=(
                        "No omite V14.7. Solo automatiza lo que ocurre después de revisar y confirmar "
                        "el snapshot. Puede abrir el solucionador manual después de la ejecución."
                    ),
                )

                if usar_prefill and preview_v147:
                    try:
                        estado_pre_v1410 = construir_estado_flujo(
                            resultado, enunciado, preview_v147,
                            preview_v147.get("firma") if confirmada_v147 else None,
                        )
                        mostrar_progreso_v1410(estado_pre_v1410)
                    except Exception as error_v1410_estado:
                        st.warning(f"V14.10 no pudo preparar el estado del flujo: {error_v1410_estado}")

                texto_boton_auto = (
                    "🚀 CONFIRMAR Y RESOLVER TODO"
                    if usar_prefill and modo_auto_v1410
                    else "✅ USAR CLASIFICACIÓN Y CONTINUAR"
                )
                if st.button(
                    texto_boton_auto,
                    type="primary",
                    use_container_width=True,
                    key="confirmar_auto",
                    disabled=bool(
                        bloqueo_texto or bloqueo_auditoria or bloquear_v147
                    ),
                ):
                    st.session_state.clase_activa = resultado["clase"]

                    if usar_prefill:
                        # Se reconstruye la vista justo antes de transferir para impedir
                        # que una confirmación antigua se aplique a datos modificados.
                        preview_final = construir_previsualizacion_transferencia(
                            resultado, enunciado
                        )
                        if not preview_final.get("listo_para_transferir"):
                            st.error(
                                "V14.7 detectó que el expediente cambió o dejó de estar listo. "
                                "Revise la previsualización antes de continuar."
                            )
                            st.stop()
                        aplicar_autollenado(
                            resultado["clase"],
                            resultado.get("prefill", {}),
                        )
                        st.session_state.transferencia_v147_confirmada = {
                            "version": VERSION_TRANSFERENCIA,
                            "firma": preview_final.get("firma"),
                            "clase": resultado.get("clase"),
                        }
                        st.session_state.manifiesto_v149 = construir_manifiesto_ejecucion(
                            resultado, enunciado, preview_final
                        )

                        if modo_auto_v1410:
                            try:
                                flujo_v1410 = resolver_flujo_confirmado(
                                    resultado=resultado,
                                    enunciado=enunciado,
                                    previsualizacion=preview_final,
                                    firma_confirmada=preview_final.get("firma"),
                                    manifiesto=st.session_state.manifiesto_v149,
                                )
                                st.session_state.resultado_flujo_v1410 = flujo_v1410
                                st.session_state.error_flujo_v1410 = None
                                st.session_state.mostrar_solver_manual_v1410 = False
                            except ErrorFlujoV1410 as error_v1410:
                                st.session_state.resultado_flujo_v1410 = None
                                st.session_state.error_flujo_v1410 = str(error_v1410)
                                st.session_state.mostrar_solver_manual_v1410 = True
                            except Exception as error_v1410:
                                st.session_state.resultado_flujo_v1410 = None
                                st.session_state.error_flujo_v1410 = f"Error inesperado V14.10: {error_v1410}"
                                st.session_state.mostrar_solver_manual_v1410 = True
                        else:
                            st.session_state.resultado_flujo_v1410 = None
                            st.session_state.error_flujo_v1410 = None

                    st.rerun()

            else:
                st.warning(
                    "No se pudo identificar la clase con suficiente seguridad."
                )
                for advertencia in resultado.get("advertencias", []):
                    st.write(f"• {advertencia}")

    elif modo == "🧭 Ayúdame a identificarla":
        incognita = st.selectbox(
            "¿Cuál es la principal incógnita?",
            [
                "Seleccione...",
                "Caudal",
                "Diámetro",
                "Presión",
                "Pérdida de carga",
                "Potencia de bomba",
                "Elevación",
                "Otra",
            ],
            key="guiado_incognita",
        )

        perdidas = "No sé / no aplica"
        objetivo_diametro = "No aplica"

        if incognita == "Caudal":
            perdidas = st.selectbox(
                "¿Cómo se consideran las pérdidas menores?",
                [
                    "No sé / no aplica",
                    "No existen / se despreciarán",
                    "Existen pero son relativamente pequeñas",
                    "Son importantes / usar solución completa",
                ],
                key="guiado_perdidas",
            )

        elif incognita == "Diámetro":
            objetivo_diametro = st.selectbox(
                "¿Qué desea hacer?",
                [
                    "No estoy seguro",
                    "Calcular diámetro mínimo teórico",
                    "Verificar un diámetro comercial ya seleccionado",
                ],
                key="guiado_objetivo_D",
            )

        if incognita != "Seleccione...":
            if st.button(
                "🧭 IDENTIFICAR CLASE",
                type="primary",
                use_container_width=True,
                key="identificar_guiado",
            ):
                st.session_state.resultado_guiado = identificar_clase_guiada(
                    incognita=incognita,
                    perdidas_menores=perdidas,
                    objetivo_diametro=objetivo_diametro,
                )

        resultado = st.session_state.resultado_guiado

        if resultado is not None and resultado.get("clase"):
            st.success(f"Clase identificada: **{resultado['clase']}**")
            st.write(f"Confianza: **{resultado['confianza']} %**")

            for razon in resultado.get("razones", []):
                st.write(f"✓ {razon}")

            if st.button(
                "✅ USAR ESTA CLASE",
                type="primary",
                use_container_width=True,
                key="usar_guiada",
            ):
                st.session_state.clase_activa = resultado["clase"]
                st.rerun()

    else:
        clase_manual = st.selectbox(
            "Seleccione la clase:",
            [
                "Clase I",
                "Clase II-A",
                "Clase II-B",
                "Clase II-C",
                "Clase III-A",
                "Clase III-B",
            ],
            key="clase_manual",
        )

        if st.button(
            "✅ USAR CLASE SELECCIONADA",
            type="primary",
            use_container_width=True,
            key="usar_manual",
        ):
            st.session_state.clase_activa = clase_manual
            st.rerun()



# ============================================================
# CLASE ACTIVA
# ============================================================

st.divider()

if st.session_state.clase_activa is None:
    st.info(
        "Identifique o seleccione una clase para abrir el solucionador correspondiente."
    )
    st.stop()

clase_activa = st.session_state.clase_activa

mostrar_ruta_interfaz(etapa=4)

c1, c2 = st.columns([5, 1])
with c1:
    st.markdown(
        f'<div class="mott-class-card"><b>🎯 Clase activa:</b> {clase_activa} &nbsp;·&nbsp; '
        f'<b>Unidades:</b> {_sistema_ui()}</div>',
        unsafe_allow_html=True,
    )
with c2:
    if st.button(
        "🔄 Cambiar clase",
        use_container_width=True,
        key="cambiar_clase",
    ):
        st.session_state.clase_activa = None
        st.session_state.resultado_auto = None
        st.session_state.resultado_guiado = None
        st.session_state.resultado_clase_i_sistema = None
        st.session_state.firma_clase_i = None
        st.session_state.transferencia_v147_confirmada = None
        st.session_state.manifiesto_v149 = None
        st.session_state.resultado_flujo_v1410 = None
        st.session_state.error_flujo_v1410 = None
        st.session_state.mostrar_solver_manual_v1410 = False
        st.rerun()

with st.expander("📄 1–2. Problema y datos interpretados", expanded=False):
    texto_original = (
        st.session_state.get("enunciado_automatico", "")
        or st.session_state.get("enunciado_confirmado_auto", "")
    )
    if texto_original:
        st.markdown("**Enunciado cargado**")
        st.write(texto_original)
    else:
        st.caption("La clase se seleccionó de forma guiada o manual; no hay un enunciado pegado en esta sesión.")
    if st.session_state.get("resultado_auto"):
        rauto = st.session_state["resultado_auto"]
        st.caption(
            f"Clasificación automática: {rauto.get('clase', '—')} · "
            f"confianza {rauto.get('confianza', '—')} %"
        )

if st.session_state.prefill_mensaje:
    st.success(
        "✅ Se cargaron automáticamente los datos reconocidos del enunciado. "
        "Revise los campos antes de resolver, especialmente propiedades del fluido, "
        "accesorios y condiciones de frontera."
    )
    st.session_state.prefill_mensaje = False

mostrar_manifiesto_v149(st.session_state.get("manifiesto_v149"))


# ============================================================
# RUTEO AL SOLUCIONADOR CORRESPONDIENTE
# ============================================================

flujo_v1410_actual = st.session_state.get("resultado_flujo_v1410")
error_v1410_actual = st.session_state.get("error_flujo_v1410")

if error_v1410_actual:
    st.warning(
        "⚠️ V14.10 no pudo completar la ejecución automática y dejó disponible el modo manual. "
        f"Motivo: {error_v1410_actual}"
    )

if flujo_v1410_actual and flujo_v1410_actual.get("clase") == clase_activa:
    mostrar_resultado_v1410(flujo_v1410_actual)
    st.divider()
    st.session_state.mostrar_solver_manual_v1410 = st.checkbox(
        "🛠️ Mostrar también el solucionador manual para revisar o modificar datos",
        value=bool(st.session_state.get("mostrar_solver_manual_v1410", False)),
        key="mostrar_solver_manual_v1410_control",
    )
    usar_solver_manual_v1410 = bool(st.session_state.mostrar_solver_manual_v1410)
else:
    usar_solver_manual_v1410 = True

if usar_solver_manual_v1410:
    if clase_activa == "Clase I":
        render_clase_i()

    elif clase_activa in ("Clase II-A", "Clase II-B", "Clase II-C"):
        render_clase_ii(clase_activa)

    elif clase_activa == "Clase III-A":
        render_clase_iii_a()

    elif clase_activa == "Clase III-B":
        render_clase_iii_b()



# ============================================================
# V14.17 — BANCO MAESTRO / MODO PRUEBA DE PROFESOR
# ============================================================

with st.expander("🧪 V14.17 — Banco maestro · Modo prueba de profesor", expanded=False):
    st.write(
        "Ejecuta 49 casos permanentes sin modificar el solver: Mott 7e, clasificación, "
        "unidades, accesorios/transiciones, flujo end-to-end y guardrails conservadores."
    )
    st.caption(
        "Úselo antes y después de cualquier cambio importante. Un punto de guardado estable "
        "no debe aceptarse si este banco reporta fallos."
    )
    if st.button("🧪 EJECUTAR BANCO MAESTRO", key="ejecutar_banco_v1417", use_container_width=True):
        with st.spinner("Ejecutando 49 casos de regresión..."):
            st.session_state["resultado_banco_v1417"] = ejecutar_banco_maestro(verbose=False)

    banco_v1417 = st.session_state.get("resultado_banco_v1417")
    if banco_v1417:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Casos", banco_v1417.get("total", 0))
        c2.metric("OK", banco_v1417.get("ok", 0))
        c3.metric("Fallos", banco_v1417.get("fallos", 0))
        c4.metric("Tiempo", f"{banco_v1417.get('duracion_ms', 0)/1000:.2f} s")
        if banco_v1417.get("estado") == "OK":
            st.success("✅ V14.17: banco maestro completo sin regresiones.")
        else:
            st.error("❌ V14.17: se detectaron regresiones. No convierta esta versión en punto estable.")

        df_banco = pd.DataFrame(banco_v1417.get("resultados", []))
        if not df_banco.empty:
            cols=[c for c in ["id","categoria","estado","nombre","esperado","obtenido","duracion_ms"] if c in df_banco.columns]
            st.dataframe(df_banco[cols], use_container_width=True, hide_index=True)

        d1, d2, d3 = st.columns(3)
        d1.download_button(
            "⬇️ JSON", reporte_json_v1417(banco_v1417),
            file_name="banco_regresion_v14_17.json", mime="application/json", use_container_width=True,
        )
        d2.download_button(
            "⬇️ CSV", reporte_csv_v1417(banco_v1417),
            file_name="banco_regresion_v14_17.csv", mime="text/csv", use_container_width=True,
        )
        d3.download_button(
            "⬇️ Markdown", reporte_markdown_v1417(banco_v1417),
            file_name="banco_regresion_v14_17.md", mime="text/markdown", use_container_width=True,
        )

# ============================================================
# PIE
# ============================================================

st.divider()

with st.expander("ℹ️ Nota sobre la automatización"):
    st.write(
        "El identificador y el autollenado utilizan reglas de texto. "
        "Convierten unidades reconocidas a SI y rellenan únicamente los datos "
        "que pueden interpretarse con suficiente claridad. Los valores deben "
        "revisarse antes de ejecutar el cálculo."
    )
    st.write(
        "El catálogo de fluidos incluye el agua del Apéndice A, los líquidos comunes y datos "
        "naturales/biológicos del Apéndice B, y los aceites lubricantes de petróleo del Apéndice C "
        "de Mott 7e. Los datos marcados como aproximados muestran una advertencia antes del cálculo."
    )
    st.write(
        "Las rugosidades corresponden a todas las categorías de la Tabla 8.2 de Mott 7e. "
        "Para válvulas y accesorios de la Tabla 10.4 se usa K=(Le/D)·fT. En acero comercial "
        "nuevo y limpio se toma fT de la Tabla 10.5; para otros materiales se obtiene fT con la "
        "rugosidad de la Tabla 8.2 en la zona de turbulencia completa del diagrama de Moody."
    )
    st.write(
        "Las entradas usan los K de la Figura 10.14 y la salida a depósito grande usa K=1. "
        "Los elementos marcados explícitamente como [auxiliar] no se presentan como datos de la Tabla 10.4."
    )
    st.write(
        "V14.8 añade una auditoría independiente posterior al solver: vuelve a comprobar continuidad, "
        "Darcy-Weisbach, pérdidas menores, sumas y residual sin alterar el método de cálculo."
    )
    st.write(
        "V14.9 conserva la firma del snapshot V14.7, verifica si hubo cambios manuales posteriores y "
        "genera un reporte técnico trazable en Markdown, JSON y Word con entradas, resultados y auditoría."
    )
    st.write(
        "V14.10 añade un flujo automático supervisado: después de la confirmación humana V14.7 puede "
        "ejecutar el solver, V14.8.3 y V14.9 de principio a fin, sin eliminar el modo manual."
    )
    st.write(
        "V14.11 añade confianza heurística individual por dato: distingue texto directo, OCR, figura, "
        "inferencias V14.5 y respuestas V14.6, y exige confirmación dirigida de los datos dudosos antes de V14.7."
    )
    st.write(
        "V14.12 añade un parser hidráulico robusto para unidades y notaciones reales: NPS/DN + Schedule, "
        "pulgadas, psig, columnas de agua, caudales SI/US, temperatura y viscosidades, conservando cada conversión original→SI."
    )
    st.write(
        "V14.13 interpreta accesorios y transiciones con mayor contexto Mott. V14.14 añade visión geométrica 2.0: "
        "recorrido poligonal, tuberías inclinadas/escalonadas, niveles relativos, múltiples cambios de sección, "
        "equipos rotativos ambiguos y rectificación conservadora de perspectiva, sin convertir píxeles a magnitudes físicas."
    )

    st.write(
        "V14.15 añade diagramas hidráulicos avanzados: esquema, LE/LAM y pérdidas acumuladas aparecen "
        "directamente después del flujo automático V14.10, con marcadores de accesorios, transiciones y equipos, "
        "además de controles para reducir etiquetas en sistemas densos."
    )
    st.write(
        "V14.16 añade una auditoría física pos-solver: velocidades, Reynolds, presión absoluta/vapor, "
        "geometría, pérdidas, equipos y alcance de cavitación/NPSH sin modificar el resultado. "
        "V14.17 incorpora un banco maestro permanente de 42 casos y un modo prueba de profesor: "
        "ejecuta Mott, clasificación, parser, componentes, flujo end-to-end y guardrails antes de aceptar una versión estable."
    )
    st.write(
        "V14.18 añade un Reporte técnico V2 para entrega académica/profesional: portada, resumen, datos y fuentes, "
        "supuestos, ecuaciones, resultados compactos, esquema V14.15, LE/LAM, pérdidas acumuladas, auditorías, "
        "nomenclatura y trazabilidad. Se exporta directamente a Word y PDF sin recalcular el problema."
    )
    st.write(
        "V14.19 añade el procedimiento académico Mott paso a paso: datos, ecuación de energía, sustituciones por tramo, "
        "iteraciones reales del solver, comprobación y respuesta final. Puede visualizarse en la app y descargarse en Markdown o Word."
    )
    st.write(
        "V14.20 añade un comparador de escenarios sobre el snapshot V14.7 confirmado. Permite evaluar variantes de "
        "diámetro, longitud, material, accesorios, presión, elevación, carga de bomba/turbina y —cuando la clase lo admite— caudal, "
        "sin modificar la base y reutilizando el mismo solver, auditorías y procedimiento Mott."
    )

st.caption(
    "Calculadora académica de sistemas de tuberías en serie — Mecánica de Fluidos II."
)
