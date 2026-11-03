from django.utils import timezone
from rest_framework import serializers
from .models import Deportista, Acudiente, VinculoAcudiente, TipoAutorizacion, Autorizacion, PoliticaDatos, TipoDocumento
from .documentos_reglas import presentacion,enmascarar,texto_canonico

class Estricto(serializers.ModelSerializer):
    def to_internal_value(self, data):
        prohibidos = set(data) - set(self.fields)
        prohibidos |= {k for k in data if k in self.fields and self.fields[k].read_only}
        if prohibidos:
            raise serializers.ValidationError({k:"Campo no permitido." for k in sorted(prohibidos)})
        return super().to_internal_value(data)

class DeportistaSerializer(Estricto):
    tipo_documento = serializers.SlugRelatedField(slug_field="codigo",queryset=TipoDocumento.objects.all(),required=False,allow_null=True,error_messages={"does_not_exist":"El tipo documental no está disponible.","invalid":"El tipo documental no es válido."})
    numero_documento = serializers.CharField(max_length=120,required=False,allow_null=True,allow_blank=True)
    pais_emisor = serializers.CharField(max_length=8,required=False,allow_null=True,allow_blank=True)
    documento_presentacion = serializers.SerializerMethodField()
    class Meta:
        model = Deportista
        fields = ("id","identificador_publico","codigo_interno","nombres","apellidos","fecha_nacimiento","estado","motivo_estado","version","tipo_documento","numero_documento","pais_emisor","documento_presentacion")
        read_only_fields = ("id","identificador_publico","codigo_interno")
        validators = []
    def get_documento_presentacion(self,obj):
        return presentacion(obj)
    def to_internal_value(self,data):
        data=dict(data)
        if data.get("tipo_documento") is not None:
            data["tipo_documento"]=texto_canonico(data["tipo_documento"])
        return super().to_internal_value(data)
    def validate_fecha_nacimiento(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError("No puede ser futura.")
        return value

class DeportistaProfesorSerializer(serializers.ModelSerializer):
    tipo_documento = serializers.CharField(source="tipo_documento_id",read_only=True,allow_null=True)
    numero_documento_enmascarado = serializers.SerializerMethodField()
    documento_presentacion = serializers.SerializerMethodField()
    class Meta:
        model = Deportista
        fields = ("id","identificador_publico","nombres","apellidos","estado","tipo_documento","numero_documento_enmascarado","documento_presentacion")
    def get_numero_documento_enmascarado(self,obj):
        return enmascarar(obj.numero_documento)
    def get_documento_presentacion(self,obj):
        return presentacion(obj,restringida=True)

class AcudienteSerializer(Estricto):
    class Meta:
        model = Acudiente
        fields = ("id","identificador_publico","nombres","apellidos","telefono","correo","activo","version")
        read_only_fields = ("id","identificador_publico")
    def validate(self, data):
        telefono = data.get("telefono",getattr(self.instance,"telefono",""))
        correo = data.get("correo",getattr(self.instance,"correo",""))
        if not telefono and not correo:
            raise serializers.ValidationError("Define al menos un contacto.")
        return data

class VinculoSerializer(Estricto):
    facultad_para_autorizar = serializers.SerializerMethodField()
    facultades = serializers.SerializerMethodField()
    control_facultades_disponible = serializers.SerializerMethodField()
    def get_facultades(self, obj):
        from .facultades import resumen_facultades
        if not hasattr(obj, '_resumen_facultades'):
            obj._resumen_facultades = resumen_facultades(obj)
        return obj._resumen_facultades
    def get_facultad_para_autorizar(self, obj):
        # Resumen informativo; la autorización siempre valida el alcance exacto.
        eventos = self.get_facultades(obj)
        return eventos[0]['estado_efectivo'] if eventos else 'pendiente'
    def get_control_facultades_disponible(self, obj):
        from .facultades import esquema_facultades
        return esquema_facultades()
    class Meta:
        model = VinculoAcudiente
        fields = ("id","deportista","acudiente","parentesco","fecha_inicio","fecha_fin","es_contacto_principal","facultad_para_autorizar","verificada_en","version","facultades","control_facultades_disponible")
        read_only_fields = ("id","facultad_para_autorizar","verificada_en")

class TipoSerializer(Estricto):
    class Meta:
        model = TipoAutorizacion
        fields = ("id","codigo","numero_version","finalidad","referencia_texto_aprobado","activo","version")
        read_only_fields = ("id",)

class AutorizacionSerializer(Estricto):
    facultad_vigente = serializers.SerializerMethodField()
    def get_facultad_vigente(self, obj):
        from .facultades import facultad_autorizacion_vigente
        return facultad_autorizacion_vigente(obj)
    class Meta:
        model = Autorizacion
        fields = ("id","deportista","tipo","otorgante","vinculo_acudiente","decision","declarada_en","vigente_desde","vigente_hasta","referencia_evidencia","revocada_en","motivo_revocacion","version","comprobacion_facultad","facultad_vigente")
        read_only_fields = ("id","revocada_en","motivo_revocacion","comprobacion_facultad")

class PoliticaSerializer(Estricto):
    class Meta:
        model = PoliticaDatos
        fields = ("id","codigo","finalidad","criterio_conservacion","procedimiento_supresion","referencia_aprobacion","edad_autonomia","activo","version")
        read_only_fields = ("id",)
