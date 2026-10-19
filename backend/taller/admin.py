from django.contrib import admin
from .models import (
    Equipo, Repuesto, OrdenTrabajo, OrdenRepuesto, SesionHoras, HistorialEstado,
    Proveedor, PrecioProveedor,
)


@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = ('tipo_equipo', 'marca_modelo', 'cliente')


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo')


class PrecioProveedorInline(admin.TabularInline):
    model = PrecioProveedor
    extra = 0


@admin.register(Repuesto)
class RepuestoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'descripcion', 'cantidad_actual', 'cantidad_minima', 'stock_bajo')
    search_fields = ('codigo', 'descripcion')
    inlines = [PrecioProveedorInline]


class OrdenRepuestoInline(admin.TabularInline):
    model = OrdenRepuesto
    extra = 0


class SesionHorasInline(admin.TabularInline):
    model = SesionHoras
    extra = 0


class HistorialEstadoInline(admin.TabularInline):
    model = HistorialEstado
    extra = 0
    readonly_fields = ('estado_anterior', 'estado_nuevo', 'fecha_cambio', 'usuario')


@admin.register(OrdenTrabajo)
class OrdenTrabajoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'estado', 'criticidad', 'indice_prioridad', 'fecha_ingreso')
    list_filter = ('estado',)
    inlines = [OrdenRepuestoInline, SesionHorasInline, HistorialEstadoInline]
