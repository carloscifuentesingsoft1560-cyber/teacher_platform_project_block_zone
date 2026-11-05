"""B2.1: expedientes pendientes. Ninguno acredita autoridad o competencia vigente."""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from .modelos_competencias import EvidenciaCompetencia


class ExpedientePendiente(EvidenciaCompetencia):
    identificador = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    registrada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    persona_registradora = models.ForeignKey('cuentas.Persona', on_delete=models.PROTECT, related_name='+')
    enlace_registrador = models.ForeignKey('cuentas.EnlaceIdentidad', on_delete=models.PROTECT, related_name='+')
    version_enlace_registrador = models.PositiveIntegerField()
    evidencia_registrador = models.UUIDField()
    registrada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        default_permissions = ('view',)
        constraints = [models.CheckConstraint(condition=Q(version_enlace_registrador__gte=1), name='%(class)s_reg_version')]


class MandatoInstitucional(ExpedientePendiente):
    persona = models.ForeignKey('cuentas.Persona', on_delete=models.PROTECT, related_name='+')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    enlace_identidad = models.ForeignKey('cuentas.EnlaceIdentidad', on_delete=models.PROTECT, related_name='+')
    version_enlace = models.PositiveIntegerField()
    evidencia_identidad = models.UUIDField()
    disciplina = models.ForeignKey('organizacion.Disciplina', on_delete=models.PROTECT)
    alcance_propuesto = models.CharField(max_length=240)

    class Meta(ExpedientePendiente.Meta):
        abstract = False
        indexes = [models.Index(fields=['persona', 'disciplina'], name='mandato_persona_disciplina')]
        constraints = ExpedientePendiente.Meta.constraints + [
            models.CheckConstraint(condition=Q(version_enlace__gte=1), name='mandato_identidad_version'),
            models.CheckConstraint(condition=Q(alcance_propuesto__regex=r'\S'), name='mandato_alcance_contenido'),
            models.CheckConstraint(condition=~Q(persona=F('persona_registradora')), name='mandato_no_autoregistro'),
        ]


class AcreditacionEmisora(ExpedientePendiente):
    competencia = models.ForeignKey('cuentas.CompetenciaEmisora', on_delete=models.PROTECT, related_name='+')
    evento_competencia = models.ForeignKey('cuentas.EventoCompetenciaEmisora', on_delete=models.PROTECT, related_name='+')
    mandato = models.ForeignKey(MandatoInstitucional, on_delete=models.PROTECT, related_name='+')
    evento_mandato = models.ForeignKey('cuentas.EventoMandatoInstitucional', on_delete=models.PROTECT, related_name='+')

    class Meta(ExpedientePendiente.Meta):
        abstract = False
        indexes = [models.Index(fields=['competencia', 'mandato'], name='acreditacion_fundamentos')]


class EventoPendiente(EvidenciaCompetencia):
    numero = models.PositiveIntegerField()
    accion = models.CharField(max_length=12, choices=[(x, x) for x in ('propuesta', 'revision', 'retiro')])
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    persona_actor = models.ForeignKey('cuentas.Persona', on_delete=models.PROTECT, related_name='+')
    enlace_actor = models.ForeignKey('cuentas.EnlaceIdentidad', on_delete=models.PROTECT, related_name='+')
    version_enlace_actor = models.PositiveIntegerField()
    evidencia_actor = models.UUIDField()
    clave = models.UUIDField()
    solicitud = models.JSONField()
    motivo = models.CharField(max_length=500)
    referencia_evidencia = models.UUIDField()
    vigente_desde_propuesta = models.DateTimeField()
    vigente_hasta_propuesta = models.DateTimeField(null=True, blank=True)
    registrada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        default_permissions = ('view',)
        ordering = ['numero']
        constraints = [
            models.UniqueConstraint(fields=['actor', 'clave'], name='%(class)s_clave'),
            models.CheckConstraint(condition=Q(numero__gte=1, version_enlace_actor__gte=1), name='%(class)s_version'),
            models.CheckConstraint(condition=Q(accion__in=['propuesta', 'revision', 'retiro']), name='%(class)s_accion'),
            models.CheckConstraint(condition=Q(motivo__regex=r'\S'), name='%(class)s_motivo'),
            models.CheckConstraint(condition=Q(vigente_hasta_propuesta__isnull=True) | Q(vigente_hasta_propuesta__gt=F('vigente_desde_propuesta')), name='%(class)s_intervalo'),
            models.CheckConstraint(condition=Q(numero=1, accion='propuesta', anterior__isnull=True) | Q(numero__gt=1, accion__in=['revision', 'retiro'], anterior__isnull=False), name='%(class)s_origen'),
        ]


class EventoMandatoInstitucional(EventoPendiente):
    mandato = models.ForeignKey(MandatoInstitucional, on_delete=models.PROTECT, related_name='eventos')
    anterior = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='siguiente')

    class Meta(EventoPendiente.Meta):
        abstract = False
        constraints = EventoPendiente.Meta.constraints + [
            models.UniqueConstraint(fields=['mandato', 'numero'], name='evento_mandato_numero'),
        ]


class EventoAcreditacionEmisora(EventoPendiente):
    acreditacion = models.ForeignKey(AcreditacionEmisora, on_delete=models.PROTECT, related_name='eventos')
    anterior = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='siguiente')

    class Meta(EventoPendiente.Meta):
        abstract = False
        constraints = EventoPendiente.Meta.constraints + [
            models.UniqueConstraint(fields=['acreditacion', 'numero'], name='evento_acreditacion_numero'),
        ]
