"""Banco maestro de regresión y modo prueba de profesor — V14.17.

49 casos permanentes distribuidos en:
- 6 casos dorados Mott 7e cap. 11;
- 15 casos de clasificación I/II-A/II-B/II-C/III-A/III-B;
- 12 casos de parser hidráulico V14.12.3;
- 8 casos de accesorios/transiciones V14.13;
- 6 casos end-to-end del flujo V14.10;
- 2 guardrails conservadores.

El banco no modifica el solver. Solo lo observa y compara contra expectativas
congeladas/tolerancias explícitas.
"""
from __future__ import annotations

import copy
import csv
import io
import json
import math
import time
from dataclasses import dataclass, asdict
from typing import Any, Callable

from casos_mott_cap11 import CASOS, FT_TO_M, PSI_TO_PA
from calculos.hidraulica import (
    calcular_sistema_para_q,
    resolver_clase_i,
    residuo_energia,
    potencia_entrada_bomba,
    verificar_clase_iii_b,
)
from metodos_mott import resolver_clase_ii_mott_v9, resolver_clase_iii_a_mott_v9
from clasificar_problema import identificar_clase_automaticamente
from parser_hidraulico_v1412 import analizar_enunciado_v1412
from componentes_mott_v1413 import analizar_componentes_v1413
from transferencia_v147 import construir_previsualizacion_transferencia
from reporte_final_v149 import construir_manifiesto_ejecucion
from flujo_automatico_v1410 import resolver_flujo_confirmado, ErrorFlujoV1410
from consolidacion_datos import consolidar_resultado

VERSION_BANCO = "V14.17"


@dataclass
class ResultadoCaso:
    id: str
    categoria: str
    nombre: str
    estado: str
    esperado: str
    obtenido: str
    detalle: str = ""
    duracion_ms: float = 0.0


def _rel(v, ref):
    return abs(float(v) - float(ref)) / max(abs(float(ref)), 1e-30)


def _cerca(v, ref, rel=1e-3, abs_tol=1e-12):
    return abs(float(v) - float(ref)) <= max(abs_tol, rel * max(abs(float(ref)), 1e-30))


def _tramo(t):
    return {
        "numero": t.get("numero", 1), "L": float(t["L"]), "D": float(t["D"]),
        "material": t.get("material", "Acero comercial o soldado"),
        "epsilon": float(t.get("epsilon", 0.0)), "K": float(t.get("K", 0.0)),
        "K_extra": float(t.get("K_extra", 0.0)),
        "K_extra_posicion_fraccion": float(t.get("K_extra_posicion_fraccion", 0.85)),
        "accesorios_detalle": list(t.get("accesorios_detalle", [])),
        "componentes_graficos": list(t.get("componentes_graficos", [])),
    }


