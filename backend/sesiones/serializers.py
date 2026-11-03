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
    objetivo = serializers.CharField(required=False, allow_blank=True)
    ejercicio_version_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)


class EditarPlan(Comando):
    objetivo = serializers.CharField()
    tareas = TareaEntrada(many=True, allow_empty=False)
    malla_version_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    clase_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    programa_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    fase_curricular_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    semana_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    competencias_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False)


class TareaLectura(serializers.ModelSerializer):
    ejercicio_detalle = serializers.SerializerMethodField()

    def get_ejercicio_detalle(self, tarea):
        v = tarea.ejercicio_version
        if not v:
            return None
        return dict(id=v.pk, uuid=str(v.uuid), numero=v.numero, nombre=v.nombre, objetivo=v.objetivo, metodologia=v.metodologia, descripcion=v.descripcion, riesgos=v.riesgos, controles=v.controles, estado_actual=v.estado, vigente_actual=v.vigente)

    class Meta:
        model = TareaSesion
        fields = ['orden', 'fase', 'minutos', 'objetivo', 'instrucciones', 'ejercicio_version', 'ejercicio_detalle']


class PlanLectura(serializers.ModelSerializer):
    tareas = TareaLectura(many=True, read_only=True)
    competencias = serializers.SerializerMethodField()
    contexto_curricular = serializers.SerializerMethodField()

    def get_competencias(self, plan):
        return [dict(id=c.pk, uuid=str(c.uuid), clave_logica=str(c.clave_logica), texto=c.texto, version=c.version_id) for c in plan.competencias.all()]

    def get_contexto_curricular(self, plan):
        v = plan.malla_version
        return dict(programa=plan.programa_id, malla_uuid=str(v.uuid) if v else None, numero=v.numero if v else None, estado_actual=v.estado if v else None, vigente_actual=v.vigente if v else None, fase_nombre=plan.fase_curricular.nombre if plan.fase_curricular else None, semana_ordinal=plan.semana.ordinal if plan.semana else None, clase_ordinal=plan.clase.ordinal if plan.clase else None)

    class Meta:
        model = PlanSesion
        fields = ['id', 'numero', 'revision_anterior', 'autor', 'creado_en', 'objetivo', 'programa', 'malla_version', 'fase_curricular', 'semana', 'clase', 'competencias', 'contexto_curricular', 'tareas']


class SesionLectura(serializers.ModelSerializer):
    planes = PlanLectura(many=True, read_only=True)

    class Meta:
        model = Sesion
        fields = ['id', 'uuid', 'grupo', 'profesor', 'fecha', 'hora_inicio', 'hora_fin', 'estado', 'version', 'asistencia_confirmada', 'inicio_real', 'fin_real', 'plan_ejecutado', 'planes']
