from django.db import transaction
from rest_framework import serializers
from clientes.serializers import ClienteSerializer
from .models import (
    Equipo, Repuesto, OrdenTrabajo, OrdenRepuesto, SesionHoras, HistorialEstado,
    Proveedor, PrecioProveedor,
)
from .pricing import calcular_precio_venta, mejor_precio_proveedor


class EquipoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Equipo
        fields = ['id', 'cliente', 'tipo_equipo', 'marca_modelo']


class ProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proveedor
        fields = ['id', 'nombre', 'activo', 'mapeo_columnas']
        read_only_fields = ['mapeo_columnas']


class PrecioProveedorSerializer(serializers.ModelSerializer):
    proveedor_nombre = serializers.CharField(source='proveedor.nombre', read_only=True)

    class Meta:
        model = PrecioProveedor
        fields = ['id', 'repuesto', 'proveedor', 'proveedor_nombre', 'precio_costo', 'fecha_actualizacion']
        read_only_fields = ['fecha_actualizacion']


class RepuestoSerializer(serializers.ModelSerializer):
    """
    `precio_costo_sugerido` / `proveedor_sugerido_nombre` / `precio_venta_sugerido`
    son solo una REFERENCIA (el precio más bajo entre los proveedores
    cargados, +40%) para mostrar en el catálogo de Stock — NO determinan
    de qué proveedor se compra en una orden puntual. Esa elección la hace
    el jefe de taller al registrar el repuesto usado (ver OrdenRepuestoSerializer
    y el buscador en el frontend), y queda guardada en OrdenRepuesto.
    """
    stock_bajo = serializers.BooleanField(read_only=True)
    precios_proveedor = PrecioProveedorSerializer(many=True, read_only=True)
    precio_costo_sugerido = serializers.SerializerMethodField()
    proveedor_sugerido_nombre = serializers.SerializerMethodField()
    precio_venta_sugerido = serializers.SerializerMethodField()

    class Meta:
        model = Repuesto
        fields = [
            'id', 'codigo', 'descripcion', 'cantidad_actual', 'cantidad_minima', 'stock_bajo',
            'precios_proveedor', 'precio_costo_sugerido', 'proveedor_sugerido_nombre', 'precio_venta_sugerido',
        ]

    def get_precio_costo_sugerido(self, obj):
        mejor = mejor_precio_proveedor(obj)
        return mejor.precio_costo if mejor else None

    def get_proveedor_sugerido_nombre(self, obj):
        mejor = mejor_precio_proveedor(obj)
        return mejor.proveedor.nombre if mejor else None

    def get_precio_venta_sugerido(self, obj):
        mejor = mejor_precio_proveedor(obj)
        return calcular_precio_venta(mejor.precio_costo) if mejor else None


class OrdenRepuestoSerializer(serializers.ModelSerializer):
    repuesto_detalle = RepuestoSerializer(source='repuesto', read_only=True)
    proveedor_nombre = serializers.CharField(source='proveedor.nombre', read_only=True, default=None)
    precio_venta = serializers.SerializerMethodField()

    class Meta:
        model = OrdenRepuesto
        fields = [
            'id', 'orden', 'repuesto', 'repuesto_detalle', 'descripcion_encargo', 'cantidad',
            'proveedor', 'proveedor_nombre', 'precio_costo', 'precio_venta',
        ]

    def get_precio_venta(self, obj):
        return calcular_precio_venta(obj.precio_costo) if obj.precio_costo is not None else None


class SesionHorasSerializer(serializers.ModelSerializer):
    usuario_username = serializers.CharField(source='usuario.username', read_only=True)

    class Meta:
        model = SesionHoras
        fields = ['id', 'orden', 'horas', 'fecha_registro', 'usuario', 'usuario_username']
        read_only_fields = ['fecha_registro', 'usuario']


class HistorialEstadoSerializer(serializers.ModelSerializer):
    usuario_username = serializers.CharField(source='usuario.username', read_only=True)

    class Meta:
        model = HistorialEstado
        fields = ['id', 'estado_anterior', 'estado_nuevo', 'fecha_cambio', 'usuario', 'usuario_username']