def _ejecutar_mott(clave: str) -> tuple[bool, str, str]:
    c = CASOS[clave]
    tol = float(c.get("tolerancia_rel", 0.03))
    if clave == "I_11_1":
        tr = [_tramo(t) for t in c["tramos"]]
        sis = calcular_sistema_para_q(c["Q"], tr, c["nu"])
        hL = float(sis["hL_total"])
        hA = float(resolver_clase_i(
            incognita="hA", P1=c["P1"], P2=c["P2"], z1=c["z1"], z2=c["z2"],
            V1=0.0, V2=0.0, hA=None, hR=0.0, hL=hL, gamma=c["gamma"],
        ))
        pin = potencia_entrada_bomba(c["gamma"], c["Q"], hA, c["eficiencia"]) / 1000.0
        ok = all([
            _rel(hL, c["esperado"]["hL_m"]) <= tol,
            _rel(hA, c["esperado"]["hA_m"]) <= tol,
            _rel(pin, c["esperado"]["potencia_entrada_kW"]) <= tol,
        ])
        return ok, f"hA≈{c['esperado']['hA_m']} m", f"hA={hA:.5g} m; hL={hL:.5g} m"
    if clave in {"IIA_11_2", "IIB_11_3", "IIC_11_4"}:
        metodo = c["clase"].replace("Clase ", "")
        sol = resolver_clase_ii_mott_v9(
            metodo=metodo, tramos=[_tramo(t) for t in c["tramos"]], nu=c["nu"], gamma=c["gamma"],
            P1=c["P1"], P2=c["P2"], z1=c["z1"], z2=c["z2"], hA=c["hA"], hR=c["hR"],
            tipo_v1=c["tipo_v1"], tipo_v2=c["tipo_v2"], transiciones=[],
        )
        q = float(sol["Q_final"])
        ok = _rel(q, c["esperado"]["Q_m3s"]) <= tol
        return ok, f"Q≈{c['esperado']['Q_m3s']:.7g}", f"Q={q:.8g}"
    if clave == "IIIA_11_5":
        r = resolver_clase_iii_a_mott_v9(
            Q=c["Q"], L=c["L"], epsilon=c["epsilon"], nu=c["nu"],
            hL_permitida=c["hL_permitida"], catalogo_comercial=c["catalogo"],
        )
        d = float(r["D_mott"])
        ok = _rel(d, c["esperado"]["D_min_m"]) <= tol and r.get("tamano_comercial", {}).get("nps") == c["esperado"]["nps"]
        return ok, f"Dmin≈{c['esperado']['D_min_m']:.6g} m; NPS {c['esperado']['nps']}", f"Dmin={d:.7g}; NPS {r.get('tamano_comercial',{}).get('nps')}"
    if clave == "IIIB_11_6":
        r = verificar_clase_iii_b(
            D_actual=c["D"], Q=c["Q"], L=c["L"], epsilon=c["epsilon"], nu=c["nu"], K=c["K"],
            gamma=c["gamma"], P1=c["P1"], P2_deseada=c["P2_deseada"], z1=c["z1"], z2=c["z2"],
            hA=c["hA"], hR=c["hR"], tipo_v1=c["tipo_v1"], tipo_v2=c["tipo_v2"],
        )
        p2 = float(r["P2_calculada"]) / PSI_TO_PA
        ok = abs(p2 - c["esperado"]["P2_psi"]) <= 0.15
        return ok, f"P2≈{c['esperado']['P2_psi']} psig", f"P2={p2:.5g} psig"
    raise KeyError(clave)


CASOS_CLASIFICACION = [
    ("C-I-01", "Clase I", "Dado Q=0.010 m3/s, L=50 m y D=80 mm, determine P2."),
    ("C-I-02", "Clase I", "Por una tubería circulan 18 L/s. Determine la carga de la bomba hA."),
    ("C-IIA-01", "Clase II-A", "Determine el caudal Q entre dos depósitos abiertos unidos por una tubería de 100 m y 100 mm. Desprecie pérdidas menores."),
    ("C-IIA-02", "Clase II-A", "Calcule Q en una tubería recta de 250 ft NPS 4 Schedule 40. Desprecie las pérdidas menores."),
    ("C-IIB-01", "Clase II-B", "Determine el caudal Q en una tubería de 120 m y 100 mm con dos codos y una válvula; considere las pérdidas menores relativamente pequeñas como corrección."),
    ("C-IIB-02", "Clase II-B", "Halle el caudal Q si la línea tiene L=90 m, D=75 mm y K=3.2; trate las pérdidas menores como una pequeña corrección."),
    ("C-IIC-01", "Clase II-C", "Dos depósitos están conectados por dos tramos en serie de 100 mm y 75 mm con una contracción súbita y una válvula. Determine Q."),
    ("C-IIC-02", "Clase II-C", "Determine el caudal entre dos depósitos a través de tres tuberías en serie de distintos diámetros, con codos, válvula y cambio de sección."),
    ("C-IIIA-01", "Clase III-A", "Para Q=0.010 m3/s determine el diámetro mínimo D de una tubería de 50 m si hL permitida es 3 m."),
    ("C-IIIA-02", "Clase III-A", "Determine el diámetro requerido de una tubería para transportar 850 gpm con una pérdida de carga máxima especificada."),
    ("C-IIIB-01", "Clase III-B", "Se seleccionó una tubería comercial de D=80 mm para Q=0.010 m3/s. Verifique la presión P2 disponible."),
    ("C-IIIB-02", "Clase III-B", "Verifique si la tubería comercial NPS 4 Schedule 40 con caudal conocido cumple la presión mínima de 100 psig en la salida."),
    ("C-MOTT112", "Clase II-A", "Aceite lubricante en tubería horizontal DN 150 cédula 40 con caída de presión máxima de 60 kPa por cada 100 m. Determine la rapidez del flujo volumétrico máximo permisible."),
    ("C-MOTT113", "Clase II-B", "Aceite lubricante en línea horizontal DN 150 Schedule 40 de 30 m + 40 m + 30 m, dos codos estándar y válvula mariposa totalmente abierta. Determine la rapidez del flujo volumétrico máxima permisible."),
    ("C-SPRINKLER", "Clase III-A", "Determine el tamaño más pequeño permisible de tubería estándar Calibre 40 para alimentar 0.50 pies^3/s de agua a 60 °F con presión mínima requerida en B."),
]


