"""
Módulo de priorización — aislado del resto de la lógica de Django (RNF-14).

Implementa la red bayesiana de la sección 7 del informe con pgmpy, en
vez de la fórmula determinística que era el punto de partida del MVP.
Mismo contrato que antes — `calc_indice_prioridad(orden)` y
`recalcular_y_guardar(orden)` no cambiaron de firma — así que signals.py
y views.py no necesitaron tocarse para este cambio (ese era justamente
el objetivo del aislamiento).

Estructura de la red (7.1/7.2 — topología convergente):

    TipoTrabajo ─┐
                 ├──▶ ProbBloqueo ─┐
    Stock ───┬───┘                 │
              └──▶ TiempoLogistico ─┼──▶ TiempoResolucion
    EstimacionManual ────────────────┘

`TiempoResolucion` existe en la red para reflejar fielmente la
factorización de 7.2 (P(T_Res | P_Bloqueo, T_Log, T_Manual) × ...), pero
el cálculo numérico del índice sigue la fórmula explícita de 7.3
(Índice = Costo × Criticidad / T_estimado, con T_estimado mezclando
T_normal y T_bloqueado según P_bloqueo) — lo único que cambió es que
P_bloqueo ya no es una multiplicación en línea, sino el resultado de una
consulta de inferencia (VariableElimination) sobre la CPD de
`ProbBloqueo`, cuya tabla se recalcula en cada corrida combinando el
prior de la Tabla 17/18 con lo aprendido del historial real (sección
7.5) vía `EstadisticaTipoStock`.

No importar nada de `django.db` a nivel de módulo (los imports de
modelos van dentro de las funciones) — mantiene el módulo testeable de
forma aislada, según pide RNF-14: se le puede pasar cualquier objeto
"orden" con los atributos correctos, sin una base de datos real.

--------------------------------------------------------------------
Cambios de esta revisión (ver REVISION_PRIORIZACION.md):

1. CONSIDERAR_STOCK=False desactiva la variable Stock de la red
   mientras el equipo no trabaja con el módulo de stock/proveedores
   (ver FEATURE_STOCK_PROVEEDORES en config/settings.py — ese flag
   apaga las rutas/UI; este flag, acá adentro, apaga el uso de Stock
   en el cálculo para que no dependa de datos que ya no se cargan).
   Con la variable apagada, `_prob_bloqueo_marginal()` consulta la red
   SIN condicionar por Stock: pgmpy marginaliza usando el prior de la
   Tabla 18 (0,65/0,35) en vez de leer hay_stock_disponible(orden), que
   daba falsos "con stock" en órdenes sin repuestos cargados (hallazgo
   #3). No hace falta tocar la topología de la red para esto — es
   una consulta de inferencia distinta sobre la misma red de 7.2.

2. `calc_indice_prioridad` comprime el costo con logaritmo (hallazgo
   #1): la fórmula 7.3 tal cual (Costo × Criticidad / T_estimado) queda
   dominada casi enteramente por el costo, porque su rango dinámico
   ($1.000–$150.000+) es mucho mayor que el de criticidad (1-3) y
   tiempo (unas pocas horas) — un trabajo rápido y barato nunca le
   gana a uno caro y lento. `log1p(costo)` conserva el orden (más caro
   sigue significando más prioridad) pero comprime la escala para que
   criticidad y tiempo vuelvan a pesar en el resultado.
--------------------------------------------------------------------
"""
import math

from pgmpy.inference import VariableElimination
from pgmpy.factors.discrete import TabularCPD
from pgmpy.models import DiscreteBayesianNetwork

# Ver punto 1 arriba. Volver a True reactiva la variable Stock (requiere
# reactivar también FEATURE_STOCK_PROVEEDORES en settings, si no
# hay_stock_disponible() va a seguir viendo órdenes sin repuestos
# cargados y dando falsos "con stock").
CONSIDERAR_STOCK = False

# P_base(tipo) — Tabla 17 del informe. Se usa tal cual con dos roles
# (igual que en el informe): como prior de frecuencia del tipo de
# trabajo Y como tasa base de bloqueo en la CPD de ProbBloqueo.
P_BASE_TIPO_TRABAJO = {
    'manguera': 0.25,
    'cilindro': 0.25,
    'bomba': 0.20,
    'motor': 0.15,
    'valvula': 0.15,
    'válvula': 0.15,
}
P_BASE_DEFAULT = 0.20  # fallback si el tipo de equipo no matchea el catálogo ("otro")
TIPOS_CONOCIDOS = ['manguera', 'cilindro', 'bomba', 'motor', 'valvula']
TIPOS_RED = TIPOS_CONOCIDOS + ['otro']

