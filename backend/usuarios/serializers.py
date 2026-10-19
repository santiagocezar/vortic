from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Usuario


class UsuarioSerializer(serializers.ModelSerializer):
    """
    Hallazgo F (revisión de testing práctico): antes de esto, dar de alta
    un técnico o cambiarle la contraseña dependía de entrar a /admin/ de
    Django — una barrera real para un taller sin nadie técnico a mano en
    el día a día. `password` es write-only y opcional en la edición (se
    cambia solo si se manda); en el alta es obligatoria.
    """
    password = serializers.CharField(write_only=True, required=False, allow_blank=False, min_length=8)

    class Meta:
        model = Usuario
        fields = ['id', 'username', 'rol', 'is_active', 'password']

    def validate(self, attrs):
        if self.instance is None and not attrs.get('password'):
            raise serializers.ValidationError({'password': 'La contraseña es obligatoria para crear un usuario.'})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        usuario = Usuario(**validated_data)
        usuario.set_password(password)
        usuario.save()
        return usuario

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class TokenObtainPairConRolSerializer(TokenObtainPairSerializer):
    """
    Igual al login de simplejwt, pero además devuelve `username` y `rol`
    en la respuesta (no solo dentro del JWT) para que el frontend sepa,
    apenas loguea, si tiene que mostrar la vista de Jefe o la de Técnico
    (HU-06) sin tener que decodificar el token.
    """

    def validate(self, attrs):
        data = super().validate(attrs)
        data['username'] = self.user.username
        data['rol'] = self.user.rol
        return data