CASOS_PARSER = [
    ("P-01", "Q=850 gpm", lambda a: _cerca(a.get("escalares",{}).get("Q_m3s"), 850*0.003785411784/60, 2e-6), "850 gpm→m³/s"),
    ("P-02", "Q=1.5 ft3/s", lambda a: _cerca(a.get("escalares",{}).get("Q_m3s"), 1.5*0.028316846592, 2e-6), "1.5 ft³/s→m³/s"),
    ("P-03", "P1=35 psig", lambda a: _cerca(a.get("escalares",{}).get("P1_kpa"), 35*6.894757293168, 2e-6), "35 psig→kPa"),
    ("P-04", "z1=120 ft", lambda a: _cerca(a.get("escalares",{}).get("z1_m"), 36.576, 2e-6), "120 ft→36.576 m"),
    ("P-05", "Tramo 1: tubería NPS 4 Schedule 40, L=100 m", lambda a: _cerca(a["tramos"][0].get("D_m"), 0.1023, 2e-4), "NPS4 Sch40→ID 102.3 mm"),
    ("P-06", "Tramo 1: DN100 cédula 80, L=100 m", lambda a: _cerca(a["tramos"][0].get("D_m"), 0.0972, 2e-4), "DN100 Sch80→ID 97.2 mm"),
    ("P-07", "Agua a 68 °F", lambda a: _cerca(a.get("escalares",{}).get("temperatura_c"), 20.0, 1e-6), "68°F→20°C"),
    ("P-08", "nu = 1.30 cSt y rho = 998 kg/m3", lambda a: _cerca(a.get("propiedades_fluido",{}).get("nu_m2s"), 1.30e-6, 1e-6), "1.30 cSt→1.30e-6 m²/s"),
    ("P-09", "gravedad específica de 0.88 y viscosidad dinámica de 9.5 x 10^-3 Pa.s", lambda a: _cerca(a.get("propiedades_fluido",{}).get("rho_kg_m3"),880.0,1e-9) and _cerca(a.get("propiedades_fluido",{}).get("nu_m2s"),0.0095/880.0,2e-6), "SG+μ→ρ=880 y ν=μ/ρ"),
    ("P-10", "presión en el punto B debe ser de al menos 60 lb/pulg^2 relativas", lambda a: _cerca(a.get("escalares",{}).get("P2_kpa"),60*6.894757293,2e-6), "60 lb/pulg²→413.685 kPa"),
    ("P-11", "Q = 0.50 pies^3/s", lambda a: _cerca(a.get("escalares",{}).get("Q_m3s"),0.50*0.028316846592,2e-6), "0.50 pies³/s→m³/s"),
    ("P-12", "La tubería tiene 600 pies de longitud y el punto B está 25 pies por encima de A.", lambda a: len(a.get("tramos") or [])==1 and _cerca(a["tramos"][0].get("L_m"),182.88,2e-6) and _cerca(a.get("escalares",{}).get("z2_m"),7.62,2e-6), "L=600 ft y Δz=25 ft"),
    ("P-13", "Aceite lubricante con gravedad específica de 0.88 y viscosidad dinámica de 9.5 x 10° Pa.s", lambda a: _cerca(a.get("propiedades_fluido",{}).get("rho_kg_m3"),880.0,1e-9) and isinstance(a.get("propiedades_fluido",{}).get("mu_ocr_ambigua"),dict), "OCR conserva ρ=880 y marca μ con exponente ambiguo sin inventarlo"),
]


