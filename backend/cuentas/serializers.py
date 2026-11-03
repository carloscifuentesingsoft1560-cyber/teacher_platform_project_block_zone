from rest_framework import serializers
from .models import Usuario


class UsuarioSerializer(serializers.ModelSerializer):
    nombre = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    facultades = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = ("id", "username", "nombre", "rol", "roles", "facultades")

    def get_roles(self,usuario):
        from .autorizacion import roles_vigentes
        return roles_vigentes(usuario)

    def get_facultades(self,usuario):
        from .autorizacion import ACCIONES
        roles=set(self.get_roles(usuario))
        return [a for a,permitidos in ACCIONES.items() if roles.intersection(permitidos)]

    def get_nombre(self, usuario):
        return usuario.get_full_name() or usuario.username


class IngresoSerializer(serializers.Serializer):
    usuario = serializers.CharField(max_length=150)
    contrasena = serializers.CharField(max_length=256, trim_whitespace=False, write_only=True)
