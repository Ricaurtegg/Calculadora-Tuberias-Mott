"""Respuesta interactiva de datos faltantes — V14.6.

Esta capa trabaja sobre el expediente V14.5. Su objetivo es aplicar únicamente
respuestas correspondientes a preguntas que el expediente realmente marcó como
faltantes, volver a consolidar y dejar trazabilidad de lo aportado por el usuario.

No resuelve la hidráulica ni modifica los métodos Mott.
"""
from __future__ import annotations

import copy

from catalogos_mott import ACCESORIOS, FLUIDOS, MATERIALES
from consolidacion_datos import consolidar_resultado
from transiciones_mott import (
    TIPO_SIN,
    TIPO_EXP_SUD,
    TIPO_EXP_GRAD,
    TIPO_CON_SUD,
    TIPO_CON_GRAD,
)

VERSION_COMPLETADO = "V14.6"

TIPOS_TRANSICION = [
    TIPO_SIN,
    TIPO_EXP_SUD,
    TIPO_EXP_GRAD,
    TIPO_CON_SUD,
    TIPO_CON_GRAD,
]


class ErrorRespuestaFaltante(ValueError):
    pass


def identificador_pregunta(item: dict) -> str:
    """Identificador estable para una pregunta del expediente."""
    clave = str(item.get("clave") or "dato")
    tramo = item.get("tramo")
    return f"{clave}__tramo_{int(tramo)}" if tramo is not None else clave


def _tramo_por_numero(prefill: dict, numero: int) -> dict:
    tramos = prefill.setdefault("tramos", [])
    for i, tramo in enumerate(tramos, 1):
        n = int(tramo.get("numero", i) or i)
        if n == int(numero):
            return tramo
    raise ErrorRespuestaFaltante(f"No existe el tramo {numero} en el expediente.")


def _float(v, nombre: str) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError) as e:
        raise ErrorRespuestaFaltante(f"{nombre} debe ser numérico.") from e
    if x != x or x in (float("inf"), float("-inf")):
        raise ErrorRespuestaFaltante(f"{nombre} debe ser un número finito.")
    return x


def _validar_numero(clave: str, valor) -> float:
    x = _float(valor, clave)
    if clave in {"Q_m3s", "L_m", "D_m"} and x <= 0:
        raise ErrorRespuestaFaltante(f"{clave} debe ser mayor que cero.")
    if clave in {"hA_m", "hR_m"} and x < 0:
        raise ErrorRespuestaFaltante(f"{clave} no puede ser negativo.")
    return x


def _aplicar_escalar(prefill: dict, item: dict, respuesta):
    clave = item["clave"]
    if clave == "incognita_clase_i":
        opciones = list(item.get("opciones") or [])
        if respuesta not in opciones:
            raise ErrorRespuestaFaltante("Seleccione una incógnita válida para Clase I.")
        prefill[clave] = respuesta
        return

    if clave == "fluido_app":
        if isinstance(respuesta, dict):
            nombre = respuesta.get("nombre")
        else:
            nombre = respuesta
            respuesta = {"nombre": nombre}
        if nombre not in FLUIDOS:
            raise ErrorRespuestaFaltante("Seleccione un fluido válido del catálogo.")
        prefill["fluido_app"] = nombre
        # Mantiene una descripción coherente para consumidores que usan este campo.
        prefill["fluido_detectado"] = nombre
        datos = FLUIDOS[nombre]
        if nombre == "Personalizado":
            rho = _float(respuesta.get("rho"), "densidad del fluido personalizado")
            nu = _float(respuesta.get("nu"), "viscosidad cinemática del fluido personalizado")
            if rho <= 0 or nu <= 0:
                raise ErrorRespuestaFaltante("ρ y ν del fluido personalizado deben ser mayores que cero.")
            prefill["rho_usuario"] = rho
            prefill["nu_usuario_m2s"] = nu
        elif datos.get("nu") is None and datos.get("tipo") != "agua_interpolar":
            nu = _float(respuesta.get("nu"), "viscosidad cinemática faltante")
            if nu <= 0:
                raise ErrorRespuestaFaltante("ν debe ser mayor que cero.")
            prefill["nu_usuario_m2s"] = nu
        return

    if clave == "temperatura_c":
        prefill[clave] = _float(respuesta, "temperatura")
        return

    if clave == "mu_usuario_pa_s":
        mu = _float(respuesta, "viscosidad dinámica μ")
        if mu <= 0:
            raise ErrorRespuestaFaltante("μ debe ser mayor que cero.")
        prefill["mu_usuario_pa_s"] = mu
        rho = prefill.get("rho_usuario")
        if rho is not None and _float(rho, "densidad ρ") > 0:
            prefill["nu_usuario_m2s"] = mu / float(rho)
            prefill["propiedades_explicitas_v1412"] = True
            prefill["fluido_app"] = "Personalizado"
            if not prefill.get("fluido_detectado"):
                prefill["fluido_detectado"] = "Personalizado"
        prefill.pop("mu_ocr_ambigua_v1412", None)
        return

    if clave == "nu_usuario_m2s":
        nu = _float(respuesta, "viscosidad cinemática ν")
        if nu <= 0:
            raise ErrorRespuestaFaltante("ν debe ser mayor que cero.")
        prefill["nu_usuario_m2s"] = nu
        if prefill.get("rho_usuario") is not None and float(prefill["rho_usuario"]) > 0:
            prefill["propiedades_explicitas_v1412"] = True
            prefill["fluido_app"] = "Personalizado"
        return

    if clave == "rho_usuario":
        rho = _float(respuesta, "densidad ρ")
        if rho <= 0:
            raise ErrorRespuestaFaltante("ρ debe ser mayor que cero.")
        prefill["rho_usuario"] = rho
        mu = prefill.get("mu_usuario_pa_s")
        if mu is not None and float(mu) > 0:
            prefill["nu_usuario_m2s"] = float(mu) / rho
        if prefill.get("nu_usuario_m2s") is not None and float(prefill["nu_usuario_m2s"]) > 0:
            prefill["propiedades_explicitas_v1412"] = True
            prefill["fluido_app"] = "Personalizado"
        return

    if clave in {"Q_m3s", "P1_kpa", "P2_kpa", "z1_m", "z2_m", "hA_m", "hR_m"}:
        prefill[clave] = _validar_numero(clave, respuesta)
        return

    raise ErrorRespuestaFaltante(f"La respuesta para {clave} no tiene un aplicador V14.6 definido.")