FACTOR_STOCK_CON_STOCK = 0.3
FACTOR_STOCK_SIN_STOCK = 2.5

ESPERA_LOGISTICA_HORAS = 0.5  # 30 minutos, T_bloqueado = T_normal + esto

# Hallazgo C (revisión de testing práctico): con T_estimado libre en el
# denominador, un trabajo carísimo pero muy rápido (ej. $500.000 en 0,5h,
# criticidad baja) le ganaba a un trabajo genuinamente urgente y largo (ej.
# motor de $150.000 en 10h, criticidad 5) — el mismo problema que el
# hallazgo #1 original (un factor aplastando a los otros dos), esta vez
# con el tiempo en vez del costo. PISO_TIEMPO_HORAS acota cuánto puede
# "ayudar" un tiempo muy chico: a los fines del índice, ningún trabajo se
# trata como si tardara menos de esto (hay un piso real de diagnóstico/
# armado/desarmado en taller aunque la reparación en sí sea rápida).
PISO_TIEMPO_HORAS = 1.0

# Hallazgo #5 (REVISION_PRIORIZACION.md): antes esto colapsaba la escala
# 1-5 del formulario a solo 3 valores efectivos (1 y 2 daban lo mismo, 4
# y 5 también), así que dos de las cinco opciones del <select> de
# OrdenesView.vue no cambiaban nada en la priorización aunque el jefe
# de taller eligiera una u otra. Ahora es 1:1 — las 5 opciones del
# formulario ("puede esperar" ... "muy urgente") tienen 5 pesos
# distintos, consistente con lo que la UI muestra.
CRITICIDAD_A_ESCALA = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}

# Sección 7.5: "con 20 o más órdenes completadas por tipo de trabajo, la
# estimación bayesiana supera en precisión a la estimación manual" — se
# usa ese mismo número como pseudo-conteo del prior en la actualización
# Beta-Binomial: hasta ~20 observaciones reales, el prior de la Tabla 17
# todavía pesa más que el historial; por encima, el historial domina.
PESO_PRIOR = 20


def _normalizar(valor: float, minimo: float = 0.0, maximo: float = 1.0) -> float:
    return max(minimo, min(maximo, valor))


def _normalizar_tipo(tipo_equipo: str | None) -> str:
    """Colapsa el texto libre de tipo_equipo a una de las categorías de
    la Tabla 17, o 'otro' si no matchea ninguna."""
    tipo = (tipo_equipo or '').strip().lower()
    for a, b in (('á', 'a'), ('í', 'i')):
        tipo = tipo.replace(a, b)
    return tipo if tipo in TIPOS_CONOCIDOS else 'otro'


def hay_stock_disponible(orden) -> bool:
    """True si todos los repuestos ya cargados en la orden tienen stock suficiente."""
    for item in orden.repuestos_usados.select_related('repuesto').all():
        if item.repuesto is None:
            continue  # repuesto por encargo: no bloquea por stock de catálogo
        if item.repuesto.cantidad_actual < item.cantidad:
            return False
    return True


