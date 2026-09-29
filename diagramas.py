import math
import textwrap
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyArrowPatch


G = 9.81
DIAGRAMAS_VERSION = "V14.15-avanzados-anti-solapamiento-etiquetas-graficas-v147_1"
VERSION_DIAGRAMAS_AVANZADOS = "V14.15"


def _es_deposito(tipo):
    if tipo is None:
        return False

    texto = str(tipo).lower()
    return (
        "deposito" in texto
        or "depósito" in texto
        or "reservorio" in texto
        or "superficie libre" in texto
    )


def _longitudes(tramos):
    valores = [max(float(t.get("L", 0.0) or 0.0), 1e-9) for t in tramos]
    total = sum(valores)

    if total <= 0:
        valores = [1.0] * max(1, len(tramos))
        total = float(len(valores))

    return valores, total


def _nodos_x(tramos):
    longitudes, _ = _longitudes(tramos)
    nodos = [0.0]

    acumulada = 0.0
    for L in longitudes:
        acumulada += L
        nodos.append(acumulada)

    return nodos


def _nodos_z(tramos, z1, z2, z_nodos=None):
    """Devuelve cotas gráficas válidas para todos los nodos.

    V14.17.7.4: algunos problemas aportan solo las cotas de frontera y el
    parser conserva ``None`` en uniones internas. Esos ``None`` no deben
    tumbar el diagrama. Se respetan todas las cotas internas válidas y solo
    se interpolan los huecos entre nodos conocidos usando la distancia
    acumulada real de los tramos.
    """
    cantidad = len(tramos) + 1

    def _a_float_o_none(valor):
        if valor is None:
            return None
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            return None
        return numero if math.isfinite(numero) else None

    z1f = _a_float_o_none(z1)
    z2f = _a_float_o_none(z2)

    if cantidad <= 1:
        return [0.0 if z1f is None else z1f]

    # Si z_nodos no tiene la estructura esperada, se conserva el
    # comportamiento histórico: perfil lineal entre las dos fronteras.
    if z_nodos is None or len(z_nodos) != cantidad:
        if z1f is None or z2f is None:
            raise ValueError("No hay cotas de frontera suficientes para construir el perfil gráfico.")
        return [z1f + (z2f - z1f) * i / (cantidad - 1) for i in range(cantidad)]

    zs = [_a_float_o_none(z) for z in z_nodos]

    # Las condiciones de frontera confirmadas tienen prioridad cuando el
    # vector parcial no trae los extremos.
    if zs[0] is None:
        zs[0] = z1f
    if zs[-1] is None:
        zs[-1] = z2f

    # En el flujo automático z1/z2 ya deben estar definidos. Aun así, se
    # conserva una excepción explícita en vez de crear cotas arbitrarias.
    if zs[0] is None or zs[-1] is None:
        raise ValueError("El perfil gráfico contiene nodos sin cota y faltan cotas de frontera para interpolarlos.")

    xs = _nodos_x(tramos)
    conocidos = [i for i, z in enumerate(zs) if z is not None]

    # Interpolación por distancia acumulada entre cada par de nodos conocidos.
    for ia, ib in zip(conocidos[:-1], conocidos[1:]):
        if ib - ia <= 1:
            continue
        xa, xb = xs[ia], xs[ib]
        za, zb = zs[ia], zs[ib]
        for k in range(ia + 1, ib):
            if zs[k] is not None:
                continue
            if abs(xb - xa) > 1e-14:
                frac = (xs[k] - xa) / (xb - xa)
            else:
                frac = (k - ia) / (ib - ia)
            zs[k] = za + frac * (zb - za)

    # Por construcción los extremos están definidos, por lo que cualquier
    # hueco restante sería inesperado. Se usa un error descriptivo, no float(None).
    if any(z is None for z in zs):
        raise ValueError("No fue posible completar todas las cotas internas del perfil gráfico.")

    return [float(z) for z in zs]


def _interpolar_perfil(x, xs, zs):
    if x <= xs[0]:
        return zs[0]

    if x >= xs[-1]:
        return zs[-1]

    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            dx = xs[i + 1] - xs[i]
            if abs(dx) < 1e-14:
                return zs[i]

            fraccion = (x - xs[i]) / dx
            return zs[i] + fraccion * (zs[i + 1] - zs[i])

    return zs[-1]


def _eventos_accesorios(tramos):
    """
    Devuelve eventos gráficos de accesorios con posición absoluta x.

    Cada accesorio se guarda en app.py con posicion_fraccion entre 0 y 1.
    Si no existe ese dato se ubica al 70 % del tramo como valor visual por defecto.
    """

    eventos = []
    x0 = 0.0

    for indice, tramo in enumerate(tramos, start=1):
        L = max(float(tramo.get("L", 0.0) or 0.0), 0.0)
        detalles = tramo.get("accesorios_detalle") or []

        for item in detalles:
            nombre = str(item.get("nombre", "Accesorio"))
            cantidad = max(1, int(item.get("cantidad", 1) or 1))
            valor_pos = item.get("posicion_fraccion")
            fraccion = 0.70 if valor_pos is None else float(valor_pos)
            fraccion = min(max(fraccion, 0.0), 1.0)

            eventos.append(
                {
                    "x": x0 + fraccion * L,
                    "nombre": nombre,
                    "cantidad": cantidad,
                    "tramo": indice,
                    "tipo": "accesorio",
                }
            )

        k_extra = float(tramo.get("K_extra", 0.0) or 0.0)
        if k_extra > 0:
            valor_pos_extra = tramo.get("K_extra_posicion_fraccion")
            fraccion_extra = 0.85 if valor_pos_extra is None else float(valor_pos_extra)
            fraccion_extra = min(max(fraccion_extra, 0.0), 1.0)
            eventos.append(
                {
                    "x": x0 + fraccion_extra * L,
                    "nombre": f"K adicional = {k_extra:.3g}",
                    "cantidad": 1,
                    "tramo": indice,
                    "tipo": "k_extra",
                }
            )

        # Componentes detectados por texto cuya naturaleza hidráulica aún no
        # está suficientemente definida (por ejemplo, "una válvula a 20 m"
        # sin indicar si es de globo, compuerta, etc.). Se dibujan, pero NO
        # generan una pérdida hasta que el usuario seleccione tipo/K.
        for componente in tramo.get("componentes_graficos") or []:
            valor_pos_comp = componente.get("posicion_fraccion")
            fraccion = 0.5 if valor_pos_comp is None else float(valor_pos_comp)
            fraccion = min(max(fraccion, 0.0), 1.0)
            eventos.append(
                {
                    "x": x0 + fraccion * L,
                    "nombre": componente.get("nombre", "Componente"),
                    "cantidad": 1,
                    "tramo": indice,
                    "tipo": "grafico_sin_k",
                }
            )

        x0 += L

    return eventos


