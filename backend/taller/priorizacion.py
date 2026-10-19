"""
Módulo de priorización (CU-08 / HU-13), aislado del resto del backend (RNF-14).

Desde octubre de 2026 la prioridad la decide un motor externo hecho en n8n
con un modelo de IA (informe, sección 7.3 y decisión DT-08). Este módulo es
la parte del backend que conversa con ese motor:

1. `solicitar_repriorizacion()`: cuando cambia algo que afecta la prioridad
   (alta o edición de una orden, cambio de estado, cambio de stock), avisa a
   n8n por webhook. Si n8n no está configurado (N8N_WEBHOOK_URL vacío, por
   ejemplo en desarrollo o en los tests), aplica directamente la regla de
   respaldo, así el sistema funciona igual sin el motor.

2. `datos_para_motor()`: arma el resumen de órdenes activas que se le manda
   a la IA. No incluye nombres ni teléfonos de clientes (minimización de
   datos personales, informe sección 16).

3. `guardar_resultados()`: recibe lo que devolvió n8n, lo valida y lo
   guarda. Si faltan órdenes en la respuesta, a esas les aplica la regla de
   respaldo, para que ninguna quede sin prioridad.

4. `puntaje_respaldo()`: regla fija y explicable que se usa cuando la IA no
   responde o responde algo inválido.

La versión anterior (red bayesiana con pgmpy) está en
docs/antecedentes/priorizacion_bayesiana_v1.py.

No se importa nada de modelos a nivel de módulo (imports dentro de las
funciones): evita ciclos con signals.py y mantiene el módulo testeable.
"""
import json
import logging
import threading
import urllib.request

from django.conf import settings
from django.utils import timezone

log = logging.getLogger(__name__)

ORIGEN_IA = 'ia'
ORIGEN_RESPALDO = 'respaldo'

# Reglas del taller que recibe el modelo de IA. Salen del relevamiento
# (Anexo A del informe). Se mandan desde acá para que vivan versionadas con
# el código; n8n solo las reenvía al modelo.
REGLAS_TALLER = [
    'La criticidad que indica el jefe de taller (1 = puede esperar, 5 = muy urgente) pesa más que cualquier otro criterio.',
    'No conviene empezar una orden a la que le falta un repuesto si hay otra que se puede terminar.',
    'Ante criticidad parecida, primero los trabajos rápidos: el taller prefiere sacarse de encima lo rápido.',
    'Ninguna orden puede quedar relegada indefinidamente: cuantos más días lleva en el taller, más sube.',
    'El costo del trabajo sirve para desempatar, pero no debe dominar la decisión.',
    'Una orden sin tiempo estimado se trata como trabajo de duración desconocida: no se la considera rápida.',
]

ESTADOS_ACTIVOS = ('pendiente', 'en_curso')


# ---------------------------------------------------------------------------
# Datos de cada orden
# ---------------------------------------------------------------------------

def dias_en_taller(orden, ahora=None) -> int:
    ahora = ahora or timezone.now()
    return max(0, (ahora - orden.fecha_ingreso).days)


def faltan_repuestos(orden) -> bool:
    """True si algún repuesto de catálogo usado en la orden dejó el stock en
    negativo (se registró más de lo que había: hay que pedirlo)."""
    for item in orden.repuestos_usados.all():
        if item.repuesto is not None and item.repuesto.cantidad_actual < 0:
            return True
    return False


def repuestos_por_encargo(orden) -> int:
    """Cantidad de repuestos fuera de catálogo (hay que encargarlos)."""
    return sum(1 for item in orden.repuestos_usados.all() if item.repuesto is None)


def resumen_orden(orden, ahora=None) -> dict:
    """Lo que ve la IA de una orden. Sin datos personales del cliente."""
    return {
        'orden_id': orden.id,
        'tipo_equipo': orden.equipo.tipo_equipo if orden.equipo else 'sin especificar',
        'estado': orden.estado,
        'criticidad': orden.criticidad,
        'dias_en_taller': dias_en_taller(orden, ahora),
        'tiempo_estimado_horas': orden.tiempo_estimado,
        'costo_estimado': orden.costo_estimado,
        'faltan_repuestos': faltan_repuestos(orden),
        'repuestos_por_encargo': repuestos_por_encargo(orden),
    }


def ordenes_activas():
    from .models import OrdenTrabajo
    return (
        OrdenTrabajo.objects.filter(estado__in=ESTADOS_ACTIVOS)
        .select_related('equipo')
        .prefetch_related('repuestos_usados__repuesto')
        .order_by('id')
    )


def datos_para_motor() -> dict:
    ahora = timezone.now()
    return {
        'generado': ahora.isoformat(),
        'reglas': REGLAS_TALLER,
        'ordenes': [resumen_orden(o, ahora) for o in ordenes_activas()],
    }


# ---------------------------------------------------------------------------
# Regla de respaldo
# ---------------------------------------------------------------------------

