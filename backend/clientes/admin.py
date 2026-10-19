from django.contrib import admin
from .models import Cliente


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('razon_social', 'telefono', 'activo')
    search_fields = ('razon_social', 'telefono')
