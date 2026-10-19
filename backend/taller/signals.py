"""
Dispara la repriorización (CU-08) cuando cambia algo que la afecta: alta o
edición de una orden (incluye cambios de estado, criticidad, costo y tiempo
estimado) y cambios de stock de un repuesto. Se ejecuta recién cuando la
transacción se confirma (on_commit), para que n8n lea datos ya guardados.
"""
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import OrdenTrabajo, Repuesto
from .priorizacion import solicitar_repriorizacion


@receiver(post_save, sender=OrdenTrabajo)
def on_orden_guardada(sender, instance, created, **kwargs):
    motivo = 'orden_nueva' if created else 'orden_modificada'
    transaction.on_commit(lambda: solicitar_repriorizacion(motivo))


@receiver(post_save, sender=Repuesto)
def on_repuesto_actualizado(sender, instance, **kwargs):
    transaction.on_commit(lambda: solicitar_repriorizacion('stock_modificado'))
