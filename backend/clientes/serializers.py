from rest_framework import serializers
from .models import Cliente, extraer_digitos


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = ['id', 'razon_social', 'telefono', 'activo']

    def validate_telefono(self, valor):
        # Hallazgo E (revisión de testing práctico): nada impedía crear un
        # cliente nuevo con el mismo teléfono que uno ya activo — en el
        # apuro del mostrador, si el buscador de HU-02 no encontraba la
        # coincidencia a tiempo (o el usuario no esperaba a que respondiera),
        # el mismo cliente terminaba con dos fichas y su historial (HU-10)
        # quedaba partido en dos. Se compara por dígitos (mismo criterio que
        # WhatsApp) para que "351-412-3456" y "3514123456" cuenten como el
        # mismo número.
        digitos = extraer_digitos(valor)
        existente = Cliente.objects.filter(activo=True).exclude(pk=getattr(self.instance, 'pk', None))
        for c in existente:
            if extraer_digitos(c.telefono) == digitos:
                raise serializers.ValidationError(
                    f'Ya existe un cliente activo con este teléfono: {c.razon_social} (id {c.id}).'
                )
        return valor