def _ancho_tuberia(D, D_min, D_max):
    if D_max <= D_min + 1e-14:
        return 3.0

    fraccion = (D - D_min) / (D_max - D_min)
    return 2.5 + 3.0 * min(max(fraccion, 0.0), 1.0)


def _texto_envuelto(texto, ancho=24):
    """Envuelve etiquetas largas para reducir solapamientos horizontales."""
    return "\n".join(textwrap.wrap(str(texto), width=ancho)) or str(texto)


def _carril_etiqueta(x, eventos_previos, total_L):
    """Asigna lado y nivel vertical procurando separar etiquetas cercanas."""
    umbral = max(total_L * 0.10, 6.0)
    cercanos_arriba = 0
    cercanos_abajo = 0

    for previo in eventos_previos:
        if abs(float(previo["x"]) - float(x)) <= umbral:
            if previo["lado"] > 0:
                cercanos_arriba += 1
            else:
                cercanos_abajo += 1

    # Se usa el lado menos ocupado. En empate se alterna automáticamente.
    if cercanos_arriba < cercanos_abajo:
        lado = 1
        nivel = cercanos_arriba
    elif cercanos_abajo < cercanos_arriba:
        lado = -1
        nivel = cercanos_abajo
    else:
        lado = 1 if len(eventos_previos) % 2 else -1
        nivel = cercanos_arriba if lado > 0 else cercanos_abajo

    return lado, min(nivel, 3)


def _bbox_con_margen(bbox, margen_px=4.0):
    """Amplía un bbox en píxeles para exigir separación visual entre etiquetas."""
    return (
        float(bbox.x0) - margen_px,
        float(bbox.y0) - margen_px,
        float(bbox.x1) + margen_px,
        float(bbox.y1) + margen_px,
    )


def _bboxes_solapan(a, b, margen_px=4.0):
    ax0, ay0, ax1, ay1 = _bbox_con_margen(a, margen_px)
    bx0, by0, bx1, by1 = _bbox_con_margen(b, margen_px)
    return not (ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0)


def _bbox_etiqueta(artista, renderer):
    """BBox solo del cuadro/texto, excluyendo la flecha de Annotation."""
    parche = artista.get_bbox_patch() if hasattr(artista, "get_bbox_patch") else None
    if parche is not None:
        return parche.get_window_extent(renderer=renderer)
    return artista.get_window_extent(renderer=renderer)


def _desplazar_texto_vertical_px(ax, artista, delta_px):
    """Mueve Text/Annotation verticalmente una cantidad de píxeles en coordenadas de datos."""
    x, y = artista.get_position()
    px, py = ax.transData.transform((float(x), float(y)))
    _, y_nuevo = ax.transData.inverted().transform((px, py + float(delta_px)))
    artista.set_position((float(x), float(y_nuevo)))


def _resolver_solapamientos_etiquetas(fig, ax, registros, max_iter=80):
    """Separa automáticamente cajas de texto que se montan unas sobre otras.

    Trabaja después de crear el esquema y antes de ``tight_layout``. Cada registro
    contiene ``artista`` y un ``lado`` preferido (+1 arriba, -1 abajo). La rutina
    usa los bounding boxes reales del renderer, por lo que también funciona cuando
    una etiqueta tiene varias líneas o cambia de tamaño por el contenido.
    """
    registros = [r for r in (registros or []) if r.get("artista") is not None]
    if len(registros) < 2:
        return

    # Mantiene la dirección inicial de cada etiqueta. Si hay empate/centro, alterna.
    for i, r in enumerate(registros):
        lado = int(r.get("lado", 0) or 0)
        r["lado"] = lado if lado in (-1, 1) else (1 if i % 2 else -1)

    for _ in range(int(max_iter)):
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        hubo_movimiento = False

        # Se preserva el orden de creación: las etiquetas estructurales se colocan
        # primero y los accesorios/transiciones se adaptan alrededor de ellas.
        for j in range(1, len(registros)):
            actual = registros[j]
            art = actual["artista"]
            bbox_actual = _bbox_etiqueta(art, renderer)

            conflictos = []
            for previo in registros[:j]:
                bbox_previo = _bbox_etiqueta(previo["artista"], renderer)
                if _bboxes_solapan(bbox_actual, bbox_previo, margen_px=5.0):
                    conflictos.append(bbox_previo)

            if not conflictos:
                continue

            lado = actual["lado"]
            # El salto mínimo evita iteraciones microscópicas; si el solapamiento
            # es grande se usa la altura real de ambas cajas.
            alto = max([bbox_actual.height] + [b.height for b in conflictos])
            delta = lado * max(16.0, 0.62 * alto + 8.0)
            _desplazar_texto_vertical_px(ax, art, delta)
            hubo_movimiento = True
            break

        if not hubo_movimiento:
            break

    # Una pasada adicional separa cajas que queden apenas tocándose después de
    # cambios de escala/tamaño del canvas.
    fig.canvas.draw()



def _agrupar_eventos_para_etiquetas(eventos, total_L, tolerancia_m=None):
    """Agrupa eventos cercanos en x para evitar rótulos montados.

    Se usa en LE/LAM y pérdidas acumuladas, donde varios accesorios pueden
    caer prácticamente en la misma abscisa.
    """
    eventos = sorted(eventos or [], key=lambda e: float(e.get("x", 0.0) or 0.0))
    if not eventos:
        return []

    if tolerancia_m is None:
        tolerancia_m = max(float(total_L) * 0.03, 4.0)

    grupos = []
    actual = [eventos[0]]

    for evento in eventos[1:]:
        x_evt = float(evento.get("x", 0.0) or 0.0)
        x_ref = sum(float(e.get("x", 0.0) or 0.0) for e in actual) / len(actual)
        if abs(x_evt - x_ref) <= tolerancia_m:
            actual.append(evento)
        else:
            grupos.append(actual)
            actual = [evento]

    grupos.append(actual)
    return grupos