def _aplicar_tramo(prefill: dict, item: dict, respuesta):
    numero = int(item.get("tramo"))
    tramo = _tramo_por_numero(prefill, numero)
    clave = item["clave"]

    if clave in {"L_m", "D_m"}:
        tramo[clave] = _validar_numero(clave, respuesta)
        return

    if clave == "material":
        if isinstance(respuesta, dict):
            nombre = respuesta.get("nombre")
        else:
            nombre = respuesta
            respuesta = {"nombre": nombre}
        if nombre not in MATERIALES:
            raise ErrorRespuestaFaltante("Seleccione un material válido del catálogo.")
        tramo["material"] = nombre
        if nombre == "Personalizada":
            epsilon = _float(respuesta.get("epsilon_m"), "rugosidad absoluta ε")
            if epsilon < 0:
                raise ErrorRespuestaFaltante("La rugosidad absoluta ε no puede ser negativa.")
            tramo["epsilon_m"] = epsilon
        return

    raise ErrorRespuestaFaltante(f"No se reconoce el dato {clave} para el tramo {numero}.")


def _crear_tramos(prefill: dict, respuesta):
    try:
        n = int(respuesta)
    except (TypeError, ValueError) as e:
        raise ErrorRespuestaFaltante("El número de tramos debe ser un entero.") from e
    if not (1 <= n <= 20):
        raise ErrorRespuestaFaltante("El número de tramos debe estar entre 1 y 20.")

    prefill["tramos"] = [
        {
            "numero": i,
            "L_m": None,
            "D_m": None,
            "material": None,
            "accesorios": [],
            "curvas": [],
            "K_extra": None,
            "componentes_graficos": [],
        }
        for i in range(1, n + 1)
    ]


def _aplicar_transicion(prefill: dict, item: dict, respuesta):
    if not isinstance(respuesta, dict):
        raise ErrorRespuestaFaltante("La transición requiere tipo y, si aplica, ángulo.")
    tipo = respuesta.get("tipo")
    if tipo not in TIPOS_TRANSICION:
        raise ErrorRespuestaFaltante("Seleccione un tipo de transición válido.")

    try:
        idx = int(str(item["clave"]).split("_")[-1]) - 1
    except Exception as e:
        raise ErrorRespuestaFaltante("No se pudo identificar la transición solicitada.") from e

    transiciones = prefill.setdefault("transiciones", [])
    if not (0 <= idx < len(transiciones)):
        raise ErrorRespuestaFaltante("La transición ya no existe en el expediente actual.")

    angulo = respuesta.get("angulo_grados")
    if tipo == TIPO_EXP_GRAD:
        angulo = _float(angulo, "ángulo de ensanchamiento")
        if not (2.0 <= angulo <= 60.0):
            raise ErrorRespuestaFaltante("El ensanchamiento gradual requiere 2° ≤ θ ≤ 60°.")
    elif tipo == TIPO_CON_GRAD:
        angulo = _float(angulo, "ángulo de contracción")
        if not (3.0 <= angulo <= 150.0):
            raise ErrorRespuestaFaltante("La contracción gradual requiere 3° ≤ θ ≤ 150°.")
    else:
        angulo = None

    transiciones[idx]["tipo"] = tipo
    transiciones[idx]["angulo_grados"] = angulo