CASOS_COMPONENTES = [
    ("A-01", "En el tramo 2 hay dos codos de 90 grados de radio largo.", [{"numero":1,"D_m":0.1},{"numero":2,"D_m":0.075}], "Codo 90° radio largo", 2),
    ("A-02", "El tramo 1 contiene una válvula de compuerta abierta al 50 %.", [{"numero":1,"D_m":0.1}], "Válvula de compuerta — 1/2 abierta", 1),
    ("A-03", "Hay una válvula de compuerta 75 % abierta en el tramo 1.", [{"numero":1,"D_m":0.1}], "Válvula de compuerta — 3/4 abierta", 1),
    ("A-04", "Existe una válvula mariposa completamente abierta en el tramo 2.", [{"numero":1,"D_m":0.1},{"numero":2,"D_m":0.075}], "Válvula mariposa — totalmente abierta", 1),
    ("A-05", "Existe una válvula mariposa en el tramo 1.", [{"numero":1,"D_m":0.1}], "PENDIENTE_MARIPOSA", 1),
    ("A-06", "En el tramo 2 existe una tee con flujo por el ramal.", [{"numero":1,"D_m":0.1},{"numero":2,"D_m":0.075}], "Tee estándar — flujo por ramal", 1),
    ("T-01", "Tramo 1 D=100 mm. Tramo 2 D=75 mm. Entre ambos hay una reducción súbita.", [{"numero":1,"D_m":0.1},{"numero":2,"D_m":0.075}], "Contracción súbita", 1),
    ("T-02", "Tramo 1 D=75 mm. Tramo 2 D=100 mm. La unión es una expansión cónica gradual de 20 grados.", [{"numero":1,"D_m":0.075},{"numero":2,"D_m":0.1}], "Ensanchamiento gradual", 1),
]


def _iic_completo():
    return {
        "clase": "Clase II-C", "confianza": 96,
        "prefill": {
            "fluido_app": "Agua a 20 °C", "fluido_detectado": "Agua a 20 °C",
            "P1_kpa": 135.0, "P2_kpa": 0.0, "z1_m": 31.2, "z2_m": 8.4,
            "hA_m": 0.0, "hR_m": 0.0, "v1_tipo": "deposito", "v2_tipo": "deposito",
            "tramos": [
                {"numero":1,"L_m":68.5,"D_m":0.1,"material":"Acero comercial o soldado","accesorios":[{"nombre":"Entrada — borde cuadrado/agudo","cantidad":1},{"nombre":"Codo 90° estándar","cantidad":2}],"componentes_graficos":[]},
                {"numero":2,"L_m":96.3,"D_m":0.075,"material":"Plástico","accesorios":[{"nombre":"Salida hacia depósito grande","cantidad":1},{"nombre":"Válvula de compuerta — totalmente abierta","cantidad":1}],"componentes_graficos":[]},
            ],
            "transiciones":[{"entre":1,"tipo":"Contracción súbita","angulo_grados":None}],
        },
    }


def _preparar_flujo(r, enunciado):
    p = construir_previsualizacion_transferencia(r, enunciado)
    if not p.get("listo_para_transferir"):
        raise AssertionError(f"V14.7 bloqueó caso: {p.get('bloqueos')}")
    m = construir_manifiesto_ejecucion(r, enunciado, p)
    return p, m