def _texto_grupo_eventos(grupo, ancho=28, max_lineas=4):
    """Convierte un grupo de eventos cercanos en un texto compacto."""
    contador = {}
    orden = []
    for evento in grupo:
        etiqueta = str(evento.get("etiqueta") or evento.get("nombre") or evento.get("tipo") or "Evento").strip()
        if etiqueta not in contador:
            contador[etiqueta] = 0
            orden.append(etiqueta)
        contador[etiqueta] += 1

    lineas = []
    for etiqueta in orden:
        prefijo = f"{contador[etiqueta]}× " if contador[etiqueta] > 1 else ""
        wrapped = textwrap.wrap(prefijo + etiqueta, width=ancho) or [prefijo + etiqueta]
        if len(wrapped) > 2:
            wrapped = wrapped[:2]
            wrapped[-1] = (wrapped[-1][: max(0, ancho - 1)] + "…") if len(wrapped[-1]) >= ancho else wrapped[-1] + " …"
        lineas.extend(wrapped)

    if len(lineas) > max_lineas:
        restantes = len(lineas) - max_lineas + 1
        lineas = lineas[: max_lineas - 1] + [f"+{restantes} evento(s)…"]

    return "\n".join(lineas)


def _nivel_superior_por_proximidad(x, registros, total_L, max_niveles=4):
    """Asigna carriles superiores para rótulos de gráficas."""
    umbral = max(float(total_L) * 0.10, 8.0)
    ocupados = {int(r.get("nivel", 0) or 0) for r in registros if abs(float(r.get("x", 0.0)) - float(x)) <= umbral}
    for nivel in range(max_niveles):
        if nivel not in ocupados:
            return nivel
    return max_niveles - 1


def _anotar_eventos_sin_solapamiento_en_grafica(ax, eventos, xs_ref, ys_ref, total_L):
    """Dibuja rótulos de eventos agrupados y escalonados sin montajes."""
    if not eventos:
        return

    y_datos_min = min(float(y) for y in ys_ref)
    y_datos_max = max(float(y) for y in ys_ref)
    rango = max(y_datos_max - y_datos_min, 1.0)

    ylim_actual = ax.get_ylim()
    y_min = min(ylim_actual[0], y_datos_min - 0.05 * rango)
    y_max = max(ylim_actual[1], y_datos_max + 0.32 * rango)
    ax.set_ylim(y_min, y_max)

    grupos = _agrupar_eventos_para_etiquetas(eventos, total_L)
    registros = []

    for grupo in grupos:
        xg = sum(float(e.get("x", 0.0) or 0.0) for e in grupo) / len(grupo)
        nivel = _nivel_superior_por_proximidad(xg, registros, total_L, max_niveles=4)
        y_punta = _valor_serie_en_x(xs_ref, ys_ref, xg)
        y_texto = y_datos_max + (0.08 + 0.07 * nivel) * rango
        texto = _texto_grupo_eventos(grupo, ancho=30, max_lineas=4)

        ax.annotate(
            texto,
            xy=(xg, y_punta),
            xytext=(xg, y_texto),
            textcoords="data",
            ha="center",
            va="bottom",
            fontsize=6.8,
            rotation=0,
            bbox={"boxstyle": "round,pad=0.18", "fc": "white", "ec": "0.55", "alpha": 0.92},
            arrowprops={"arrowstyle": "-", "linewidth": 0.45, "color": "0.35"},
            annotation_clip=False,
            zorder=5,
        )
        registros.append({"x": xg, "nivel": nivel})


