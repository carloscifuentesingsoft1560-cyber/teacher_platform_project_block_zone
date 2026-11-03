from rest_framework import serializers
from .models import TipoDocumento,CambioDocumentoDeportista
from .serializers import Estricto
from .documentos_reglas import texto_canonico,MOTIVOS_CAMBIO

class CodigoDocumentoCampo(serializers.SlugRelatedField):
    def __init__(self,**kwargs):
        kwargs.setdefault("error_messages",{"does_not_exist":"El tipo documental no está disponible.","invalid":"El tipo documental no es válido."})
        super().__init__(slug_field="codigo",queryset=TipoDocumento.objects.all(),**kwargs)
    def to_internal_value(self,data):
        return super().to_internal_value(texto_canonico(data))

class SolicitudDocumentoSerializer(serializers.Serializer):
    version=serializers.IntegerField(min_value=1)
    tipo_documento=CodigoDocumentoCampo(allow_null=True)
    numero_documento=serializers.CharField(max_length=120,allow_null=True,allow_blank=True)
    pais_emisor=serializers.CharField(max_length=8,allow_null=True,allow_blank=True,required=False)
    motivo=serializers.ChoiceField(choices=MOTIVOS_CAMBIO,error_messages={"invalid_choice":"Selecciona un motivo administrativo permitido."})
    def to_internal_value(self,data):
        if set(data)-set(self.fields):
            raise serializers.ValidationError("Campos fuera del cambio documental.")
        return super().to_internal_value(data)

class TipoDocumentoSerializer(Estricto):
    codigo=serializers.CharField(max_length=24)
    class Meta:
        model=TipoDocumento
        fields=("codigo","nombre","referencia_aprobacion","activo","version")
        validators=[]
    def validate_codigo(self,valor):
        import re
        valor=texto_canonico(valor)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,23}",valor):
            raise serializers.ValidationError("Código de tipo documental no válido.")
        return valor

class HistorialDocumentoSerializer(serializers.ModelSerializer):
    class Meta:
        model=CambioDocumentoDeportista
        fields=("id","fecha","actor","motivo","tipo_anterior","pais_anterior","documento_anterior_enmascarado","tipo_nuevo","pais_nuevo","documento_nuevo_enmascarado","version_resultante")

class ConsultaDocumentoSerializer(serializers.Serializer):
    tipo_documento=CodigoDocumentoCampo()
    numero_documento=serializers.CharField(max_length=120)
    pais_emisor=serializers.CharField(max_length=8,allow_null=True,allow_blank=True,required=False)
    def to_internal_value(self,data):
        if set(data)-set(self.fields):
            raise serializers.ValidationError("Campos fuera de la consulta documental.")
        return super().to_internal_value(data)