def _construir_red(conteos: dict[tuple[str, str], tuple[int, int]]) -> DiscreteBayesianNetwork:
    """
    Arma la red bayesiana completa (7.1/7.2) con las CPDs de las
    Tablas 17/18 como prior, ajustadas por lo aprendido del historial
    (`conteos`: {(tipo, stock_estado): (veces_bloqueado, veces_total)}).

    Para cada combinación (tipo, stock), el prior P_base(tipo) × factor
    se combina con la frecuencia observada mediante una actualización
    Beta-Binomial (conjugada): el prior pesa como PESO_PRIOR
    observaciones "virtuales", así que con pocos datos reales domina el
    prior y con muchos domina lo observado — exactamente el
    comportamiento descrito en la sección 7.5.
    """
    stocks = ['con_stock', 'sin_stock']
    factores = {'con_stock': FACTOR_STOCK_CON_STOCK, 'sin_stock': FACTOR_STOCK_SIN_STOCK}

    valores_si = []
    for tipo in TIPOS_RED:
        p_base = P_BASE_TIPO_TRABAJO.get(tipo, P_BASE_DEFAULT)
        for stock in stocks:  # Stock es la última variable en `evidence` -> varía más rápido (ver nota abajo)
            prior = _normalizar(p_base * factores[stock])
            veces_bloqueado, veces_total = conteos.get((tipo, stock), (0, 0))
            posterior = (prior * PESO_PRIOR + veces_bloqueado) / (PESO_PRIOR + veces_total)
            valores_si.append(_normalizar(posterior))
    valores_no = [1 - v for v in valores_si]

    # Prior marginal del nodo raíz TipoTrabajo (debe sumar 1, a diferencia
    # de P_base(tipo) que son tasas independientes): reparte 95% entre
    # las 5 categorías relevadas según sus proporciones de la Tabla 17 y
    # 5% a "otro" (equipos que no matchean el catálogo relevado).
    proporciones = [P_BASE_TIPO_TRABAJO[t] for t in TIPOS_CONOCIDOS]
    prior_raiz_tipo = [p * 0.95 for p in proporciones] + [0.05]

    red = DiscreteBayesianNetwork([
        ('TipoTrabajo', 'ProbBloqueo'),
        ('Stock', 'ProbBloqueo'),
        ('Stock', 'TiempoLogistico'),
        ('ProbBloqueo', 'TiempoResolucion'),
        ('TiempoLogistico', 'TiempoResolucion'),
        ('EstimacionManual', 'TiempoResolucion'),
    ])

    cpd_tipo = TabularCPD('TipoTrabajo', len(TIPOS_RED), [[p] for p in prior_raiz_tipo],
                           state_names={'TipoTrabajo': TIPOS_RED})
    # Tabla 18: prior de disponibilidad de stock (0,65 / 0,35). Para una
    # orden puntual siempre se conoce el estado real vía
    # hay_stock_disponible(), así que este prior solo importaría si se
    # consultara la red sin evidencia — se deja igual por fidelidad a 7.4.
    cpd_stock = TabularCPD('Stock', 2, [[0.65], [0.35]], state_names={'Stock': stocks})
    # Estimación manual (7.1: variable binaria, simplificación admitida
    # en 7.6): si la orden trae tiempo_estimado cargado o no. El prior
    # 70/30 es una suposición razonable (la mayoría de las órdenes se
    # cargan con una estimación) sin dato relevado específico para esto.
    cpd_manual = TabularCPD('EstimacionManual', 2, [[0.7], [0.3]],
                             state_names={'EstimacionManual': ['con_estimacion', 'sin_estimacion']})
    # Sin stock, el pedido a proveedor genera espera logística con alta
    # probabilidad; con stock, prácticamente no hay espera.
    cpd_log = TabularCPD(
        'TiempoLogistico', 2, [[0.95, 0.15], [0.05, 0.85]],
        evidence=['Stock'], evidence_card=[2],
        state_names={'TiempoLogistico': ['sin_espera', 'espera'], 'Stock': stocks},
    )
    cpd_prob = TabularCPD(
        'ProbBloqueo', 2, [valores_no, valores_si],
        evidence=['TipoTrabajo', 'Stock'], evidence_card=[len(TIPOS_RED), 2],
        state_names={'ProbBloqueo': ['no', 'si'], 'TipoTrabajo': TIPOS_RED, 'Stock': stocks},
    )
    # TiempoResolucion completa la topología de 7.2 (para que la red
    # coincida con el diagrama del informe); no se consulta numéricamente
    # acá — T_estimado/Índice siguen la fórmula explícita de 7.3.
    n_combos = 2 * 2 * 2
    cpd_res = TabularCPD(
        'TiempoResolucion', 2, [[0.5] * n_combos, [0.5] * n_combos],
        evidence=['ProbBloqueo', 'TiempoLogistico', 'EstimacionManual'], evidence_card=[2, 2, 2],
        state_names={
            'TiempoResolucion': ['normal', 'demorado'], 'ProbBloqueo': ['no', 'si'],
            'TiempoLogistico': ['sin_espera', 'espera'],
            'EstimacionManual': ['con_estimacion', 'sin_estimacion'],
        },
    )

    red.add_cpds(cpd_tipo, cpd_stock, cpd_manual, cpd_log, cpd_prob, cpd_res)
    return red


