import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q, F
from .documentos_reglas import PAISES_ISO, TIPOS_CO, PATRON_NUMERO, MOTIVOS_CAMBIO

def codigo_deportista():
    return "ZB-" + uuid.uuid4().hex.upper()

class Registro(models.Model):
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    actualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)
    class Meta:
        abstract = True

class Deportista(Registro):
    identificador_publico = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    codigo_interno = models.CharField(max_length=35, default=codigo_deportista, unique=True, editable=False)
    tipo_documento = models.ForeignKey("TipoDocumento", to_field="codigo", null=True, blank=True, on_delete=models.PROTECT, related_name="deportistas")
    numero_documento = models.CharField(max_length=40, null=True, blank=True)
    pais_emisor = models.CharField(max_length=2, null=True, blank=True)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    fecha_nacimiento = models.DateField()
    estado = models.CharField(max_length=12, choices=[(x,x) for x in ("activo","inactivo","archivado")], default="activo")
    motivo_estado = models.CharField(max_length=160, blank=True)
    class Meta:
        ordering = ["apellidos", "nombres", "id"]
        indexes = [models.Index(fields=["estado","apellidos"], name="deportista_estado_nombre")]
        constraints = [
            models.CheckConstraint(condition=Q(estado__in=["activo","inactivo","archivado"]), name="deportista_estado_valido"),
            models.CheckConstraint(condition=Q(tipo_documento__isnull=True,numero_documento__isnull=True,pais_emisor__isnull=True)|Q(tipo_documento__isnull=False,numero_documento__isnull=False,pais_emisor__isnull=False),name="documento_completo_o_pendiente"),
            models.CheckConstraint(condition=Q(numero_documento__isnull=True)|Q(numero_documento__regex=PATRON_NUMERO),name="numero_documento_canonico"),
            models.CheckConstraint(condition=Q(pais_emisor__isnull=True)|Q(pais_emisor__in=PAISES_ISO),name="pais_documento_iso_valido"),
            models.CheckConstraint(condition=~Q(tipo_documento_id__in=TIPOS_CO)|Q(pais_emisor="CO",numero_documento__regex=r"^[A-Z0-9]+$"),name="documento_colombiano_canonico"),
            models.UniqueConstraint(fields=["tipo_documento","pais_emisor","numero_documento"],condition=Q(tipo_documento__isnull=False,numero_documento__isnull=False),name="documento_deportista_unico"),
        ]

class Acudiente(Registro):
    identificador_publico = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    telefono = models.CharField(max_length=30, blank=True)
    correo = models.EmailField(blank=True)
    activo = models.BooleanField(default=True)
    class Meta:
        ordering = ["apellidos","nombres","id"]

class VinculoAcudiente(Registro):
    deportista = models.ForeignKey(Deportista, on_delete=models.PROTECT, related_name="vinculos")
    acudiente = models.ForeignKey(Acudiente, on_delete=models.PROTECT, related_name="vinculos")
    parentesco = models.CharField(max_length=60, blank=True)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    es_contacto_principal = models.BooleanField(default=False)
    facultad_para_autorizar = models.CharField(max_length=20, choices=[(x,x) for x in ("pendiente","verificada","no_acreditada")], default="pendiente")
    verificada_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    verificada_en = models.DateTimeField(null=True, blank=True)
    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(fecha_fin__isnull=True)|Q(fecha_fin__gt=F("fecha_inicio")), name="vinculo_fechas_validas"),
            models.UniqueConstraint(fields=["deportista","acudiente","fecha_inicio"], name="vinculo_inicio_unico"),
            models.CheckConstraint(condition=Q(facultad_para_autorizar__in=["pendiente","verificada","no_acreditada"]), name="vinculo_facultad_valida"),
            models.CheckConstraint(condition=~Q(facultad_para_autorizar="verificada")|(Q(verificada_por__isnull=False)&Q(verificada_en__isnull=False)), name="vinculo_verificacion_completa"),
        ]

class HistorialFacultadQuerySet(models.QuerySet):
    def update(self, **kwargs):
        from django.core.exceptions import ValidationError
        raise ValidationError('Las comprobaciones son inmutables; registra una decisión nueva.')

    def delete(self):
        from django.core.exceptions import ValidationError
        raise ValidationError('No se elimina el historial de facultades.')


class ComprobacionFacultad(models.Model):
    vinculo = models.ForeignKey(VinculoAcudiente, on_delete=models.PROTECT, related_name='comprobaciones')
    tipo_autorizacion = models.ForeignKey('TipoAutorizacion', on_delete=models.PROTECT, related_name='comprobaciones_facultad')
    metodo = models.CharField(max_length=12, choices=[(x,x) for x in ('presencial','documental')])
    referencia_evidencia = models.UUIDField()
    resultado = models.CharField(max_length=12, choices=[(x,x) for x in ('pendiente','verificada','rechazada','revocada')])
    identidad_contrastada = models.BooleanField(default=False)
    facultad_contrastada = models.BooleanField(default=False)
    comprobada_en = models.DateTimeField()
    registrada_en = models.DateTimeField(auto_now_add=True)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    vigente_desde = models.DateField()
    vigente_hasta = models.DateField(null=True, blank=True)
    version_resultante = models.PositiveIntegerField()
    objects = HistorialFacultadQuerySet.as_manager()

    class Meta:
        ordering = ['-version_resultante']
        default_permissions = ('view',)
        constraints = [
            models.UniqueConstraint(fields=['vinculo','version_resultante'], name='facultad_version_unica'),
            models.CheckConstraint(condition=Q(metodo__in=['presencial','documental']), name='facultad_metodo_valido'),
            models.CheckConstraint(condition=Q(resultado__in=['pendiente','verificada','rechazada','revocada']), name='facultad_resultado_valido'),
            models.CheckConstraint(condition=~Q(resultado='verificada') | Q(identidad_contrastada=True, facultad_contrastada=True), name='facultad_revision_suficiente'),
            models.CheckConstraint(condition=Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gte=F('vigente_desde')), name='facultad_vigencia_valida'),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding or self.pk is not None:
            from django.core.exceptions import ValidationError
            raise ValidationError('Las comprobaciones son inmutables.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        raise ValidationError('No se elimina el historial de facultades.')


class TipoAutorizacion(Registro):
    codigo = models.SlugField(max_length=50)
    numero_version = models.PositiveIntegerField(default=1)
    finalidad = models.CharField(max_length=240)
    referencia_texto_aprobado = models.CharField(max_length=240)
    activo = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["codigo","numero_version"], name="tipo_autorizacion_version_unica")]