def _aplicar_componente(prefill: dict, item: dict, respuesta):
    if not isinstance(respuesta, dict):
        raise ErrorRespuestaFaltante("El componente gráfico requiere una confirmación estructurada.")
    numero = int(item.get("tramo"))
    tramo = _tramo_por_numero(prefill, numero)
    try:
        indice = int(str(item["clave"]).rsplit("_", 1)[-1]) - 1
    except Exception as e:
        raise ErrorRespuestaFaltante("No se pudo identificar el componente gráfico.") from e

    componentes = list(tramo.get("componentes_graficos") or [])
    if not (0 <= indice < len(componentes)):
        raise ErrorRespuestaFaltante("El componente gráfico ya no existe en el expediente actual.")
    componente = componentes[indice]
    modo = respuesta.get("modo")

    if modo == "accesorio":
        nombre = respuesta.get("nombre")
        if nombre not in ACCESORIOS:
            raise ErrorRespuestaFaltante("Seleccione un accesorio válido del catálogo Mott.")
        pos = componente.get("posicion_fraccion")
        item_acc = {"nombre": nombre, "cantidad": 1}
        if pos is not None:
            item_acc["posicion_fraccion"] = float(pos)
            item_acc["posiciones_fraccion"] = [float(pos)]
        tramo.setdefault("accesorios", []).append(item_acc)

    elif modo == "k_manual":
        k = _float(respuesta.get("K"), "K manual")
        if k < 0:
            raise ErrorRespuestaFaltante("K manual no puede ser negativo.")
        previo = tramo.get("K_extra")
        tramo["K_extra"] = float(previo or 0.0) + k
        if componente.get("posicion_fraccion") is not None:
            tramo["K_extra_posicion_fraccion"] = float(componente["posicion_fraccion"])

    elif modo == "sin_perdida":
        pass
    else:
        raise ErrorRespuestaFaltante("Confirme el componente como accesorio, K manual o sin pérdida adicional.")

    # Se elimina únicamente el candidato resuelto; los demás conservan su orden.
    componentes.pop(indice)
    tramo["componentes_graficos"] = componentes



def _aplicar_componente_texto_v1413(prefill: dict, item: dict, respuesta):
    if not isinstance(respuesta, dict):
        raise ErrorRespuestaFaltante("El componente V14.13 requiere una confirmación estructurada.")
    try:
        indice = int(str(item["clave"]).rsplit("_", 1)[-1]) - 1
    except Exception as e:
        raise ErrorRespuestaFaltante("No se pudo identificar el componente V14.13.") from e
    pendientes = list(prefill.get("componentes_pendientes_v1413") or [])
    if not (0 <= indice < len(pendientes)):
        raise ErrorRespuestaFaltante("El componente V14.13 ya no existe en el expediente actual.")
    componente = pendientes[indice]
    numero = componente.get("tramo") or item.get("tramo")
    if numero is None:
        raise ErrorRespuestaFaltante("Indique primero a qué tramo pertenece el componente.")
    tramo = _tramo_por_numero(prefill, int(numero))
    modo = respuesta.get("modo")

    if modo == "accesorio":
        nombre = respuesta.get("nombre")
        if nombre not in ACCESORIOS:
            raise ErrorRespuestaFaltante("Seleccione un accesorio válido del catálogo Mott.")
        tramo.setdefault("accesorios", []).append({
            "nombre": nombre, "cantidad": max(1, int(componente.get("cantidad", 1) or 1)),
            "fuente_v1413": "confirmación usuario V14.6/V14.13",
        })
    elif modo == "k_manual":
        k = _float(respuesta.get("K"), "K manual")
        if k < 0:
            raise ErrorRespuestaFaltante("K manual no puede ser negativo.")
        tramo["K_extra"] = float(tramo.get("K_extra") or 0.0) + k
    elif modo == "sin_perdida":
        pass
    else:
        raise ErrorRespuestaFaltante("Confirme el componente como accesorio, K manual o sin pérdida adicional.")

    pendientes.pop(indice)
    prefill["componentes_pendientes_v1413"] = pendientes

def _aplicar_una(prefill: dict, item: dict, respuesta):
    clave = str(item.get("clave") or "")
    if clave == "tramos":
        return _crear_tramos(prefill, respuesta)
    if clave.startswith("transicion_"):
        return _aplicar_transicion(prefill, item, respuesta)
    if clave.startswith("componente_grafico_"):
        return _aplicar_componente(prefill, item, respuesta)
    if clave.startswith("componente_texto_v1413_"):
        return _aplicar_componente_texto_v1413(prefill, item, respuesta)
    if item.get("tramo") is not None:
        return _aplicar_tramo(prefill, item, respuesta)
    return _aplicar_escalar(prefill, item, respuesta)


