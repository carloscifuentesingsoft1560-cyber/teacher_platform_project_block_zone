from django.utils import timezone
from rest_framework import serializers
from deportistas.serializers import Estricto
from .models import Inscripcion, Propuesta, ReservaCupo, EventoInscripcion

class InscripcionSerializer(Estricto):
    nombre_deportista=serializers.SerializerMethodField()
    situacion_temporal=serializers.SerializerMethodField()
    nombre_grupo=serializers.CharField(source="grupo.nombre",read_only=True)
    nivel=serializers.CharField(source="grupo.nivel.nombre",read_only=True)
    periodo=serializers.CharField(source="grupo.periodo.nombre",read_only=True)
    motivo=serializers.CharField(write_only=True,max_length=240)
    class Meta:
        model=Inscripcion
        fields=("id","deportista","nombre_deportista","grupo","nombre_grupo","nivel","periodo","fecha_ingreso","fecha_salida","estado","situacion_temporal","causa_salida","inscripcion_anterior","version","motivo")
        read_only_fields=("id","fecha_salida","estado","situacion_temporal","causa_salida","inscripcion_anterior","version")
        validators=[]
    def get_situacion_temporal(self,obj):
        hoy=timezone.localdate()
        if obj.fecha_ingreso>hoy:
            return "programada"
        if obj.fecha_salida and obj.fecha_salida<=hoy:
            return "finalizada"
        if obj.grupo.periodo.fecha_fin<hoy:
            return "periodo_finalizado"
        if obj.estado=="suspendida" and not obj.reservas.filter(liberada_en__isnull=True,fecha_vencimiento__gte=hoy).exists():
            return "reserva_vencida"
        return obj.estado
    def get_nombre_deportista(self,obj):
        return obj.deportista.nombres+" "+obj.deportista.apellidos

class PropuestaSerializer(Estricto):
    mecanismo_deshabilitado = serializers.SerializerMethodField()
    aviso_procedimiento = serializers.SerializerMethodField()
    nivel_anterior=serializers.CharField(source="inscripcion_origen.grupo.nivel.nombre",read_only=True,default=None)
    nivel_nuevo=serializers.CharField(source="grupo_destino.nivel.nombre",read_only=True)
    codigo_destino=serializers.CharField(source='grupo_destino.codigo',read_only=True)
    nombre_destino=serializers.CharField(source='grupo_destino.nombre',read_only=True)
    periodo_destino=serializers.CharField(source='grupo_destino.periodo.nombre',read_only=True)
    class Meta:
        model=Propuesta
        fields=("id","tipo","deportista","inscripcion_origen","grupo_destino","fecha_efectiva","justificacion","estado","creado_por","creado_en","resuelta_por","resuelta_en","resolucion","inscripcion_resultante","version","nivel_anterior","nivel_nuevo","codigo_destino","nombre_destino","periodo_destino","mecanismo_deshabilitado","aviso_procedimiento")
        read_only_fields=("id","estado","creado_por","creado_en","resuelta_por","resuelta_en","resolucion","inscripcion_resultante","version")
        validators=[]

    def get_mecanismo_deshabilitado(self, obj):
        return obj.tipo == 'nivel'

    def get_aviso_procedimiento(self, obj):
        from .compatibilidad_propuestas import AVISO_NIVEL_ANTIGUO
        return AVISO_NIVEL_ANTIGUO if obj.tipo == 'nivel' else ''

class ReservaSerializer(serializers.ModelSerializer):
    class Meta:
        model=ReservaCupo
        fields=("id","fecha_inicio","fecha_vencimiento","motivo","autorizada_por","liberada_en","liberada_por")

class EventoSerializer(serializers.ModelSerializer):
    class Meta:
        model=EventoInscripcion
        fields=("id","tipo","estado_anterior","estado_resultante","fecha_efectiva","registrado_en","actor","motivo")
