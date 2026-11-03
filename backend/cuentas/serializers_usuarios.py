from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as ErrorDjango
from rest_framework import serializers
from .models import Usuario

class AdministracionUsuarioSerializer(serializers.ModelSerializer):
    # La unicidad condicional se valida con el estado completo en servicio/DB.
    roles = serializers.SerializerMethodField()
    def get_roles(self,u):
        from .autorizacion import roles_vigentes
        return roles_vigentes(u)

    rol = serializers.ChoiceField(choices=Usuario.Rol.choices, required=False)
    contrasena = serializers.CharField(write_only=True, required=False, min_length=12, max_length=256, trim_whitespace=False)
    class Meta:
        model = Usuario
        fields = ("id", "username", "first_name", "last_name", "email", "rol", "is_active", "contrasena", "roles")

    def validate(self, datos):
        if self.instance and "contrasena" in datos:
            raise serializers.ValidationError({"contrasena": "Utiliza el procedimiento de restablecimiento de acceso."})
        if "contrasena" in datos:
            cuenta = Usuario(**{k: v for k, v in datos.items() if k != "contrasena"})
            try:
                validate_password(datos["contrasena"], cuenta)
            except ErrorDjango as error:
                raise serializers.ValidationError({"contrasena": error.messages}) from error
        return datos

class SolicitarRestablecimientoSerializer(serializers.Serializer):
    contrasena_actual = serializers.CharField(write_only=True, trim_whitespace=False, max_length=256)

class ConfirmarRestablecimientoSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=100, trim_whitespace=False)
    contrasena = serializers.CharField(min_length=12, max_length=256, trim_whitespace=False, write_only=True)
