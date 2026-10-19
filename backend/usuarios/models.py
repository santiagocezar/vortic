from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    """
    Extiende el modelo de usuario de Django. El campo `password` ya se
    almacena hasheado por Django (RNF-09), y `is_active` cumple el rol de
    `activo` (baja lógica) del diccionario de datos.
    """
    ROL_JEFE = 'jefe'
    ROL_TECNICO = 'tecnico'
    ROL_CHOICES = [
        (ROL_JEFE, 'Jefe de Taller'),
        (ROL_TECNICO, 'Técnico'),
    ]
    rol = models.CharField(max_length=10, choices=ROL_CHOICES, default=ROL_TECNICO)

    def __str__(self):
        return f'{self.username} ({self.get_rol_display()})'