class OrdenTrabajoListSerializer(serializers.ModelSerializer):
    """Listado (HU-05/HU-06/HU-13): liviano, para la vista principal."""
    cliente_nombre = serializers.CharField(source='cliente.razon_social', read_only=True)
    tipo_equipo = serializers.CharField(source='equipo.tipo_equipo', read_only=True, default=None)

    class Meta:
        model = OrdenTrabajo
        fields = [
            'id', 'cliente', 'cliente_nombre', 'equipo', 'tipo_equipo',
            'estado', 'motivo_bloqueo', 'fecha_ingreso', 'criticidad', 'indice_prioridad',
            'justificacion_prioridad', 'prioridad_origen', 'prioridad_actualizada',
        ]


class OrdenTrabajoDetailSerializer(serializers.ModelSerializer):
    """Detalle de una orden (HU-01, HU-07, HU-08): incluye subrecursos."""
    cliente_detalle = ClienteSerializer(source='cliente', read_only=True)
    equipo_detalle = EquipoSerializer(source='equipo', read_only=True)
    repuestos_usados = OrdenRepuestoSerializer(many=True, read_only=True)
    sesiones_horas = SesionHorasSerializer(many=True, read_only=True)
    historial = HistorialEstadoSerializer(many=True, read_only=True)
    total_horas = serializers.SerializerMethodField()
    # CU-01: alta de equipo nuevo en el mismo paso que la orden (HU-01). Antes
    # el frontend hacía dos POST separados (equipo, después orden); si el
    # segundo fallaba, el equipo quedaba creado y huérfano, sin ninguna
    # orden apuntándolo, y reintentar creaba otro más. Con estos dos campos
    # write-only, ambas filas se crean en una sola transacción atómica acá.
    nuevo_tipo_equipo = serializers.CharField(write_only=True, required=False, allow_blank=True)
    nuevo_marca_modelo = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = OrdenTrabajo
        fields = [
            'id', 'cliente', 'cliente_detalle', 'equipo', 'equipo_detalle', 'descripcion_falla',
            'estado', 'motivo_bloqueo', 'fecha_ingreso', 'costo_estimado',
            'tiempo_estimado', 'criticidad', 'indice_prioridad', 'justificacion_prioridad',
            'prioridad_origen', 'prioridad_actualizada', 'fecha_aviso_cliente',
            'repuestos_usados', 'sesiones_horas', 'historial', 'total_horas',
            'nuevo_tipo_equipo', 'nuevo_marca_modelo',
        ]
        # `estado` y `motivo_bloqueo` son de solo lectura ACÁ a propósito:
        # cambiarlos por un PATCH genérico a este endpoint se saltaba
        # cambiar_estado() (taller/views.py) — no quedaba registro en
        # HistorialEstado (rompe la trazabilidad de CU-02) y, al salir de
        # Bloqueado por esta vía, motivo_bloqueo se quedaba con el texto
        # viejo (el fix de esa staleness vive en cambiar_estado, no acá).
        # El único camino para cambiar el estado de una orden es la action.
        read_only_fields = [
            'indice_prioridad', 'fecha_ingreso', 'fecha_aviso_cliente', 'estado', 'motivo_bloqueo',
        ]

    def get_total_horas(self, obj):
        return sum(s.horas for s in obj.sesiones_horas.all())

    def create(self, validated_data):
        nuevo_tipo = validated_data.pop('nuevo_tipo_equipo', None)
        nuevo_marca = validated_data.pop('nuevo_marca_modelo', None)
        with transaction.atomic():
            if nuevo_tipo and not validated_data.get('equipo'):
                validated_data['equipo'] = Equipo.objects.create(
                    cliente=validated_data['cliente'], tipo_equipo=nuevo_tipo, marca_modelo=nuevo_marca or None,
                )
            return super().create(validated_data)