def _leer_conteos_historicos() -> dict[tuple[str, str], tuple[int, int]]:
    from .models import EstadisticaTipoStock  # import local: evita ciclo y mantiene el módulo aislado

    return {
        (e.tipo_equipo, e.stock_estado): (e.veces_bloqueado, e.veces_total)
        for e in EstadisticaTipoStock.objects.all()
    }


def _prob_bloqueo_bayesiana(tipo: str, stock: str) -> float:
    """Consulta P(ProbBloqueo=si | TipoTrabajo=tipo, Stock=stock) en la
    red bayesiana (VariableElimination), ya combinada con el historial."""
    red = _construir_red(_leer_conteos_historicos())
    infer = VariableElimination(red)
    resultado = infer.query(['ProbBloqueo'], evidence={'TipoTrabajo': tipo, 'Stock': stock}, show_progress=False)
    return float(resultado.get_value(ProbBloqueo='si'))


def _prob_bloqueo_marginal(tipo: str) -> float:
    """
    Igual que `_prob_bloqueo_bayesiana`, pero sin condicionar por Stock:
    se usa mientras CONSIDERAR_STOCK=False, porque hay_stock_disponible()
    no es confiable sin el módulo de repuestos activo (ver punto 1 en el
    docstring del módulo). pgmpy marginaliza Stock automáticamente usando
    su propio prior (Tabla 18, 0,65/0,35) al no pasarlo como evidencia —
    es la forma matemáticamente correcta de "no saber" el stock, en vez
    de asumir un valor fijo.
    """
    red = _construir_red(_leer_conteos_historicos())
    infer = VariableElimination(red)
    resultado = infer.query(['ProbBloqueo'], evidence={'TipoTrabajo': tipo}, show_progress=False)
    return float(resultado.get_value(ProbBloqueo='si'))


def calc_indice_prioridad(orden) -> float | None:
    """
    Calcula el índice de prioridad de una OrdenTrabajo (sección 7.3),
    usando la red bayesiana para P_bloqueo en vez de la multiplicación
    directa P_base(tipo) × factor_stock de la versión determinística.

    Índice = (log1p(Costo) × Criticidad) / log1p(máx(T_estimado, PISO_TIEMPO_HORAS))

    El log1p sobre el costo es la corrección del hallazgo #1 (ver
    docstring del módulo): la fórmula original de 7.3 usaba Costo tal
    cual, pero su rango dinámico (miles a cientos de miles de pesos)
    aplastaba a criticidad (1-3) y tiempo (pocas horas), así que un
    trabajo caro le ganaba siempre a uno rápido y barato sin importar
    cuánto más rápido fuera. log1p conserva el orden (más caro = más
    índice) pero comprime la escala para que los otros dos factores
    vuelvan a influir en el resultado.

    Hallazgo C (revisión de testing práctico): corregido el punto
    anterior, el problema reaparecía en el sentido opuesto — con
    T_estimado libre en el denominador, un trabajo carísimo pero muy
    rápido (ej. $500.000 en 0,5h, criticidad baja) le seguía ganando a
    uno genuinamente urgente y largo (ej. $150.000 en 10h, criticidad
    alta), porque el tiempo en el denominador podía volverse arbitrariamente
    chico. Se le aplica el mismo tratamiento que al costo: un piso
    (PISO_TIEMPO_HORAS, ningún trabajo se considera más rápido que eso a
    estos fines) y log1p para comprimir el otro extremo (que un trabajo de
    10h no pese 10 veces más que uno de 1h en el denominador). Verificado
    con los mismos casos que expusieron el problema original.

    Devuelve None si falta costo_estimado o tiempo_estimado — esas
    órdenes se ubican al final del listado (HU-13, criterio 03), el
    ordenamiento se resuelve en el serializer/queryset, no acá.
    """
    if orden.costo_estimado is None or orden.tiempo_estimado is None:
        return None

    tipo = _normalizar_tipo(orden.equipo.tipo_equipo if orden.equipo else None)
    if CONSIDERAR_STOCK:
        stock = 'con_stock' if hay_stock_disponible(orden) else 'sin_stock'
        p_bloqueo = _prob_bloqueo_bayesiana(tipo, stock)
    else:
        p_bloqueo = _prob_bloqueo_marginal(tipo)

    t_normal = orden.tiempo_estimado
    t_bloqueado = t_normal + ESPERA_LOGISTICA_HORAS
    t_estimado = t_normal * (1 - p_bloqueo) + t_bloqueado * p_bloqueo

    if t_estimado <= 0:
        return None

    criticidad = CRITICIDAD_A_ESCALA.get(orden.criticidad, 2)
    costo_efectivo = math.log1p(max(orden.costo_estimado, 0))
    tiempo_efectivo = math.log1p(max(t_estimado, PISO_TIEMPO_HORAS))
    return (costo_efectivo * criticidad) / tiempo_efectivo


