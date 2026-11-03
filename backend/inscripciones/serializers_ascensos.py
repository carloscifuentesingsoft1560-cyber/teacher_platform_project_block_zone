from rest_framework import serializers
from .modelos_ascensos import ProgresionInstitucional, AfectacionInscripcion


class EntradaEstricta(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError('Se requiere un objeto de campos.')
        desconocidos = set(data) - set(self.fields)
        if hasattr(data, 'lists'):
            desconocidos |= {k for k, valores in data.lists() if len(valores) != 1}
        if desconocidos:
            raise serializers.ValidationError({k: 'Campo no permitido o repetido.' for k in sorted(desconocidos)})
        return super().to_internal_value(data)


class CrearAscensoSerializer(EntradaEstricta):
    deportista = serializers.IntegerField(min_value=1)
    disciplina = serializers.IntegerField(min_value=1)
    inscripcion_referencia = serializers.IntegerField(min_value=1)
    nivel_destino = serializers.IntegerField(min_value=1)
    justificacion = serializers.CharField(max_length=500, allow_blank=False, trim_whitespace=True)


class ContextoAscensoSerializer(EntradaEstricta):
    deportista = serializers.IntegerField(min_value=1)
    disciplina = serializers.IntegerField(min_value=1, required=False)
    vista = serializers.ChoiceField(choices=['referencias', 'disciplinas'], default='referencias')
    search = serializers.CharField(max_length=120, required=False, allow_blank=True)
    page = serializers.IntegerField(min_value=1, required=False)


class NivelesAscensoSerializer(EntradaEstricta):
    deportista = serializers.IntegerField(min_value=1)
    disciplina = serializers.IntegerField(min_value=1)
    inscripcion_referencia = serializers.IntegerField(min_value=1)
    search = serializers.CharField(max_length=120, required=False, allow_blank=True)
    page = serializers.IntegerField(min_value=1, required=False)


class FiltrosAscensoSerializer(EntradaEstricta):
    estado_decision = serializers.ChoiceField(choices=['pendiente', 'aprobada', 'rechazada'], required=False)
    disciplina = serializers.IntegerField(min_value=1, required=False)
    deportista = serializers.IntegerField(min_value=1, required=False)
    page = serializers.IntegerField(min_value=1, required=False)


class AscensoLecturaSerializer(serializers.ModelSerializer):
    nombre_deportista = serializers.SerializerMethodField()
    disciplina_nombre = serializers.CharField(source='disciplina.nombre')
    nivel_origen_nombre = serializers.CharField(source='nivel_origen.nombre')
    nivel_destino_nombre = serializers.CharField(source='nivel_destino.nombre')
    periodo_nombre = serializers.CharField(source='periodo.nombre')

    class Meta:
        model = ProgresionInstitucional
        fields = ('id', 'deportista', 'nombre_deportista', 'disciplina', 'disciplina_nombre',
            'inscripcion_referencia', 'nivel_origen', 'nivel_origen_nombre', 'nivel_destino',
            'nivel_destino_nombre', 'periodo', 'periodo_nombre', 'justificacion', 'creado_en',
            'estado_decision', 'estado_plan')
        read_only_fields = fields

    def get_nombre_deportista(self, obj):
        return obj.deportista.nombres + ' ' + obj.deportista.apellidos


class AscensoCoordinacionSerializer(AscensoLecturaSerializer):
    profesor_proponente = serializers.SerializerMethodField()

    class Meta(AscensoLecturaSerializer.Meta):
        fields = AscensoLecturaSerializer.Meta.fields + ('version', 'profesor_proponente')
        read_only_fields = fields

    def get_profesor_proponente(self, obj):
        from .revision_ascensos import actor_minimo
        return actor_minimo(obj.creado_por)


class DecisionAscensoSerializer(EntradaEstricta):
    version = serializers.IntegerField(min_value=1)
    decision = serializers.ChoiceField(choices=['aprobar', 'rechazar'])
    resolucion = serializers.CharField(max_length=500, allow_blank=False, trim_whitespace=True)


class DisposicionAscensoSerializer(EntradaEstricta):
    version = serializers.IntegerField(min_value=1)
    afectacion = serializers.IntegerField(min_value=1)
    disposicion = serializers.ChoiceField(choices=AfectacionInscripcion._meta.get_field('disposicion').choices)
    motivo = serializers.CharField(max_length=500, allow_blank=False, trim_whitespace=True)
    destino = serializers.IntegerField(min_value=1, allow_null=True, required=False, default=None)

    def validate(self, datos):
        if (datos['disposicion'] == 'reubicar') != (datos['destino'] is not None):
            raise serializers.ValidationError('Solo reubicar exige y admite un destino propuesto.')
        return datos