def crear_esquema_sistema(
    tramos,
    z1=0.0,
    z2=0.0,
    tipo_v1="tuberia",
    tipo_v2="tuberia",
    hA=0.0,
    hR=0.0,
    posicion_bomba=None,
    posicion_turbina=None,
    z_nodos=None,
    transiciones=None,
    titulo="Esquema hidráulico del sistema",
    mostrar_etiquetas_tramos=True,
    mostrar_etiquetas_accesorios=True,
    mostrar_etiquetas_transiciones=True,
    mostrar_etiquetas_equipos=True,
    mostrar_sentido_flujo=True,
):
    """
    Genera un esquema hidráulico con perfil vertical, diámetros, accesorios
    y posición configurable de bomba/turbina.

    Las distancias horizontales sí siguen las longitudes de los tramos.
    Las elevaciones siguen z_nodos cuando se suministran; de lo contrario
    se interpola entre z1 y z2.
    """

    if not tramos:
        raise ValueError("No hay tramos para dibujar el esquema.")

    xs = _nodos_x(tramos)
    zs = _nodos_z(tramos, z1, z2, z_nodos=z_nodos)
    total_L = xs[-1]

    diametros = [max(float(t.get("D", 0.0) or 0.0), 0.0) for t in tramos]
    D_min = min(diametros) if diametros else 0.0
    D_max = max(diametros) if diametros else 0.0

    rango_z = max(max(zs) - min(zs), 1.0)
    margen_x = max(total_L * 0.07, 0.8)
    margen_z = max(rango_z * 0.35, 1.0)

    n_eventos_previstos = len(_eventos_accesorios(tramos)) + len(transiciones or [])
    alto_fig = min(8.6, 6.6 + 0.16 * max(0, n_eventos_previstos - 2))
    fig, ax = plt.subplots(figsize=(13.8, alto_fig))
    etiquetas_dinamicas = []

    # Tuberías y etiquetas por tramo
    for i, tramo in enumerate(tramos):
        x_a, x_b = xs[i], xs[i + 1]
        z_a, z_b = zs[i], zs[i + 1]
        D = max(float(tramo.get("D", 0.0) or 0.0), 0.0)
        L = max(float(tramo.get("L", 0.0) or 0.0), 0.0)
        material = tramo.get("material") or ""

        ax.plot(
            [x_a, x_b],
            [z_a, z_b],
            linewidth=_ancho_tuberia(D, D_min, D_max),
            solid_capstyle="round",
        )

        x_m = (x_a + x_b) / 2
        z_m = (z_a + z_b) / 2

        if mostrar_etiquetas_tramos:
            etiqueta = f"Tramo {i + 1}\nL={L:.4g} m"
            if D > 0:
                etiqueta += f"   D={D:.4g} m"
            if material:
                etiqueta += f"\n{material}"

            lado_tramo = 1 if i % 2 == 0 else -1
            etiqueta_tramo = ax.text(
                x_m,
                z_m + lado_tramo * margen_z * 0.56,
                etiqueta,
                ha="center",
                va="bottom" if lado_tramo > 0 else "top",
                fontsize=8,
                bbox={"boxstyle": "round,pad=0.18", "facecolor": "white", "alpha": 0.78, "linewidth": 0.35},
                clip_on=False,
            )
            etiquetas_dinamicas.append({"artista": etiqueta_tramo, "lado": lado_tramo, "tipo": "tramo"})

        # Nodo/intersección
        if i < len(tramos) - 1:
            ax.add_patch(Circle((x_b, z_b), radius=max(total_L * 0.0035, 0.04), fill=False))
            if mostrar_etiquetas_tramos:
                desplazamiento_union = total_L * (0.014 if i % 2 == 0 else -0.014)
                etiqueta_union = ax.text(
                    x_b + desplazamiento_union,
                    z_b - margen_z * 0.40,
                    f"Unión {i + 1}\nz={z_b:.4g} m",
                    ha="center",
                    va="top",
                    fontsize=7.2,
                    bbox={"boxstyle": "round,pad=0.12", "facecolor": "white", "alpha": 0.70, "linewidth": 0.3},
                    clip_on=False,
                )
                etiquetas_dinamicas.append({"artista": etiqueta_union, "lado": -1, "tipo": "union"})

    # Depósitos o puntos extremos
    alto_dep = max(rango_z * 0.45, 1.2)
    ancho_dep = max(total_L * 0.045, 0.7)

    if _es_deposito(tipo_v1):
        ax.add_patch(
            Rectangle(
                (xs[0] - ancho_dep, zs[0] - alto_dep * 0.55),
                ancho_dep,
                alto_dep,
                fill=False,
                linewidth=1.5,
            )
        )
        ax.plot(
            [xs[0] - ancho_dep, xs[0]],
            [zs[0], zs[0]],
            linewidth=1.1,
        )
        ax.text(
            xs[0] - ancho_dep / 2,
            zs[0] + alto_dep * 0.56,
            f"Depósito 1\nz1={float(z1):.4g} m",
            ha="center",
            va="bottom",
            fontsize=8,
        )
    else:
        ax.add_patch(Circle((xs[0], zs[0]), radius=max(total_L * 0.004, 0.05), fill=False))
        ax.text(
            xs[0],
            zs[0] + margen_z * 0.16,
            f"Punto 1\nz1={float(z1):.4g} m",
            ha="center",
            fontsize=8,
        )

    if _es_deposito(tipo_v2):
        ax.add_patch(
            Rectangle(
                (xs[-1], zs[-1] - alto_dep * 0.55),
                ancho_dep,
                alto_dep,
                fill=False,
                linewidth=1.5,
            )
        )
        ax.plot(
            [xs[-1], xs[-1] + ancho_dep],
            [zs[-1], zs[-1]],
            linewidth=1.1,
        )
        ax.text(
            xs[-1] + ancho_dep / 2,
            zs[-1] + alto_dep * 0.56,
            f"Depósito 2\nz2={float(z2):.4g} m",
            ha="center",
            va="bottom",
            fontsize=8,
        )
    else:
        ax.add_patch(Circle((xs[-1], zs[-1]), radius=max(total_L * 0.004, 0.05), fill=False))
        ax.text(
            xs[-1],
            zs[-1] + margen_z * 0.16,
            f"Punto 2\nz2={float(z2):.4g} m",
            ha="center",
            fontsize=8,
        )

    # Accesorios en posiciones reales/seleccionadas dentro de cada tramo.
    # Las etiquetas se distribuyen en carriles alternos para evitar que queden
    # todas superpuestas cuando existen muchos accesorios próximos.
    eventos_acc = sorted(_eventos_accesorios(tramos), key=lambda e: float(e["x"]))
    etiquetas_colocadas = []

    for evento in eventos_acc:
        x = float(evento["x"])
        z = _interpolar_perfil(x, xs, zs)
        radio = max(total_L * 0.0032, 0.04)
        ax.add_patch(Circle((x, z), radius=radio, fill=False, linewidth=1.1))

        if not mostrar_etiquetas_accesorios:
            continue

        texto = evento["nombre"]
        if evento.get("cantidad", 1) > 1:
            texto = f"{evento['cantidad']}× {texto}"
        texto = _texto_envuelto(texto, ancho=23)

        lado, nivel = _carril_etiqueta(x, etiquetas_colocadas, total_L)
        desplazamiento_y = margen_z * (0.26 + 0.18 * nivel) * lado
        desplazamiento_x = total_L * (0.008 if lado > 0 else -0.008)

        etiqueta_acc = ax.annotate(
            f"{texto}\nx={x:.2f} m",
            xy=(x, z),
            xytext=(x + desplazamiento_x, z + desplazamiento_y),
            ha="center",
            va="bottom" if lado > 0 else "top",
            fontsize=6.8,
            arrowprops={"arrowstyle": "-", "linewidth": 0.65},
            bbox={"boxstyle": "round,pad=0.18", "facecolor": "white", "alpha": 0.84, "linewidth": 0.4},
            annotation_clip=False,
        )

        etiquetas_colocadas.append({"x": x, "lado": lado})
        etiquetas_dinamicas.append({"artista": etiqueta_acc, "lado": lado, "tipo": "accesorio"})

    # Transiciones geométricas entre tramos (contracciones/ensanchamientos).
    # Se dibujan en la unión correspondiente. El cambio de espesor de la línea
    # ya representa el cambio de diámetro; esta etiqueta añade el modelo Mott
    # y la pérdida calculada sin saturar el esquema.
    if transiciones:
        for item in transiciones:
            try:
                entre = int(item.get("entre", 0) or 0)
            except (TypeError, ValueError):
                entre = 0

            if entre < 1 or entre >= len(xs):
                continue

            x = float(xs[entre])
            z = float(zs[entre])
            tipo = str(item.get("tipo", "Transición"))
            K = float(item.get("K", 0.0) or 0.0)
            hL = float(item.get("hL", 0.0) or 0.0)
            angulo = item.get("angulo_grados")

            # La unión ya marca geométricamente el cambio de diámetro. En modo
            # compacto se conserva un marcador discreto pero se oculta la caja.
            ax.scatter([x], [z], marker="D", s=24)
            if not mostrar_etiquetas_transiciones:
                continue

            texto = _texto_envuelto(tipo, ancho=20)
            if angulo is not None:
                texto += f"\nθ={float(angulo):.3g}°"
            texto += f"\nK={K:.4g}; hL={hL:.4g} m"

            lado, nivel = _carril_etiqueta(x, etiquetas_colocadas, total_L)
            desplazamiento_y = margen_z * (0.50 + 0.18 * nivel) * lado
            desplazamiento_x = total_L * (0.012 if lado > 0 else -0.012)

            etiqueta_trans = ax.annotate(
                texto,
                xy=(x, z),
                xytext=(x + desplazamiento_x, z + desplazamiento_y),
                ha="center",
                va="bottom" if lado > 0 else "top",
                fontsize=6.9,
                arrowprops={"arrowstyle": "->", "linewidth": 0.75},
                bbox={"boxstyle": "round,pad=0.20", "facecolor": "white", "alpha": 0.88, "linewidth": 0.5},
                annotation_clip=False,
            )
            etiquetas_colocadas.append({"x": x, "lado": lado})
            etiquetas_dinamicas.append({"artista": etiqueta_trans, "lado": lado, "tipo": "transicion"})

    # Posición de bomba y turbina
    if (hA or 0.0) > 0:
        if posicion_bomba is None:
            posicion_bomba = total_L * 0.05

        x_bomba = min(max(float(posicion_bomba), 0.0), total_L)
        z_bomba = _interpolar_perfil(x_bomba, xs, zs)
        radio = max(total_L * 0.010, 0.12)

        ax.add_patch(Circle((x_bomba, z_bomba), radius=radio, fill=False, linewidth=1.6))
        ax.text(x_bomba, z_bomba, "B", ha="center", va="center", fontsize=9, fontweight="bold")
        if mostrar_etiquetas_equipos:
            etiqueta_bomba = ax.annotate(
                f"Bomba\nhA={float(hA):.4g} m\nx={x_bomba:.4g} m",
                xy=(x_bomba, z_bomba),
                xytext=(x_bomba - total_L * 0.018, z_bomba + margen_z * 0.52),
                ha="center",
                fontsize=7.5,
                arrowprops={"arrowstyle": "-", "linewidth": 0.7},
                bbox={"boxstyle": "round,pad=0.20", "facecolor": "white", "alpha": 0.86, "linewidth": 0.5},
                annotation_clip=False,
            )
            etiquetas_dinamicas.append({"artista": etiqueta_bomba, "lado": 1, "tipo": "bomba"})

    if (hR or 0.0) > 0:
        if posicion_turbina is None:
            posicion_turbina = total_L * 0.75

        x_turbina = min(max(float(posicion_turbina), 0.0), total_L)
        z_turbina = _interpolar_perfil(x_turbina, xs, zs)
        radio = max(total_L * 0.010, 0.12)

        ax.add_patch(Circle((x_turbina, z_turbina), radius=radio, fill=False, linewidth=1.6))
        ax.text(x_turbina, z_turbina, "T", ha="center", va="center", fontsize=9, fontweight="bold")
        if mostrar_etiquetas_equipos:
            etiqueta_turbina = ax.annotate(
                f"Turbina\nhR={float(hR):.4g} m\nx={x_turbina:.4g} m",
                xy=(x_turbina, z_turbina),
                xytext=(x_turbina + total_L * 0.018, z_turbina + margen_z * 0.52),
                ha="center",
                fontsize=7.5,
                arrowprops={"arrowstyle": "-", "linewidth": 0.7},
                bbox={"boxstyle": "round,pad=0.20", "facecolor": "white", "alpha": 0.86, "linewidth": 0.5},
                annotation_clip=False,
            )
            etiquetas_dinamicas.append({"artista": etiqueta_turbina, "lado": 1, "tipo": "turbina"})

    # Flecha de flujo
    if total_L > 0:
        x_f1 = total_L * 0.08
        x_f2 = total_L * 0.20
        z_f1 = _interpolar_perfil(x_f1, xs, zs)
        z_f2 = _interpolar_perfil(x_f2, xs, zs)

        flecha = FancyArrowPatch(
            (x_f1, z_f1 + margen_z * 0.08),
            (x_f2, z_f2 + margen_z * 0.08),
            arrowstyle="->",
            mutation_scale=14,
            linewidth=1.2,
        )
        ax.add_patch(flecha)
        if mostrar_sentido_flujo:
            etiqueta_flujo = ax.text(
                (x_f1 + x_f2) / 2,
                (z_f1 + z_f2) / 2 + margen_z * 0.17,
                "Sentido del flujo",
                ha="center",
                fontsize=7.5,
                bbox={"boxstyle": "round,pad=0.12", "facecolor": "white", "alpha": 0.72, "linewidth": 0.3},
                clip_on=False,
            )
            etiquetas_dinamicas.append({"artista": etiqueta_flujo, "lado": 1, "tipo": "flujo"})

    ax.set_xlabel("Distancia acumulada (m)")
    ax.set_ylabel("Elevación geométrica z (m)")
    ax.set_title(titulo)
    ax.grid(True, alpha=0.18)

    ax.set_xlim(xs[0] - margen_x - ancho_dep * int(_es_deposito(tipo_v1)), xs[-1] + margen_x + ancho_dep * int(_es_deposito(tipo_v2)))
    ax.set_ylim(min(zs) - margen_z * 1.65, max(zs) + margen_z * 1.85)

    # V14.7: usa los bounding boxes reales del renderizador para separar
    # automáticamente cuadros de texto que todavía puedan tocarse.
    _resolver_solapamientos_etiquetas(fig, ax, etiquetas_dinamicas)

    fig.text(
        0.5,
        0.02,
        "Las distancias horizontales siguen las longitudes indicadas. El perfil vertical usa las elevaciones definidas por el usuario.",
        ha="center",
        fontsize=8,
    )

    fig.tight_layout(rect=(0, 0.05, 1, 1))
    return fig