def _casos_flujo():
    casos=[]
    # I
    casos.append(("F-I", {"clase":"Clase I","confianza":95,"prefill":{"fluido_app":"Agua a 20 °C","Q_m3s":0.01,"P1_kpa":0.0,"P2_kpa":None,"z1_m":10.0,"z2_m":0.0,"hA_m":0.0,"hR_m":0.0,"v1_tipo":"deposito","v2_tipo":"deposito","incognita_clase_i":"Presión P2","tramos":[{"numero":1,"L_m":50.0,"D_m":0.08,"material":"Acero comercial o soldado","accesorios":[],"componentes_graficos":[]}],"transiciones":[]}}, "Determine P2", "P2", lambda f: f["auditoria"]["estado"]=="OK" and float(f["resultado_solver"]["valor"])>0))
    # II-A
    casos.append(("F-IIA", {"clase":"Clase II-A","confianza":95,"prefill":{"fluido_app":"Agua a 20 °C","P1_kpa":150.0,"P2_kpa":0.0,"z1_m":0.0,"z2_m":0.0,"hA_m":0.0,"hR_m":0.0,"v1_tipo":"tuberia","v2_tipo":"tuberia","tramos":[{"numero":1,"L_m":100.0,"D_m":0.1,"material":"Acero comercial o soldado","accesorios":[],"componentes_graficos":[]}],"transiciones":[]}}, "Determine Q", "Q>0", lambda f: f["auditoria"]["estado"]=="OK" and float(f["resultado_solver"]["Q_final"])>0))
    # II-B
    casos.append(("F-IIB", {"clase":"Clase II-B","confianza":95,"prefill":{"fluido_app":"Agua a 20 °C","P1_kpa":150.0,"P2_kpa":0.0,"z1_m":0.0,"z2_m":0.0,"hA_m":0.0,"hR_m":0.0,"v1_tipo":"tuberia","v2_tipo":"tuberia","tramos":[{"numero":1,"L_m":100.0,"D_m":0.1,"material":"Acero comercial o soldado","accesorios":[{"nombre":"Codo 90° estándar","cantidad":2},{"nombre":"Válvula de compuerta — totalmente abierta","cantidad":1}],"componentes_graficos":[]}],"transiciones":[]}}, "Determine Q con pérdidas menores", "Q>0", lambda f: f["auditoria"]["estado"]=="OK" and float(f["resultado_solver"]["Q_final"])>0))
    # II-C
    casos.append(("F-IIC", _iic_completo(), "Determine Q en dos tramos", "Q≈0.0246035", lambda f: f["auditoria"]["estado"]=="OK" and abs(float(f["resultado_solver"]["Q_final"])-0.02460353)<8e-7))
    # III-A
    casos.append(("F-IIIA", {"clase":"Clase III-A","confianza":95,"prefill":{"fluido_app":"Agua a 20 °C","Q_m3s":0.01,"P1_kpa":100.0,"P2_kpa":0.0,"z1_m":10.0,"z2_m":0.0,"hA_m":0.0,"hR_m":0.0,"tramos":[{"numero":1,"L_m":50.0,"D_m":None,"material":"Acero comercial o soldado","accesorios":[],"componentes_graficos":[]}],"transiciones":[]}}, "Determine D mínimo", "D>0", lambda f: f["auditoria"]["estado"] in {"OK","REVISAR"} and float(f["resultado_solver"]["D_mott"])>0))
    # III-B
    casos.append(("F-IIIB", {"clase":"Clase III-B","confianza":95,"prefill":{"fluido_app":"Agua a 20 °C","Q_m3s":0.01,"P1_kpa":100.0,"P2_kpa":0.0,"z1_m":10.0,"z2_m":0.0,"hA_m":0.0,"hR_m":0.0,"v1_tipo":"deposito","v2_tipo":"deposito","tramos":[{"numero":1,"L_m":50.0,"D_m":0.08,"material":"Acero comercial o soldado","accesorios":[],"componentes_graficos":[]}],"transiciones":[]}}, "Verifique D y P2", "auditoría OK", lambda f: f["auditoria"]["estado"]=="OK" and "satisfactorio" in f["resultado_solver"]))
    return casos