class Autorizacion(Registro):
    deportista = models.ForeignKey(Deportista, on_delete=models.PROTECT, related_name="autorizaciones")
    tipo = models.ForeignKey(TipoAutorizacion, on_delete=models.PROTECT)
    otorgante = models.CharField(max_length=12, choices=[("deportista","Deportista"),("acudiente","Acudiente")])
    vinculo_acudiente = models.ForeignKey(VinculoAcudiente, null=True, blank=True, on_delete=models.PROTECT)
    comprobacion_facultad = models.ForeignKey('ComprobacionFacultad', null=True, blank=True, on_delete=models.PROTECT, related_name='autorizaciones')
    decision = models.CharField(max_length=10, choices=[("otorgada","Otorgada"),("denegada","Denegada")])
    declarada_en = models.DateTimeField()
    vigente_desde = models.DateField()
    vigente_hasta = models.DateField(null=True, blank=True)
    referencia_evidencia = models.CharField(max_length=240, blank=True)
    revocada_en = models.DateTimeField(null=True, blank=True)
    motivo_revocacion = models.CharField(max_length=160, blank=True)
    class Meta:
        constraints = [
            models.CheckConstraint(condition=(Q(otorgante="deportista",vinculo_acudiente__isnull=True)|Q(otorgante="acudiente",vinculo_acudiente__isnull=False)), name="autorizacion_otorgante_coherente"),
            models.CheckConstraint(condition=Q(vigente_hasta__isnull=True)|Q(vigente_hasta__gte=F("vigente_desde")), name="autorizacion_vigencia_valida"),
            models.CheckConstraint(condition=Q(decision__in=["otorgada","denegada"]), name="autorizacion_decision_valida"),
        ]

class PoliticaDatos(Registro):
    codigo = models.SlugField(max_length=50, unique=True)
    finalidad = models.CharField(max_length=240)
    criterio_conservacion = models.TextField()
    procedimiento_supresion = models.TextField()
    referencia_aprobacion = models.CharField(max_length=240)
    edad_autonomia = models.PositiveSmallIntegerField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    # No valores legales predeterminados ni borrado automático.

class TipoDocumento(models.Model):
    codigo = models.CharField(max_length=24, unique=True)
    nombre = models.CharField(max_length=120)
    referencia_aprobacion = models.CharField(max_length=240)
    activo = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    class Meta:
        ordering = ["codigo"]
        constraints = [models.CheckConstraint(condition=Q(codigo__regex=r"^[A-Z][A-Z0-9_]{0,23}$"),name="tipo_documento_codigo_canonico")]

class CambioDocumentoDeportista(models.Model):
    deportista = models.ForeignKey(Deportista,on_delete=models.PROTECT,related_name="cambios_documentales")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True)
    motivo = models.CharField(max_length=32,choices=[(x,x) for x in ("registro_inicial",*MOTIVOS_CAMBIO)])
    tipo_anterior = models.CharField(max_length=24,blank=True)
    pais_anterior = models.CharField(max_length=2,blank=True)
    documento_anterior_enmascarado = models.CharField(max_length=8,blank=True)
    tipo_nuevo = models.CharField(max_length=24,blank=True)
    pais_nuevo = models.CharField(max_length=2,blank=True)
    documento_nuevo_enmascarado = models.CharField(max_length=8,blank=True)
    version_resultante = models.PositiveIntegerField()
    class Meta:
        ordering = ["-fecha","-id"]
        constraints = [
            models.UniqueConstraint(fields=["deportista","version_resultante"],name="cambio_documental_version_unico"),
            models.CheckConstraint(condition=Q(motivo__in=["registro_inicial",*MOTIVOS_CAMBIO]),name="cambio_documental_motivo_valido"),
            models.CheckConstraint(condition=Q(documento_anterior_enmascarado="")|Q(documento_anterior_enmascarado__regex=r"^\*{4}[A-Z0-9/-]{0,4}$"),name="historia_anterior_solo_mascara"),
            models.CheckConstraint(condition=Q(documento_nuevo_enmascarado="")|Q(documento_nuevo_enmascarado__regex=r"^\*{4}[A-Z0-9/-]{0,4}$"),name="historia_nueva_solo_mascara"),
        ]


from .modelos_autorizaciones_funcionales import (ExpedienteAutorizacionFuncional,
    PropuestaDecisionFuncionalVersion, AlcanceDecisionFuncional, CondicionDecisionFuncional,
    AdaptacionDecisionFuncional, ReferenciaEvidenciaFuncional, EventoExpedienteFuncional)  # noqa: E402,F401