def _gradientes_friccion(resultados):
    gradientes = []
    inicio = 0.0

    for fila in resultados:
        L = max(float(fila.get("L (m)", 0.0) or 0.0), 0.0)
        hf = float(fila.get("hf (m)", 0.0) or 0.0)
        fin = inicio + L
        gradiente = hf / L if L > 0 else 0.0
        gradientes.append((inicio, fin, gradiente))
        inicio = fin

    return gradientes


def _perdida_friccion_entre(xa, xb, gradientes):
    perdida = 0.0

    for inicio, fin, gradiente in gradientes:
        solape = max(0.0, min(xb, fin) - max(xa, inicio))
        perdida += gradiente * solape

    return perdida


def _velocidad_en_x(x, resultados, lado="derecha"):
    acumulada = 0.0
    total = sum(float(f.get("L (m)", 0.0) or 0.0) for f in resultados)

    if not resultados:
        return 0.0

    if x <= 0:
        return float(resultados[0].get("V (m/s)", 0.0) or 0.0)

    for i, fila in enumerate(resultados):
        L = float(fila.get("L (m)", 0.0) or 0.0)
        fin = acumulada + L

        if x < fin - 1e-12:
            return float(fila.get("V (m/s)", 0.0) or 0.0)

        if abs(x - fin) <= 1e-12:
            if lado == "derecha" and i + 1 < len(resultados):
                return float(resultados[i + 1].get("V (m/s)", 0.0) or 0.0)
            return float(fila.get("V (m/s)", 0.0) or 0.0)

        acumulada = fin

    return float(resultados[-1].get("V (m/s)", 0.0) or 0.0)


