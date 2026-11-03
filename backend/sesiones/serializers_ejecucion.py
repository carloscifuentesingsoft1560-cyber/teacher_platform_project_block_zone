from datetime import timezone as utc_timezone
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers
from .serializers import EntradaEstricta, Comando, PlanLectura
from .models import EjecucionSesion, ActividadEjecutada
from .ejecucion import ESTADOS


class FechaReal(serializers.Field):
    def to_internal_value(self, valor):
        try:
            fecha = parse_datetime(valor) if isinstance(valor, str) else None
        except (ValueError, TypeError):
            fecha = None
        if not fecha or timezone.is_naive(fecha):
            raise serializers.ValidationError('Se requiere fecha y hora ISO con zona explícita.')
        return fecha.astimezone(utc_timezone.utc).isoformat()


class ActividadEntrada(EntradaEstricta):
    tarea = serializers.IntegerField(min_value=1)
    resultado = serializers.ChoiceField(choices=['realizada', 'modificada', 'omitida'])
    minutos = serializers.IntegerField(min_value=0, max_value=32767)
    descripcion = serializers.CharField(max_length=8000, allow_blank=True, required=False)
    adaptacion_metodologica = serializers.CharField(max_length=8000, allow_blank=True, required=False)
    motivo_omision = serializers.CharField(max_length=1000, allow_blank=True, required=False)


class GuardarEjecucion(Comando):
    plan = serializers.IntegerField(min_value=1)
    inicio = FechaReal()
    fin = FechaReal()
    actividades = ActividadEntrada(many=True, allow_empty=False)
    observaciones = serializers.CharField(max_length=8000, allow_blank=True, required=False)
    incidencias_pedagogicas = serializers.CharField(max_length=8000, allow_blank=True, required=False)


class PrepararAsistencia(Comando):
    motivo = serializers.CharField(max_length=500)


class GuardarAsistencia(Comando):
    registros = serializers.DictField(child=serializers.ChoiceField(choices=['', *ESTADOS]))


class CorregirAsistencia(Comando):
    deportista = serializers.IntegerField(min_value=1)
    anterior = serializers.ChoiceField(choices=ESTADOS)
    nuevo = serializers.ChoiceField(choices=ESTADOS)
    motivo = serializers.CharField(max_length=500)


class ActividadLectura(serializers.ModelSerializer):
    class Meta:
        model = ActividadEjecutada
        fields = ['tarea', 'resultado', 'minutos', 'descripcion', 'adaptacion_metodologica', 'motivo_omision']


class EjecucionLectura(serializers.ModelSerializer):
    plan = PlanLectura(read_only=True)
    actividades = ActividadLectura(many=True, read_only=True)
    duracion_real_minutos = serializers.SerializerMethodField()
    tiempo_no_distribuido_minutos = serializers.SerializerMethodField()
    validacion_funcional = serializers.SerializerMethodField()

    def get_duracion_real_minutos(self, ejecucion):
        return (ejecucion.fin-ejecucion.inicio).total_seconds()/60

    def get_tiempo_no_distribuido_minutos(self, ejecucion):
        return self.get_duracion_real_minutos(ejecucion)-sum(a.minutos for a in ejecucion.actividades.all())

    def get_validacion_funcional(self, ejecucion):
        return 'pendiente'

    class Meta:
        model = EjecucionSesion
        fields = ['id', 'plan', 'inicio', 'fin', 'duracion_real_minutos', 'tiempo_no_distribuido_minutos', 'observaciones', 'incidencias_pedagogicas', 'actividades', 'creada_por', 'creada_en', 'finalizada_por', 'finalizada_en', 'validacion_funcional']