def recalcular_y_guardar(orden) -> None:
    """
    Recalcula el índice y lo persiste con `.update()` (evita recursión:
    no dispara post_save de nuevo). También lo pisa en el objeto en
    memoria que se pasó, para que la respuesta del request que originó
    el recálculo (ej. el POST que crea la orden) ya muestre el valor
    correcto en lugar del que tenía antes de guardarse.
    """
    from .models import OrdenTrabajo  # import local, evita ciclo con signals.py

    nuevo_indice = calc_indice_prioridad(orden)
    if orden.indice_prioridad != nuevo_indice:
        OrdenTrabajo.objects.filter(pk=orden.pk).update(indice_prioridad=nuevo_indice)
        orden.indice_prioridad = nuevo_indice


def registrar_resultado_historico(orden) -> None:
    """
    Sección 7.5 — "mecanismo de actualización": se llama cuando una
    orden pasa a Terminado (ver taller/views.py, cambiar_estado). Registra
    si esa orden pasó por Bloqueado alguna vez y cuál era la
    disponibilidad de stock al finalizar, e incrementa el contador de
    EstadisticaTipoStock correspondiente — la próxima consulta a la red
    ya combina esta evidencia con el prior (ver _construir_red).

    Simplificación admitida (consistente con 7.6, que ya reconoce que el
    modelo no captura todo con precisión total): no se guarda un
    snapshot histórico del stock al INICIO del trabajo (no existe esa
    tabla), así que se usa la disponibilidad de stock al momento de
    terminar como aproximación de la condición relevante.

    Mientras CONSIDERAR_STOCK=False no se registra nada acá: sin el
    módulo de repuestos activo, hay_stock_disponible() siempre daría
    "con stock" (orden sin repuestos cargados = ningún ítem por debajo
    del mínimo = True por defecto), y grabar eso como si fuera un dato
    real contaminaría el historial con el mismo sesgo del hallazgo #3
    en vez de corregirlo. Se retoma solo al reactivar el stock.
    """
    if not CONSIDERAR_STOCK:
        return

    from django.db.models import F
    from .models import EstadisticaTipoStock, HistorialEstado, OrdenTrabajo

    # Hallazgo G (revisión de testing práctico): una orden puede reabrirse
    # después de Terminado (ej. el cliente la trae de vuelta) y volver a
    # terminarse — taller/views.py ya llama a esta función una vez por
    # CADA transición a Terminado, así que sin este chequeo la misma orden
    # sumaría dos veces a veces_total/veces_bloqueado, contaminando el
    # aprendizaje bayesiano con una repetición que no es un caso nuevo. El
    # registro de HistorialEstado de ESTA transición ya se creó antes de
    # llamar acá (ver cambiar_estado), así que más de una fila = ya se
    # había contado antes.
    ya_contabilizada = HistorialEstado.objects.filter(
        orden=orden, estado_nuevo=OrdenTrabajo.TERMINADO,
    ).count() > 1
    if ya_contabilizada:
        return

    tipo = _normalizar_tipo(orden.equipo.tipo_equipo if orden.equipo else None)
    stock = 'con_stock' if hay_stock_disponible(orden) else 'sin_stock'
    paso_por_bloqueado = HistorialEstado.objects.filter(
        orden=orden, estado_nuevo=OrdenTrabajo.BLOQUEADO,
    ).exists()

    stat, _ = EstadisticaTipoStock.objects.get_or_create(tipo_equipo=tipo, stock_estado=stock)
    EstadisticaTipoStock.objects.filter(pk=stat.pk).update(
        veces_total=F('veces_total') + 1,
        veces_bloqueado=F('veces_bloqueado') + (1 if paso_por_bloqueado else 0),
    )