def _run_case(cid, categoria, nombre, esperado, fn: Callable[[], tuple[bool,str]]):
    t0=time.perf_counter()
    try:
        ok, obtenido = fn()
        estado="OK" if ok else "FALLO"
        detalle="" if ok else "El resultado no cumplió la expectativa congelada."
    except Exception as e:
        estado="ERROR"; obtenido=f"{type(e).__name__}: {e}"; detalle="Excepción durante la ejecución del caso."
    return ResultadoCaso(cid,categoria,nombre,estado,esperado,obtenido,detalle,(time.perf_counter()-t0)*1000.0)


def ejecutar_banco_maestro(verbose: bool=False) -> dict:
    resultados=[]
    # 6 Mott
    for clave in ("I_11_1","IIA_11_2","IIB_11_3","IIC_11_4","IIIA_11_5","IIIB_11_6"):
        c=CASOS[clave]
        def f(k=clave):
            ok, esp, obt = _ejecutar_mott(k); return ok, obt
        resultados.append(_run_case(f"M-{clave}","Mott dorado",c["nombre"],"Dentro de tolerancia Mott 7e",f))
    # 12 clasificación
    for cid, esperado, texto in CASOS_CLASIFICACION:
        def f(txt=texto, esp=esperado):
            r=identificar_clase_automaticamente(txt); return r.get("clase")==esp, f"{r.get('clase')} ({r.get('confianza')} %)"
        resultados.append(_run_case(cid,"Clasificación",texto,esperado,f))
    # 8 parser
    for cid,texto,pred,esperado in CASOS_PARSER:
        def f(txt=texto,p=pred):
            a=analizar_enunciado_v1412(txt); return bool(p(a)), json.dumps(a,ensure_ascii=False,default=str)[:260]
        resultados.append(_run_case(cid,"Parser/unidades",texto,esperado,f))
    # 8 componentes/transiciones
    for cid,texto,tramos,esperado,cant in CASOS_COMPONENTES:
        def f(txt=texto,tr=tramos,esp=esperado,c=cant):
            a=analizar_componentes_v1413(txt,copy.deepcopy(tr))
            if esp=="PENDIENTE_MARIPOSA":
                pend=a.get("pendientes") or a.get("componentes_pendientes") or []
                blob=json.dumps(a,ensure_ascii=False)
                ok=("mariposa" in blob.lower()) and ("definir" in blob.lower() or "pendiente" in blob.lower() or "apertura" in blob.lower())
                return ok, blob[:300]
            blob=json.dumps(a,ensure_ascii=False)
            ok=(esp.lower() in blob.lower())
            if cid.startswith("A-") and c>1:
                ok=ok and (str(c) in blob or f'"cantidad": {c}' in blob)
            return ok, blob[:300]
        resultados.append(_run_case(cid,"Accesorios/transiciones",texto,esperado,f))
    # 6 flujo end-to-end
    for cid,r,en,esperado,pred in _casos_flujo():
        def f(rr=r,ee=en,p=pred):
            prev,man=_preparar_flujo(copy.deepcopy(rr),ee)
            out=resolver_flujo_confirmado(copy.deepcopy(rr),ee,prev,prev["firma"],man)
            return bool(p(out)), f"auditoría={out['auditoria']['estado']}; solver={json.dumps(out['resultado_solver'],ensure_ascii=False,default=str)[:180]}"
        resultados.append(_run_case(cid,"Flujo end-to-end",en,esperado,f))
    # 2 guardrails
    def g1():
        a=analizar_enunciado_v1412("Tramo 1: NPS 4, longitud 100 m")
        tr=(a.get("tramos") or [{}])[0]
        return tr.get("D_m") is None, f"D_m={tr.get('D_m')}"
    resultados.append(_run_case("G-01","Guardrail","NPS sin Schedule no inventa diámetro","D_m=None",g1))
    def g2():
        r={"clase":"Clase II-C","confianza":90,"prefill":{"fluido_app":"Agua a 20 °C","P1_kpa":0.0,"P2_kpa":50.0,"z1_m":10.0,"z2_m":0.0,"hA_m":0.0,"hR_m":0.0,"tramos":[{"numero":1,"L_m":50.0,"D_m":0.08,"material":"Acero comercial o soldado","accesorios":[],"componentes_graficos":[]}],"transiciones":[]}}
        c=consolidar_resultado(r,"El depósito 2 está abierto a la atmósfera.")
        blob=json.dumps(c,ensure_ascii=False)
        # una contradicción atmosférica debe quedar visible/bloqueante en el expediente
        ok=("conflict" in blob.lower() or "contradic" in blob.lower() or "bloque" in blob.lower())
        return ok, blob[:260]
    resultados.append(_run_case("G-02","Guardrail","Atmósfera + P2 no nula genera conflicto","Conflicto bloqueante",g2))

    filas=[asdict(x) for x in resultados]
    ok=sum(1 for x in resultados if x.estado=="OK")
    fallos=len(resultados)-ok
    por_categoria={}
    for x in resultados:
        d=por_categoria.setdefault(x.categoria,{"total":0,"ok":0,"fallos":0})
        d["total"]+=1; d["ok"]+=x.estado=="OK"; d["fallos"]+=x.estado!="OK"
    resumen={
        "version":VERSION_BANCO,
        "total":len(resultados),"ok":ok,"fallos":fallos,
        "estado":"OK" if fallos==0 else "FALLO",
        "por_categoria":por_categoria,
        "duracion_ms":sum(x.duracion_ms for x in resultados),
        "resultados":filas,
    }
    if verbose:
        for x in resultados:
            print(f"[{x.estado:5}] {x.id:10} {x.categoria:24} {x.nombre[:65]}")
        print(f"\nV14.17: {ok}/{len(resultados)} OK")
    return resumen


