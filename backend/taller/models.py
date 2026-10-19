from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from clientes.models import Cliente


class Equipo(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='equipos')
    tipo_equipo = models.CharField(max_length=100)  # cilindro, bomba, motor, manguera, válvula...
    marca_modelo = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f'{self.tipo_equipo} ({self.cliente})'


class Proveedor(models.Model):
    nombre = models.CharField(max_length=200, unique=True)
    activo = models.BooleanField(default=True)
    # Cada proveedor manda su lista de precios con sus propias columnas
    # (no hay un formato estándar entre proveedores). La primera vez que
    # se importa una planilla, el usuario confirma qué columna es cuál
    # (ver previsualizar_planilla/importar_precios en views.py); ese
    # mapeo se guarda acá para pre-completarlo en la próxima importación
    # de este mismo proveedor. Formato: {"codigo": "...", "descripcion":
    # "..."|null, "precio": "..."} con los nombres de columna tal como
    # vienen en la planilla.
    mapeo_columnas = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Repuesto(models.Model):
    codigo = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=200)
    cantidad_actual = models.IntegerField(default=0)
    cantidad_minima = models.IntegerField(default=0)  # umbral de alerta (HU-11)
    # Un mismo repuesto puede tener precio de costo distinto según el
    # proveedor (tabla PrecioProveedor, más abajo). El precio de costo
    # "del repuesto" y el precio de venta con margen se resuelven en
    # taller/pricing.py, no acá — mismo criterio de aislamiento que
    # priorizacion.py.

    @property
    def stock_bajo(self):
        return self.cantidad_actual < self.cantidad_minima

    def __str__(self):
        return f'{self.codigo} — {self.descripcion}'


class PrecioProveedor(models.Model):
    """Precio de costo de un repuesto según un proveedor puntual."""
    repuesto = models.ForeignKey(Repuesto, on_delete=models.CASCADE, related_name='precios_proveedor')
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name='precios')
    precio_costo = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('repuesto', 'proveedor')
        ordering = ['precio_costo']

    def __str__(self):
        return f'{self.repuesto.codigo} @ {self.proveedor.nombre}: ${self.precio_costo}'


class OrdenTrabajo(models.Model):
    PENDIENTE = 'pendiente'
    EN_CURSO = 'en_curso'
    BLOQUEADO = 'bloqueado'
    TERMINADO = 'terminado'
    ESTADOS = [
        (PENDIENTE, 'Pendiente'),
        (EN_CURSO, 'En curso'),
        (BLOQUEADO, 'Bloqueado'),
        (TERMINADO, 'Terminado'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='ordenes')
    equipo = models.ForeignKey(Equipo, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes')
    descripcion_falla = models.TextField()
    estado = models.CharField(max_length=20, choices=ESTADOS, default=PENDIENTE)
    # Criticidad DEL TRABAJO, no del cliente: el mismo cliente puede traer
    # una orden urgente y otra que puede esperar. Escala 1 (puede esperar)
    # a 5 (muy urgente), validada para que no entren valores fuera de rango.
    criticidad = models.PositiveSmallIntegerField(
        default=2, validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    motivo_bloqueo = models.TextField(blank=True, null=True)  # obligatorio si estado=bloqueado (HU-04)
    fecha_ingreso = models.DateTimeField(auto_now_add=True)
    # No puede ser negativo (un error de tipeo se rechaza en vez de guardarse).
    costo_estimado = models.FloatField(
        blank=True, null=True, validators=[MinValueValidator(0)],
        help_text='Dispara recálculo de prioridad al cargarse',
    )
    # Mínimo 0,1 h (6 minutos): un 0 por error de tipeo se rechaza.
    tiempo_estimado = models.FloatField(
        blank=True, null=True, validators=[MinValueValidator(0.1)],
        help_text='Horas estimadas por el jefe; mínimo 0,1 h',
    )
    # Prioridad sugerida (CU-08): puntaje de 0 a 100 que calcula el motor de
    # n8n con IA, o la regla de respaldo si la IA no respondió. Ninguno de
    # estos campos se edita desde la interfaz (ver taller/priorizacion.py).
    indice_prioridad = models.FloatField(blank=True, null=True, editable=False)
    justificacion_prioridad = models.TextField(blank=True, default='', editable=False)
    prioridad_origen = models.CharField(
        max_length=10, blank=True, default='', editable=False,
        choices=[('ia', 'IA'), ('respaldo', 'Regla de respaldo')],
    )
    prioridad_actualizada = models.DateTimeField(blank=True, null=True, editable=False)
    fecha_aviso_cliente = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-fecha_ingreso']

    def __str__(self):
        return f'OT-{self.id:04d} — {self.cliente}'


class OrdenRepuesto(models.Model):
    orden = models.ForeignKey(OrdenTrabajo, on_delete=models.CASCADE, related_name='repuestos_usados')
    repuesto = models.ForeignKey(Repuesto, on_delete=models.PROTECT, blank=True, null=True)
    descripcion_encargo = models.CharField(
        max_length=200, blank=True, null=True,
        help_text='Si el repuesto no está en catálogo (repuesto por encargo, HU-07)',
    )
    cantidad = models.PositiveIntegerField()
    # Proveedor elegido para ESTA compra puntual — el jefe de taller lo
    # busca entre todas las listas cargadas y elige, no se asume el más
    # barato automáticamente (el "mejor precio" en Repuesto/pricing.py es
    # solo una referencia orientativa, no una decisión de compra).
    # precio_costo queda como foto histórica: si la lista de precios del
    # proveedor cambia después, esta orden conserva el precio real pagado.
    proveedor = models.ForeignKey(
        Proveedor, on_delete=models.SET_NULL, blank=True, null=True, related_name='compras',
    )
    precio_costo = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)


class SesionHoras(models.Model):
    orden = models.ForeignKey(OrdenTrabajo, on_delete=models.CASCADE, related_name='sesiones_horas')
    horas = models.FloatField()
    fecha_registro = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class HistorialEstado(models.Model):
    orden = models.ForeignKey(OrdenTrabajo, on_delete=models.CASCADE, related_name='historial')
    estado_anterior = models.CharField(max_length=20)
    estado_nuevo = models.CharField(max_length=20)
    fecha_cambio = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        ordering = ['-fecha_cambio']
