"""Comprobaciones manuales trazables; un parentesco nunca concede facultades."""
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError
from rest_framework import serializers
from organizacion.servicios import bloquear_usuarios
from auditoria.servicios import registrar
from .models import ComprobacionFacultad, VinculoAcudiente, Acudiente, TipoAutorizacion


class FacultadesPendientes(APIException):
    status_code = 503
    default_detail = 'La comprobación de facultades requiere una migración pendiente de autorización.'


def esquema_facultades():
    if 'deportistas_comprobacionfacultad' not in connection.introspection.table_names():
        return False
    with connection.cursor() as c:
        return 'comprobacion_facultad_id' in {f.name for f in connection.introspection.get_table_description(c, 'deportistas_autorizacion')}


def exigir_esquema():
    if not esquema_facultades():
        raise FacultadesPendientes()


class DecisionFacultad(serializers.Serializer):
    version = serializers.IntegerField(min_value=1)
    metodo = serializers.ChoiceField(choices=['presencial','documental'])
    # Clave opaca de custodia externa: no documentos, URLs públicas ni texto libre.
    referencia_evidencia = serializers.UUIDField()
    tipo_autorizacion = serializers.PrimaryKeyRelatedField(queryset=TipoAutorizacion.objects.all())
    resultado = serializers.ChoiceField(choices=['pendiente','verificada','rechazada','revocada'])
    identidad_contrastada = serializers.BooleanField()
    facultad_contrastada = serializers.BooleanField()
    comprobada_en = serializers.DateTimeField()
    vigente_desde = serializers.DateField()
    vigente_hasta = serializers.DateField(required=False, allow_null=True)

    def to_internal_value(self, data):
        if set(data) - set(self.fields):
            raise ValidationError({'non_field_errors': ['Campos no permitidos en la comprobación.']})
        # Evitar que valores personales introducidos por error reaparezcan en mensajes.
        if data.get('metodo') not in ('presencial','documental') or data.get('resultado') not in ('pendiente','verificada','rechazada','revocada'):
            raise ValidationError({'non_field_errors': ['Selecciona método y resultado admitidos.']})
        return super().to_internal_value(data)

    def validate(self, data):
        if data['comprobada_en'] > timezone.now():
            raise ValidationError({'comprobada_en': 'No puede ser futura.'})
        if data.get('vigente_hasta') and data['vigente_hasta'] < data['vigente_desde']:
            raise ValidationError({'vigente_hasta': 'Vigencia inválida.'})
        if data['resultado'] == 'verificada' and not (data['identidad_contrastada'] and data['facultad_contrastada']):
            raise ValidationError('Una revisión insuficiente no acredita la facultad.')
        if data['referencia_evidencia'].version != 4:
            raise ValidationError({'referencia_evidencia': 'Indica una clave opaca UUID v4 del registro de custodia.'})
        return data


class ComprobacionSerializer(serializers.ModelSerializer):
    alcance = serializers.CharField(source='tipo_autorizacion.finalidad', read_only=True)
    numero_version_texto = serializers.IntegerField(source='tipo_autorizacion.numero_version', read_only=True)
    class Meta:
        model = ComprobacionFacultad
        fields = ('id','vinculo','tipo_autorizacion','alcance','numero_version_texto','metodo','referencia_evidencia','resultado',
                  'identidad_contrastada','facultad_contrastada','comprobada_en','registrada_en','responsable','vigente_desde','vigente_hasta','version_resultante')
        read_only_fields = fields


def estado_efectivo(evento, hoy=None):
    hoy = hoy or timezone.localdate()
    if evento.resultado == 'verificada' and (evento.vigente_desde > hoy or (evento.vigente_hasta and evento.vigente_hasta < hoy)):
        return 'pendiente'
    return evento.resultado


def resumen_facultades(vinculo):
    if not esquema_facultades():
        return []
    actuales = {}
    hoy = timezone.localdate()
    vinculo_vigente = vinculo.acudiente.activo and vinculo.fecha_inicio <= hoy and (not vinculo.fecha_fin or vinculo.fecha_fin > hoy)
    for e in vinculo.comprobaciones.select_related('tipo_autorizacion').all():
        if e.tipo_autorizacion_id not in actuales:
            actuales[e.tipo_autorizacion_id] = {
                'id': e.pk, 'tipo_autorizacion': e.tipo_autorizacion_id, 'alcance': e.tipo_autorizacion.finalidad,
                'numero_version_texto': e.tipo_autorizacion.numero_version, 'resultado': e.resultado,
                'estado_efectivo': ('pendiente' if e.resultado == 'verificada' and (not vinculo_vigente or not e.tipo_autorizacion.activo) else estado_efectivo(e)), 'metodo': e.metodo,
                'comprobada_en': e.comprobada_en, 'registrada_en': e.registrada_en,
                'vigente_desde': e.vigente_desde, 'vigente_hasta': e.vigente_hasta, 'responsable': e.responsable_id,
            }
    return list(actuales.values())