def _eventos_perdidas_menores(tramos, resultados):
    """
    Distribuye hm de cada tramo entre sus accesorios proporcionalmente a K.
    Si no hay detalle, deja una pérdida concentrada al final del tramo.
    """

    eventos = []
    x0 = 0.0

    for i, (tramo, fila) in enumerate(zip(tramos, resultados), start=1):
        L = max(float(tramo.get("L", fila.get("L (m)", 0.0)) or 0.0), 0.0)
        hm_tramo = float(fila.get("hm (m)", 0.0) or 0.0)
        K_total = float(tramo.get("K", fila.get("ΣK", 0.0)) or 0.0)
        detalles = tramo.get("accesorios_detalle") or []
        k_extra = float(tramo.get("K_extra", 0.0) or 0.0)

        if hm_tramo <= 0:
            x0 += L
            continue

        if K_total > 0 and (detalles or k_extra > 0):
            k_reconstruido = 0.0

            for item in detalles:
                k_unit = float(item.get("K_unitario", 0.0) or 0.0)
                cantidad = max(1, int(item.get("cantidad", 1) or 1))
                k_item = k_unit * cantidad
                k_reconstruido += k_item

                if k_item <= 0:
                    continue

                valor_pos = item.get("posicion_fraccion")
                fraccion = 0.70 if valor_pos is None else float(valor_pos)
                fraccion = min(max(fraccion, 0.0), 1.0)

                eventos.append(
                    {
                        "x": x0 + fraccion * L,
                        "delta": -hm_tramo * (k_item / K_total),
                        "tipo": "menor",
                        "etiqueta": item.get("nombre", "Accesorio"),
                    }
                )

            if k_extra > 0:
                valor_pos_extra = tramo.get("K_extra_posicion_fraccion")
                fraccion_extra = 0.85 if valor_pos_extra is None else float(valor_pos_extra)
                fraccion_extra = min(max(fraccion_extra, 0.0), 1.0)
                eventos.append(
                    {
                        "x": x0 + fraccion_extra * L,
                        "delta": -hm_tramo * (k_extra / K_total),
                        "tipo": "menor",
                        "etiqueta": "K adicional",
                    }
                )

            # Si por alguna razón el K reconstruido no coincide, la diferencia
            # se concentra al final del tramo para conservar exactamente hm.
            k_reconstruido += k_extra
            if K_total > 0 and k_reconstruido < K_total - 1e-12:
                fraccion_restante = (K_total - k_reconstruido) / K_total
                eventos.append(
                    {
                        "x": x0 + L,
                        "delta": -hm_tramo * fraccion_restante,
                        "tipo": "menor",
                        "etiqueta": "Pérdida menor restante",
                    }
                )

        else:
            eventos.append(
                {
                    "x": x0 + L,
                    "delta": -hm_tramo,
                    "tipo": "menor",
                    "etiqueta": f"Pérdida menor tramo {i}",
                }
            )

        x0 += L

    return eventos


def _valor_serie_en_x(xs, ys, x):
    """Último valor de una serie escalonada en x, útil para anotar eventos."""
    valor = ys[0] if ys else 0.0
    for xx, yy in zip(xs, ys):
        if float(xx) <= float(x) + 1e-12:
            valor = yy
        else:
            break
    return float(valor)


