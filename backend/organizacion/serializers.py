from rest_framework import serializers
from cuentas.models import Usuario
from .models import Disciplina, Nivel, Periodo, Grupo, Horario, Asignacion
from .servicios import validar_horarios

class DisciplinaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Disciplina
        fields = ("id", "codigo", "nombre", "activo")

class NivelSerializer(serializers.ModelSerializer):
    disciplina_nombre = serializers.CharField(source="disciplina.nombre", read_only=True)
    class Meta:
        model = Nivel
        fields = ("id", "disciplina", "disciplina_nombre", "codigo", "nombre", "orden", "activo")

    def validate(self, datos):
        disciplina = datos.get("disciplina", getattr(self.instance, "disciplina", None))
        if not disciplina.activo and datos.get("activo", getattr(self.instance, "activo", True)):
            raise serializers.ValidationError({"disciplina": "La disciplina debe estar activa."})
        if self.instance and self.instance.grupos.exists() and disciplina.pk != self.instance.disciplina_id:
            raise serializers.ValidationError({"disciplina": "No cambies la disciplina de un nivel con grupos asociados."})
        return datos

class PeriodoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Periodo
        fields = ("id", "codigo", "nombre", "fecha_inicio", "fecha_fin", "activo")

    def validate(self, datos):
        inicio = datos.get("fecha_inicio", getattr(self.instance, "fecha_inicio", None))
        fin = datos.get("fecha_fin", getattr(self.instance, "fecha_fin", None))
        if inicio > fin:
            raise serializers.ValidationError({"fecha_fin": "No puede preceder al inicio."})
        from deportistas.permisos import esquema_disponible
        hay_inscripciones = bool(self.instance and esquema_disponible() and self.instance.grupos.filter(inscripciones__isnull=False).exists())
        if self.instance and (hay_inscripciones or self.instance.grupos.filter(asignaciones__isnull=False).exists()):
            if inicio != self.instance.fecha_inicio or fin != self.instance.fecha_fin:
                raise serializers.ValidationError("El periodo tiene asignaciones históricas; crea un periodo nuevo para otras fechas.")
        return datos

class HorarioSerializer(serializers.ModelSerializer):
    duracion_minutos = serializers.IntegerField(read_only=True)
    class Meta:
        model = Horario
        fields = ("id", "dia", "hora_inicio", "hora_fin", "duracion_minutos")
        read_only_fields = ("id",)

class GrupoSerializer(serializers.ModelSerializer):
    horarios = HorarioSerializer(many=True, required=False)
    disciplina_nombre = serializers.CharField(source="disciplina.nombre", read_only=True)
    nivel_nombre = serializers.CharField(source="nivel.nombre", read_only=True)
    periodo_nombre = serializers.CharField(source="periodo.nombre", read_only=True)
    class Meta:
        model = Grupo
        fields = ("id", "codigo", "nombre", "disciplina", "disciplina_nombre", "nivel", "nivel_nombre", "periodo", "periodo_nombre", "activo", "cupo_maximo", "horarios")

    def validate(self, datos):
        disciplina = datos.get("disciplina", getattr(self.instance, "disciplina", None))
        nivel = datos.get("nivel", getattr(self.instance, "nivel", None))
        periodo = datos.get("periodo", getattr(self.instance, "periodo", None))
        if nivel.disciplina_id != disciplina.pk:
            raise serializers.ValidationError({"nivel": "El nivel no pertenece a la disciplina seleccionada."})
        if datos.get("activo", getattr(self.instance, "activo", True)) and not all([disciplina.activo, nivel.activo, periodo.activo]):
            raise serializers.ValidationError("Un grupo activo requiere disciplina, nivel y periodo activos.")
        if not self.instance and "horarios" not in datos:
            raise serializers.ValidationError({"horarios": "Define al menos un horario."})
        if "horarios" in datos:
            validar_horarios(datos["horarios"])
        return datos

    def to_representation(self, instancia):
        datos = super().to_representation(instancia)
        datos["horarios"] = HorarioSerializer(instancia.horarios.filter(activo=True), many=True).data
        return datos

class AsignacionSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.SerializerMethodField()
    grupo_nombre = serializers.CharField(source="grupo.nombre", read_only=True)
    class Meta:
        model = Asignacion
        fields = ("id", "grupo", "grupo_nombre", "usuario", "usuario_nombre", "tipo", "fecha_inicio", "fecha_fin")

    def get_usuario_nombre(self, objeto):
        return objeto.usuario.get_full_name() or objeto.usuario.username


class ProfesorOperativoSerializer(serializers.ModelSerializer):
    nombre = serializers.SerializerMethodField()
    grupos = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = ("id", "username", "nombre", "rol", "is_active", "grupos")

    def get_nombre(self, usuario):
        return usuario.get_full_name() or usuario.username

    def get_grupos(self, usuario):
        from .alcance import en_fecha
        asignaciones = Asignacion.objects.filter(en_fecha(), usuario=usuario, tipo="profesor").select_related("grupo").prefetch_related("grupo__horarios")
        grupos = {a.grupo_id: a.grupo for a in asignaciones}
        return [{
            "id": grupo.pk, "codigo": grupo.codigo, "nombre": grupo.nombre, "activo": grupo.activo,
            "horarios": HorarioSerializer(grupo.horarios.filter(activo=True), many=True).data,
        } for grupo in grupos.values()]