def reporte_json(resumen: dict) -> str:
    return json.dumps(resumen,indent=2,ensure_ascii=False)


def reporte_csv(resumen: dict) -> str:
    s=io.StringIO(); campos=["id","categoria","nombre","estado","esperado","obtenido","detalle","duracion_ms"]
    w=csv.DictWriter(s,fieldnames=campos); w.writeheader()
    for r in resumen.get("resultados",[]): w.writerow({k:r.get(k,"") for k in campos})
    return s.getvalue()


def reporte_markdown(resumen: dict) -> str:
    lines=[f"# Banco maestro de regresión — {VERSION_BANCO}","",f"**Estado:** {resumen['estado']} · **OK:** {resumen['ok']}/{resumen['total']} · **Fallos:** {resumen['fallos']}","","| ID | Categoría | Estado | Caso |","|---|---|---|---|"]
    for r in resumen.get("resultados",[]):
        lines.append(f"| {r['id']} | {r['categoria']} | {r['estado']} | {r['nombre'].replace('|','/')} |")
    return "\n".join(lines)


def catalogo_casos() -> list[dict]:
    """Metadatos ligeros del banco maestro para UI/documentación."""
    out=[]
    for k in ("I_11_1","IIA_11_2","IIB_11_3","IIC_11_4","IIIA_11_5","IIIB_11_6"):
        out.append({"id":f"M-{k}","categoria":"Mott dorado","nombre":CASOS[k]["nombre"]})
    out += [{"id":cid,"categoria":"Clasificación","nombre":txt,"esperado":esp} for cid,esp,txt in CASOS_CLASIFICACION]
    out += [{"id":cid,"categoria":"Parser/unidades","nombre":txt,"esperado":esp} for cid,txt,_,esp in CASOS_PARSER]
    out += [{"id":cid,"categoria":"Accesorios/transiciones","nombre":txt,"esperado":esp} for cid,txt,_,esp,_ in CASOS_COMPONENTES]
    out += [{"id":cid,"categoria":"Flujo end-to-end","nombre":en,"esperado":esp} for cid,_,en,esp,_ in _casos_flujo()]
    out += [
        {"id":"G-01","categoria":"Guardrail","nombre":"NPS sin Schedule no inventa diámetro"},
        {"id":"G-02","categoria":"Guardrail","nombre":"Atmósfera + P2 no nula genera conflicto"},
    ]
    return out