def crear_lineas_energia(
    resultados,
    gamma,
    P1,
    z1,
    P2,
    z2,
    V1,
    V2,
    hA=0.0,
    hR=0.0,
    tramos=None,
    posicion_bomba=None,
    posicion_turbina=None,
    transiciones=None,
    g=G,
    titulo="Línea de energía y línea piezométrica",
    mostrar_marcadores_eventos=True,
    mostrar_etiquetas_eventos=False,
):
    """
    Dibuja LE/EGL y LAM/HGL ubicando las máquinas y pérdidas menores
    en las posiciones seleccionadas por el usuario.
    """

    if not resultados:
        raise ValueError("No hay resultados hidráulicos para construir LE/LAM.")

    if gamma <= 0:
        raise ValueError("El peso específico debe ser mayor que cero.")

    total_L = sum(float(f.get("L (m)", 0.0) or 0.0) for f in resultados)
    E1 = float(P1) / gamma + float(z1) + float(V1) ** 2 / (2 * g)
    E2_obj = float(P2) / gamma + float(z2) + float(V2) ** 2 / (2 * g)

    gradientes = _gradientes_friccion(resultados)

    eventos = []

    if (hA or 0.0) > 0:
        x_b = total_L * 0.05 if posicion_bomba is None else float(posicion_bomba)
        x_b = min(max(x_b, 0.0), total_L)
        eventos.append(
            {
                "x": x_b,
                "delta": float(hA),
                "tipo": "bomba",
                "etiqueta": "Bomba",
            }
        )

    if (hR or 0.0) > 0:
        x_t = total_L * 0.75 if posicion_turbina is None else float(posicion_turbina)
        x_t = min(max(x_t, 0.0), total_L)
        eventos.append(
            {
                "x": x_t,
                "delta": -float(hR),
                "tipo": "turbina",
                "etiqueta": "Turbina",
            }
        )

    if tramos is not None:
        eventos.extend(_eventos_perdidas_menores(tramos, resultados))
    else:
        x0 = 0.0
        for i, fila in enumerate(resultados, start=1):
            L = float(fila.get("L (m)", 0.0) or 0.0)
            hm = float(fila.get("hm (m)", 0.0) or 0.0)
            x0 += L
            if hm > 0:
                eventos.append(
                    {
                        "x": x0,
                        "delta": -hm,
                        "tipo": "menor",
                        "etiqueta": f"Pérdida menor tramo {i}",
                    }
                )

    # Pérdidas concentradas asociadas a contracciones/ensanchamientos.
    # Se tratan como pérdidas menores en la LE/LAM y se ubican exactamente
    # en la unión entre los dos tramos.
    if transiciones:
        xs_nodos = [0.0]
        acumulada_t = 0.0
        for fila in resultados:
            acumulada_t += float(fila.get("L (m)", 0.0) or 0.0)
            xs_nodos.append(acumulada_t)

        for item in transiciones:
            try:
                entre = int(item.get("entre", 0) or 0)
            except (TypeError, ValueError):
                entre = 0

            if entre < 1 or entre >= len(xs_nodos):
                continue

            hL_trans = float(item.get("hL", 0.0) or 0.0)
            if hL_trans <= 0:
                continue

            eventos.append(
                {
                    "x": float(xs_nodos[entre]),
                    "delta": -hL_trans,
                    "tipo": "menor",
                    "etiqueta": f"Transición: {item.get('tipo', 'cambio de diámetro')}",
                }
            )

    # Uniones de tramos son puntos de cambio de velocidad.
    uniones = []
    acumulada = 0.0
    for fila in resultados[:-1]:
        acumulada += float(fila.get("L (m)", 0.0) or 0.0)
        uniones.append(acumulada)

    puntos = {0.0, total_L}
    puntos.update(uniones)
    puntos.update(evento["x"] for evento in eventos)
    puntos_ordenados = sorted(puntos)

    eventos_por_x = {}
    for evento in eventos:
        eventos_por_x.setdefault(round(evento["x"], 12), []).append(evento)

    x_egl = [0.0]
    y_egl = [E1]
    x_hgl = [0.0]
    y_hgl = [E1 - float(V1) ** 2 / (2 * g)]

    energia = E1
    x_prev = 0.0

    # Al entrar al primer tramo, la LE no cambia pero la LAM refleja V del tubo.
    V_pipe_0 = _velocidad_en_x(0.0, resultados, lado="derecha")
    if abs(V_pipe_0 - float(V1)) > 1e-12:
        x_egl.append(0.0)
        y_egl.append(energia)
        x_hgl.append(0.0)
        y_hgl.append(energia - V_pipe_0**2 / (2 * g))

    for x in puntos_ordenados[1:]:
        # Fricción distribuida entre puntos consecutivos.
        perdida_f = _perdida_friccion_entre(x_prev, x, gradientes)
        energia -= perdida_f

        V_izq = _velocidad_en_x(x, resultados, lado="izquierda")
        x_egl.append(x)
        y_egl.append(energia)
        x_hgl.append(x)
        y_hgl.append(energia - V_izq**2 / (2 * g))

        # Eventos concentrados en x: bomba, turbina o pérdidas menores.
        for evento in eventos_por_x.get(round(x, 12), []):
            energia += evento["delta"]
            V_evento = _velocidad_en_x(x, resultados, lado="derecha")

            x_egl.append(x)
            y_egl.append(energia)
            x_hgl.append(x)
            y_hgl.append(energia - V_evento**2 / (2 * g))

        # Cambio de diámetro/velocidad en una unión.
        if any(abs(x - u) < 1e-10 for u in uniones):
            V_der = _velocidad_en_x(x, resultados, lado="derecha")
            x_egl.append(x)
            y_egl.append(energia)
            x_hgl.append(x)
            y_hgl.append(energia - V_der**2 / (2 * g))

        x_prev = x

    # Ajuste de la HGL a la condición de frontera del punto 2.
    x_egl.append(total_L)
    y_egl.append(energia)
    x_hgl.append(total_L)
    y_hgl.append(energia - float(V2) ** 2 / (2 * g))

    fig, ax = plt.subplots(figsize=(11.5, 5.8))
    ax.plot(x_egl, y_egl, marker="o", label="LE / EGL")
    ax.plot(x_hgl, y_hgl, marker="s", label="LAM / HGL")

    ax.scatter([0.0], [E1], marker="x", s=70, label="E1")
    ax.scatter([total_L], [E2_obj], marker="x", s=70, label="E2 por frontera")

    # V14.15: marcas de máquinas, accesorios y transiciones. Las etiquetas
    # pueden ocultarse en esquemas densos sin retirar los eventos hidráulicos.
    if mostrar_marcadores_eventos:
        for evento in eventos:
            ax.axvline(evento["x"], linestyle="--", linewidth=0.65, alpha=0.32)
        if mostrar_etiquetas_eventos:
            _anotar_eventos_sin_solapamiento_en_grafica(
                ax=ax,
                eventos=eventos,
                xs_ref=x_egl,
                ys_ref=y_egl + y_hgl,
                total_L=total_L,
            )

    ax.set_xlabel("Distancia acumulada a lo largo de la tubería (m)")
    ax.set_ylabel("Carga (m de fluido)")
    ax.set_title(titulo)
    ax.grid(True, alpha=0.25)
    ax.legend()

    residual_grafico = energia - E2_obj

    ax.text(
        0.01,
        0.02,
        f"Residual gráfico final = {residual_grafico:.3e} m\n"
        "La fricción se distribuye por tramo; máquinas, accesorios y transiciones se aplican en su posición correspondiente.",
        transform=ax.transAxes,
        fontsize=8,
        va="bottom",
    )

    fig.tight_layout()
    return fig


# ============================================================
# V14.15 — Diagramas hidráulicos avanzados
# ============================================================