def puntaje_respaldo(orden, ahora=None) -> tuple[float, str]:
    """
    Puntaje de 0 a 100 con una regla fija:
      criticidad x 12          (12 a 60 puntos)
    + 15 si no le faltan repuestos
    + 2 por día en el taller   (máximo 15)
    + 10 si el tiempo estimado es de 2 horas o menos
    Devuelve (puntaje, justificación en texto).
    """
    partes = []
    puntos = orden.criticidad * 12
    partes.append(f'criticidad {orden.criticidad} ({puntos} pts)')

    if faltan_repuestos(orden):
        partes.append('le faltan repuestos (0 pts)')
    else:
        puntos += 15
        partes.append('repuestos disponibles (+15)')

    dias = dias_en_taller(orden, ahora)
    extra = min(dias * 2, 15)
    if extra:
        puntos += extra
        partes.append(f'{dias} días en el taller (+{extra})')

    if orden.tiempo_estimado is not None and orden.tiempo_estimado <= 2:
        puntos += 10
        partes.append('trabajo rápido (+10)')

    return float(min(puntos, 100)), 'Regla fija: ' + ', '.join(partes) + '.'


# ---------------------------------------------------------------------------
# Guardado
# ---------------------------------------------------------------------------

def _guardar(orden_id, puntaje, justificacion, origen, ahora):
    from .models import OrdenTrabajo
    # .update() en vez de .save(): no dispara las señales, así guardar la
    # prioridad no provoca otra repriorización (evita un bucle).
    OrdenTrabajo.objects.filter(pk=orden_id).update(
        indice_prioridad=puntaje,
        justificacion_prioridad=justificacion[:500],
        prioridad_origen=origen,
        prioridad_actualizada=ahora,
    )


def limpiar_inactivas():
    """Bloqueadas y terminadas no compiten en el orden (CU-08, regla de
    negocio): se les borra el puntaje y se deja el motivo como explicación."""
    from django.db.models import Q
    from .models import OrdenTrabajo
    ahora = timezone.now()
    inactivas = OrdenTrabajo.objects.exclude(estado__in=ESTADOS_ACTIVOS).filter(
        Q(estado='bloqueado') | Q(indice_prioridad__isnull=False) | ~Q(prioridad_origen='')
    )
    for o in inactivas:
        texto = f'Bloqueada: {o.motivo_bloqueo}' if o.estado == 'bloqueado' else ''
        OrdenTrabajo.objects.filter(pk=o.pk).update(
            indice_prioridad=None, justificacion_prioridad=texto, prioridad_origen='', prioridad_actualizada=ahora,
        )


def aplicar_respaldo(ordenes=None) -> int:
    ahora = timezone.now()
    ordenes = list(ordenes if ordenes is not None else ordenes_activas())
    for o in ordenes:
        puntaje, texto = puntaje_respaldo(o, ahora)
        _guardar(o.id, puntaje, texto, ORIGEN_RESPALDO, ahora)
    limpiar_inactivas()
    return len(ordenes)


class ResultadoInvalido(ValueError):
    pass


def guardar_resultados(resultados) -> dict:
    """
    Recibe la lista que devolvió la IA: [{orden_id, puntaje, justificacion}].
    Valida cada elemento; los que no son válidos o faltan se completan con la
    regla de respaldo. Devuelve un resumen de lo que pasó.
    """
    if not isinstance(resultados, list):
        raise ResultadoInvalido('"resultados" tiene que ser una lista.')

    activas = {o.id: o for o in ordenes_activas()}
    ahora = timezone.now()
    guardadas_ia, ignoradas = set(), []

    for r in resultados:
        try:
            oid = int(r['orden_id'])
            puntaje = float(r['puntaje'])
            texto = str(r.get('justificacion', '')).strip()
        except (KeyError, TypeError, ValueError):
            ignoradas.append(r)
            continue
        if oid not in activas or oid in guardadas_ia or not 0 <= puntaje <= 100 or not texto:
            ignoradas.append(r)
            continue
        _guardar(oid, puntaje, texto, ORIGEN_IA, ahora)
        guardadas_ia.add(oid)

    faltantes = [o for oid, o in activas.items() if oid not in guardadas_ia]
    aplicar_respaldo(faltantes)
    return {
        'guardadas_ia': len(guardadas_ia),
        'completadas_con_respaldo': len(faltantes),
        'ignoradas': len(ignoradas),
    }


# ---------------------------------------------------------------------------
# Disparo hacia n8n
# ---------------------------------------------------------------------------

def _post_webhook(url: str, secreto: str, cuerpo: dict):
    req = urllib.request.Request(
        url, data=json.dumps(cuerpo).encode(), method='POST',
        headers={'Content-Type': 'application/json', 'X-Vortic-Secreto': secreto},
    )
    try:
        urllib.request.urlopen(req, timeout=5).close()
    except Exception as e:
        # n8n caído o lento: el listado ya tiene los puntajes de la regla de
        # respaldo (se aplicaron antes de llamar), así que solo se registra.
        log.warning('No se pudo avisar a n8n (%s); queda la regla de respaldo.', e)


def solicitar_repriorizacion(motivo: str = '') -> None:
    """
    Pide recalcular las prioridades de todas las órdenes activas.
    - Con N8N_WEBHOOK_URL configurado: aplica la regla de respaldo en el
      momento (para que el listado nunca quede desactualizado) y avisa a n8n
      en segundo plano; cuando la IA responde, sus puntajes reemplazan a los
      de la regla.
    - Sin n8n configurado: solo aplica la regla de respaldo.
    """
    aplicar_respaldo()
    url = getattr(settings, 'N8N_WEBHOOK_URL', '')
    if not url:
        return
    cuerpo = {'motivo': motivo, 'momento': timezone.now().isoformat()}
    threading.Thread(
        target=_post_webhook, args=(url, settings.N8N_WEBHOOK_SECRETO, cuerpo), daemon=True,
    ).start()
