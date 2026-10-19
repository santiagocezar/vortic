from django.core.exceptions import ValidationError
from django.db import models


def extraer_digitos(telefono: str) -> str:
    """Solo los dígitos de un teléfono tal cual lo cargó el usuario (con
    espacios, guiones, +54, etc.) — lo que realmente usa wa.me/<numero>."""
    return ''.join(filter(str.isdigit, telefono or ''))


def numero_whatsapp(telefono: str) -> str:
    """
    Convierte un teléfono argentino tal como lo carga el usuario al formato
    que pide wa.me: 549 + código de área + número, sin el 0 ni el 15.
    Ejemplos: "3564 123456" -> "5493564123456";
              "(03564) 15-123456" -> "5493564123456";
              "+54 9 3564 123456" -> "5493564123456".
    Devuelve '' si no se puede obtener un número de 10 dígitos.
    """
    d = extraer_digitos(telefono)
    if d.startswith('549') and len(d) == 13:
        return d
    if d.startswith('54') and len(d) == 12:
        d = d[2:]
    d = d.lstrip('0')
    if len(d) == 12:
        # Celular escrito con el 15 después del código de área (2 a 4 dígitos).
        for k in (2, 3, 4):
            if d[k:k + 2] == '15':
                d = d[:k] + d[k + 2:]
                break
    return '549' + d if len(d) == 10 else ''


def validar_telefono(valor: str) -> None:
    """
    El teléfono se usa para el aviso por WhatsApp (CU-05), así que tiene que
    poder convertirse a formato internacional. Se acepta como lo escriba el
    usuario (con espacios, guiones, 0, 15 o +54), pero tiene que incluir el
    código de área.
    """
    if not numero_whatsapp(valor):
        raise ValidationError(
            'Ingresá el teléfono con código de área, por ejemplo 3564 123456 o (03564) 15-123456.'
        )


class Cliente(models.Model):
    """
    Eje principal del sistema: las órdenes de trabajo se vinculan al
    cliente, no al equipo (ver informe, sección 6 - Modelo de Datos).
    """
    razon_social = models.CharField(max_length=200)
    telefono = models.CharField(
        max_length=30, validators=[validar_telefono],
        help_text='Obligatorio para habilitar aviso por WhatsApp (CU-05)',
    )
    activo = models.BooleanField(default=True)  # baja lógica, no eliminación física
    # Nota: la criticidad NO va acá — vive en OrdenTrabajo. Un mismo cliente
    # trae trabajos con distinta urgencia según el día (ver taller/models.py).

    class Meta:
        ordering = ['razon_social']

    def __str__(self):
        return self.razon_social