def facultad_autorizacion_vigente(autorizacion):
    if autorizacion.otorgante != 'acudiente':
        return None  # No corresponde una acreditación de acudiente a este otorgante.
    if not autorizacion.comprobacion_facultad_id or not autorizacion.vinculo_acudiente_id:
        return False
    v = autorizacion.vinculo_acudiente
    hoy = timezone.localdate()
    if not v.acudiente.activo or v.fecha_inicio > hoy or (v.fecha_fin and v.fecha_fin <= hoy) or not autorizacion.tipo.activo:
        return False
    actual = v.comprobaciones.filter(tipo_autorizacion_id=autorizacion.tipo_id).first()
    return bool(actual and actual.pk == autorizacion.comprobacion_facultad_id and estado_efectivo(actual) == 'verificada')


@transaction.atomic
def comprobar_facultad(vinculo, actor, datos):
    from .servicios import version_valida
    bloquear_usuarios(actor, permitir_coordinador=True)
    exigir_esquema()
    vinculo = VinculoAcudiente.objects.select_for_update().get(pk=vinculo.pk)
    contacto = Acudiente.objects.select_for_update().get(pk=vinculo.acudiente_id)
    datos = dict(datos)
    version_valida(vinculo, datos)
    hoy = timezone.localdate()
    if not contacto.activo or vinculo.fecha_inicio > hoy or (vinculo.fecha_fin and vinculo.fecha_fin <= hoy):
        raise ValidationError('El vínculo no está vigente.')
    # También validar llamadas internas; no confiar exclusivamente en el serializer REST.
    serial = DecisionFacultad(data={**datos, 'version': vinculo.version, 'tipo_autorizacion': getattr(datos.get('tipo_autorizacion'), 'pk', datos.get('tipo_autorizacion'))})
    serial.is_valid(raise_exception=True)
    datos = dict(serial.validated_data); datos.pop('version')
    tipo = TipoAutorizacion.objects.select_for_update().get(pk=datos['tipo_autorizacion'].pk)
    if not tipo.activo:
        raise ValidationError('El alcance no está activo.')
    if datos['vigente_desde'] < vinculo.fecha_inicio or (vinculo.fecha_fin and (not datos.get('vigente_hasta') or datos['vigente_hasta'] >= vinculo.fecha_fin)):
        raise ValidationError('Vigencia fuera del vínculo.')
    anterior = vinculo.comprobaciones.filter(tipo_autorizacion=tipo).first()
    if datos['resultado'] == 'revocada' and (not anterior or anterior.resultado != 'verificada'):
        raise ValidationError('No existe una acreditación anterior que retirar para este alcance.')
    vinculo.version += 1
    vinculo.actualizado_por = actor
    # No transformar estados legacy ni inferir facultad universal. La decisión vive en el historial.
    vinculo.save(update_fields=['version','actualizado_por','actualizado_en'])
    evento = ComprobacionFacultad.objects.create(vinculo=vinculo, responsable=actor, version_resultante=vinculo.version, **datos)
    registrar(actor, evento, 'comprobar_facultad', ['resultado','metodo','tipo_autorizacion'])
    return evento


def acreditar_otorgante(vinculo, datos):
    """Se llama bajo el mismo bloqueo global de usuarios que decisiones y cuentas."""
    exigir_esquema()
    vinculo = VinculoAcudiente.objects.select_for_update().get(pk=vinculo.pk)
    contacto = Acudiente.objects.select_for_update().get(pk=vinculo.acudiente_id)
    hoy = timezone.localdate()
    evento = vinculo.comprobaciones.filter(tipo_autorizacion=datos['tipo']).first()
    if not contacto.activo or vinculo.fecha_inicio > hoy or (vinculo.fecha_fin and vinculo.fecha_fin <= hoy):
        raise ValidationError('El vínculo no está vigente.')
    if not evento or estado_efectivo(evento) != 'verificada':
        raise ValidationError('La facultad no está verificada y vigente para esta finalidad y versión.')
    declaracion = timezone.localtime(datos['declarada_en']).date()
    hasta = datos.get('vigente_hasta')
    if (datos['vigente_desde'] < evento.vigente_desde or declaracion < evento.vigente_desde
        or datos['declarada_en'] < evento.comprobada_en
        or (evento.vigente_hasta and (not hasta or hasta > evento.vigente_hasta or declaracion > evento.vigente_hasta))):
        raise ValidationError('La autorización excede la comprobación acreditada.')
    return evento
