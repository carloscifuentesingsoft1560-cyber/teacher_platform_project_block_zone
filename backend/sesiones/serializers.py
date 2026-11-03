from collections.abc import Mapping
from rest_framework import serializers
from .models import Sesion, PlanSesion, TareaSesion


class EntradaEstricta(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError('Se requiere un objeto JSON.')
        desconocidos = set(data) - set(self.fields)
        if desconocidos:
            raise serializers.ValidationError({k: 'Campo no permitido.' for k in sorted(desconocidos)})
        return super().to_internal_value(data)


class CrearSesion(EntradaEstricta):
    clave = serializers.UUIDField()
    grupo = serializers.IntegerField(min_value=1)
    profesor = serializers.IntegerField(min_value=1, required=False)
    fecha = serializers.DateField()
    hora_inicio = serializers.TimeField()
    hora_fin = serializers.TimeField()

    def validate(self, datos):
        if any(datos[c].tzinfo is not None for c in ('hora_inicio', 'hora_fin')):
            raise serializers.ValidationError('La franja usa horas locales de America/Bogota sin offset.')
        if any(datos[c].second or datos[c].microsecond for c in ('hora_inicio', 'hora_fin')):
            raise serializers.ValidationError('Las horas deben expresarse en minutos completos.')
        return datos


class Comando(EntradaEstricta):
    clave = serializers.UUIDField()
    version = serializers.IntegerField(min_value=1)


class CancelarSesion(Comando):
    motivo = serializers.CharField(max_length=240)


class TareaEntrada(EntradaEstricta):
    fase = serializers.ChoiceField(choices=['inicial', 'central', 'final'])
    minutos = serializers.IntegerField(min_value=1, max_value=32767)
    instrucciones = serializers.CharField()
    ejercicio_version_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)


class EditarPlan(Comando):
    objetivo = serializers.CharField()
    tareas = TareaEntrada(many=True, allow_empty=False)
    malla_version_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    clase_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)


class TareaLectura(serializers.ModelSerializer):
    class Meta:
        model = TareaSesion
        fields = ['orden', 'fase', 'minutos', 'instrucciones', 'ejercicio_version']


class PlanLectura(serializers.ModelSerializer):
    tareas = TareaLectura(many=True, read_only=True)

    class Meta:
        model = PlanSesion
        fields = ['id', 'numero', 'autor', 'creado_en', 'objetivo', 'malla_version', 'clase', 'tareas']


class SesionLectura(serializers.ModelSerializer):
    planes = PlanLectura(many=True, read_only=True)

    class Meta:
        model = Sesion
        fields = ['id', 'uuid', 'grupo', 'profesor', 'fecha', 'hora_inicio', 'hora_fin', 'estado', 'version', 'asistencia_confirmada', 'inicio_real', 'fin_real', 'plan_ejecutado', 'planes']