def construir_perfil_perdidas_v1415(
    resultados,
    tramos=None,
    transiciones=None,
    hA=0.0,
    hR=0.0,
    posicion_bomba=None,
    posicion_turbina=None,
):
    """Construye un perfil acumulado reproducible de pérdidas.

    La fricción se distribuye linealmente a lo largo de cada tramo. Las pérdidas
    por accesorios y transiciones se aplican como saltos concentrados en su
    posición. Bomba/turbina se registran como eventos mecánicos, pero no se
    contabilizan como pérdidas hidráulicas.
    """
    if not resultados:
        raise ValueError("No hay resultados para construir el perfil de pérdidas.")

    total_L = sum(float(f.get("L (m)", 0.0) or 0.0) for f in resultados)
    gradientes = _gradientes_friccion(resultados)
    eventos = []

    if tramos is not None:
        for e in _eventos_perdidas_menores(tramos, resultados):
            eventos.append({**e, "perdida": max(0.0, -float(e.get("delta", 0.0) or 0.0)), "grupo": "accesorios"})
    else:
        x0 = 0.0
        for i, fila in enumerate(resultados, start=1):
            x0 += float(fila.get("L (m)", 0.0) or 0.0)
            hm = float(fila.get("hm (m)", 0.0) or 0.0)
            if hm > 0:
                eventos.append({"x": x0, "perdida": hm, "grupo": "accesorios", "tipo": "menor", "etiqueta": f"Pérdida menor tramo {i}"})

    if transiciones:
        xs_nodos = [0.0]
        acum = 0.0
        for fila in resultados:
            acum += float(fila.get("L (m)", 0.0) or 0.0)
            xs_nodos.append(acum)
        for item in transiciones:
            try:
                entre = int(item.get("entre", 0) or 0)
            except (TypeError, ValueError):
                entre = 0
            if 1 <= entre < len(xs_nodos):
                hlt = float(item.get("hL", 0.0) or 0.0)
                if hlt > 0:
                    eventos.append({
                        "x": float(xs_nodos[entre]), "perdida": hlt,
                        "grupo": "transiciones", "tipo": "transicion",
                        "etiqueta": str(item.get("tipo") or "Transición"),
                    })

    if (hA or 0.0) > 0:
        xb = total_L * 0.05 if posicion_bomba is None else min(max(float(posicion_bomba), 0.0), total_L)
        eventos.append({"x": xb, "perdida": 0.0, "grupo": "maquina", "tipo": "bomba", "etiqueta": f"Bomba (+{float(hA):.4g} m)"})
    if (hR or 0.0) > 0:
        xt = total_L * 0.75 if posicion_turbina is None else min(max(float(posicion_turbina), 0.0), total_L)
        eventos.append({"x": xt, "perdida": 0.0, "grupo": "maquina", "tipo": "turbina", "etiqueta": f"Turbina (-{float(hR):.4g} m)"})

    nodos = {0.0, total_L}
    acum = 0.0
    for fila in resultados:
        acum += float(fila.get("L (m)", 0.0) or 0.0)
        nodos.add(acum)
    nodos.update(float(e["x"]) for e in eventos)
    xs = sorted(nodos)

    eventos_por_x = {}
    for e in eventos:
        eventos_por_x.setdefault(round(float(e["x"]), 12), []).append(e)

    puntos = [{"x_m": 0.0, "hf_acum_m": 0.0, "hm_accesorios_acum_m": 0.0, "hm_transiciones_acum_m": 0.0, "hL_acum_m": 0.0}]
    hf_ac = hm_acc = hm_trans = 0.0
    x_prev = 0.0

    for x in xs[1:]:
        hf_ac += _perdida_friccion_entre(x_prev, x, gradientes)
        puntos.append({"x_m": float(x), "hf_acum_m": hf_ac, "hm_accesorios_acum_m": hm_acc, "hm_transiciones_acum_m": hm_trans, "hL_acum_m": hf_ac + hm_acc + hm_trans})
        for e in eventos_por_x.get(round(float(x), 12), []):
            if e.get("grupo") == "accesorios":
                hm_acc += float(e.get("perdida", 0.0) or 0.0)
            elif e.get("grupo") == "transiciones":
                hm_trans += float(e.get("perdida", 0.0) or 0.0)
            else:
                continue
            puntos.append({"x_m": float(x), "hf_acum_m": hf_ac, "hm_accesorios_acum_m": hm_acc, "hm_transiciones_acum_m": hm_trans, "hL_acum_m": hf_ac + hm_acc + hm_trans})
        x_prev = x

    return {
        "version": VERSION_DIAGRAMAS_AVANZADOS,
        "longitud_total_m": float(total_L),
        "puntos": puntos,
        "eventos": sorted(eventos, key=lambda e: (float(e.get("x", 0.0)), str(e.get("tipo", "")))),
        "total_hf_m": float(hf_ac),
        "total_hm_accesorios_m": float(hm_acc),
        "total_hm_transiciones_m": float(hm_trans),
        "hL_total_m": float(hf_ac + hm_acc + hm_trans),
    }


def crear_perdidas_acumuladas_v1415(
    resultados,
    tramos=None,
    transiciones=None,
    hA=0.0,
    hR=0.0,
    posicion_bomba=None,
    posicion_turbina=None,
    mostrar_etiquetas_eventos=True,
    titulo="Distribución acumulada de pérdidas",
):
    """Grafica pérdidas distribuidas, menores, transiciones y total acumulado."""
    perfil = construir_perfil_perdidas_v1415(
        resultados=resultados, tramos=tramos, transiciones=transiciones,
        hA=hA, hR=hR, posicion_bomba=posicion_bomba, posicion_turbina=posicion_turbina,
    )
    pts = perfil["puntos"]
    x = [p["x_m"] for p in pts]
    hf = [p["hf_acum_m"] for p in pts]
    hm = [p["hm_accesorios_acum_m"] for p in pts]
    ht = [p["hm_transiciones_acum_m"] for p in pts]
    total = [p["hL_acum_m"] for p in pts]

    fig, ax = plt.subplots(figsize=(11.5, 5.8))
    ax.plot(x, hf, label="Σ hf distribuida")
    ax.plot(x, hm, label="Σ hm accesorios")
    ax.plot(x, ht, label="Σ hm transiciones")
    ax.plot(x, total, linewidth=2.0, label="hL acumulada total")

    for e in perfil["eventos"]:
        xe = float(e.get("x", 0.0))
        ax.axvline(xe, linestyle="--", linewidth=0.55, alpha=0.28)

    if mostrar_etiquetas_eventos:
        _anotar_eventos_sin_solapamiento_en_grafica(
            ax=ax,
            eventos=perfil["eventos"],
            xs_ref=x,
            ys_ref=total,
            total_L=perfil["longitud_total_m"],
        )

    ax.set_xlabel("Distancia acumulada a lo largo de la tubería (m)")
    ax.set_ylabel("Pérdida acumulada (m de fluido)")
    ax.set_title(titulo)
    ax.grid(True, alpha=0.25)
    ax.legend()
    ax.text(
        0.01, 0.02,
        f"hf={perfil['total_hf_m']:.6g} m · hm accesorios={perfil['total_hm_accesorios_m']:.6g} m · "
        f"hm transiciones={perfil['total_hm_transiciones_m']:.6g} m · hL={perfil['hL_total_m']:.6g} m",
        transform=ax.transAxes, fontsize=8, va="bottom",
    )
    fig.tight_layout()
    return fig