def aplicar_respuestas_faltantes(resultado: dict, enunciado: str, respuestas: dict) -> dict:
    """Aplica respuestas válidas solo a preguntas que están actualmente pendientes.

    ``respuestas`` se indexa por :func:`identificador_pregunta`.
    Las respuestas vacías/None se ignoran para permitir completar por etapas.
    """
    base = consolidar_resultado(copy.deepcopy(resultado or {}), enunciado)
    expediente = base.get("expediente_v145") or {}
    faltantes = list(expediente.get("faltantes") or [])
    mapa = {identificador_pregunta(x): x for x in faltantes}

    prefill = base.setdefault("prefill", {})
    aplicadas = []
    errores = []

    # Componentes se procesan de índice mayor a menor por tramo para que al
    # eliminar uno no cambie el índice de los todavía pendientes.
    orden = list(respuestas.items())
    def _sort_key(par):
        pid, _ = par
        item = mapa.get(pid) or {}
        clave = str(item.get("clave") or "")
        if clave.startswith("componente_grafico_") or clave.startswith("componente_texto_v1413_"):
            try:
                idx = int(clave.rsplit("_", 1)[-1])
            except Exception:
                idx = 0
            return (0, int(item.get("tramo") or 0), -idx)
        return (1, int(item.get("tramo") or 0), 0)
    orden.sort(key=_sort_key)

    for pid, respuesta in orden:
        if pid not in mapa:
            continue
        if respuesta is None or respuesta == "":
            continue
        item = mapa[pid]
        try:
            _aplicar_una(prefill, item, respuesta)
            aplicadas.append({
                "id": pid,
                "clave": item.get("clave"),
                "tramo": item.get("tramo"),
                "respuesta": copy.deepcopy(respuesta),
                "fuente": "usuario V14.6",
            })
        except ErrorRespuestaFaltante as e:
            errores.append({"id": pid, "mensaje": str(e)})

    if errores:
        detalle = " | ".join(f"{x['id']}: {x['mensaje']}" for x in errores)
        raise ErrorRespuestaFaltante(detalle)

    previo = list(base.get("respuestas_v146") or [])
    # Conserva la última respuesta por identificador para trazabilidad compacta.
    acumulado = {x.get("id"): x for x in previo if x.get("id")}
    for x in aplicadas:
        acumulado[x["id"]] = x
    base["respuestas_v146"] = list(acumulado.values())

    salida = consolidar_resultado(base, enunciado)
    exp_nuevo = salida.get("expediente_v145") or {}
    salida["completado_v146"] = {
        "version": VERSION_COMPLETADO,
        "respuestas_aplicadas_en_esta_iteracion": len(aplicadas),
        "respuestas_acumuladas": len(salida.get("respuestas_v146") or []),
        "faltantes_restantes": int(exp_nuevo.get("cantidad_faltantes", 0) or 0),
        "conflictos": int(exp_nuevo.get("cantidad_conflictos", 0) or 0),
        "listo_para_transferir": bool(exp_nuevo.get("listo_para_resolver")),
    }
    return salida


def opciones_transicion_para_pregunta(item: dict, prefill: dict) -> list[str]:
    """Devuelve solo las transiciones físicamente compatibles si conoce D1/D2."""
    try:
        idx = int(str(item["clave"]).split("_")[-1]) - 1
        trans = (prefill.get("transiciones") or [])[idx]
        entre = int(trans.get("entre"))
        tramos = prefill.get("tramos") or []
        # Si V14.13 ya identificó una transición gradual pero falta solo θ,
        # no obligamos al usuario a reclasificarla: mostramos únicamente ese tipo.
        tipo_existente = trans.get("tipo")
        if tipo_existente in {TIPO_EXP_GRAD, TIPO_CON_GRAD} and trans.get("angulo_grados") is None:
            return [tipo_existente]
        d1 = tramos[entre - 1].get("D_m")
        d2 = tramos[entre].get("D_m")
        if d1 is None or d2 is None:
            return list(TIPOS_TRANSICION)
        d1, d2 = float(d1), float(d2)
        if abs(d1 - d2) < 1e-12:
            return [TIPO_SIN]
        if d2 > d1:
            return [TIPO_SIN, TIPO_EXP_SUD, TIPO_EXP_GRAD]
        return [TIPO_SIN, TIPO_CON_SUD, TIPO_CON_GRAD]
    except Exception:
        return list(TIPOS_TRANSICION)
