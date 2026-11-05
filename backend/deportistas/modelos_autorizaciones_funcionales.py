"""B2.3 escenario A: documentos pendientes; nunca autorizaciones operativas."""
import uuid
from django.conf import settings
from django.db import models
from django.db.models import F, Q
from cuentas.modelos_competencias import EvidenciaCompetencia


def fk(destino, **kwargs):
    return models.ForeignKey(destino, on_delete=models.PROTECT, related_name='+', **kwargs)


class DocumentoFuncionalPendiente(EvidenciaCompetencia):
    class Meta:
        abstract = True
        # No conceder lectura ni escritura por permisos genéricos de Django.
        default_permissions = ()


class ExpedienteAutorizacionFuncional(DocumentoFuncionalPendiente):
    identificador = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    deportista = fk('deportistas.Deportista')
    persona = fk('cuentas.Persona')
    enlace_identidad = fk('cuentas.EnlaceIdentidad')
    version_enlace = models.PositiveIntegerField()
    evidencia_identidad = models.UUIDField()
    disciplina = fk('organizacion.Disciplina')
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta(DocumentoFuncionalPendiente.Meta):
        abstract = False
        indexes = [models.Index(fields=['persona', 'disciplina'], name='b23_persona_disciplina')]
        constraints = [models.CheckConstraint(condition=Q(version_enlace__gte=1), name='b23_identidad_version')]


class PropuestaDecisionFuncionalVersion(DocumentoFuncionalPendiente):
    expediente = models.ForeignKey(ExpedienteAutorizacionFuncional, on_delete=models.PROTECT, related_name='versiones')
    numero = models.PositiveIntegerField()
    anterior = models.OneToOneField('self', null=True, on_delete=models.PROTECT, related_name='siguiente')
    acreditacion = fk('cuentas.AcreditacionEmisora')
    evento_acreditacion = fk('cuentas.EventoAcreditacionEmisora')
    emitida_en_declarada = models.DateTimeField(null=True)
    desde_propuesta = models.DateTimeField()
    hasta_propuesta = models.DateTimeField()
    registrada_en = models.DateTimeField(auto_now_add=True)

    class Meta(DocumentoFuncionalPendiente.Meta):
        abstract = False
        constraints = [models.UniqueConstraint(fields=['expediente', 'numero'], name='b23_version_numero'),
            models.CheckConstraint(condition=Q(numero=1, anterior__isnull=True) | Q(numero__gt=1, anterior__isnull=False), name='b23_version_origen'),
            models.CheckConstraint(condition=Q(hasta_propuesta__gt=F('desde_propuesta')) &
                (Q(emitida_en_declarada__isnull=True) | Q(emitida_en_declarada__lte=F('desde_propuesta'))), name='b23_intervalo_propuesto')]


class AlcanceDecisionFuncional(DocumentoFuncionalPendiente):
    version = models.ForeignKey(PropuestaDecisionFuncionalVersion, on_delete=models.PROTECT, related_name='alcances')
    perfil_version = fk('biblioteca.PerfilFuncionalVersion')
    evento_perfil = fk('biblioteca.EventoPerfilFuncional')
    correspondencia_version = fk('biblioteca.CorrespondenciaFuncionalVersion', null=True)
    evento_correspondencia = fk('biblioteca.EventoCorrespondenciaFuncional', null=True)

    class Meta(DocumentoFuncionalPendiente.Meta):
        abstract = False
        constraints = [models.UniqueConstraint(fields=['version', 'perfil_version'], name='b23_alcance_perfil'),
            models.CheckConstraint(condition=Q(correspondencia_version__isnull=True, evento_correspondencia__isnull=True) |
                Q(correspondencia_version__isnull=False, evento_correspondencia__isnull=False), name='b23_correspondencia_par')]


class CondicionDecisionFuncional(DocumentoFuncionalPendiente):
    alcance = models.ForeignKey(AlcanceDecisionFuncional, on_delete=models.PROTECT, related_name='condiciones')
    condicion = fk('biblioteca.CondicionPerfilFuncional')
    modalidad = models.CharField(max_length=12, choices=[(x, x) for x in ('condicionar', 'excluir')])

    class Meta(DocumentoFuncionalPendiente.Meta):
        abstract = False
        constraints = [models.UniqueConstraint(fields=['alcance', 'condicion'], name='b23_condicion_unica'),
            models.CheckConstraint(condition=Q(modalidad__in=['condicionar', 'excluir']), name='b23_condicion_modalidad')]


class AdaptacionDecisionFuncional(DocumentoFuncionalPendiente):
    alcance = models.ForeignKey(AlcanceDecisionFuncional, on_delete=models.PROTECT, related_name='adaptaciones')
    condicion_individual = fk(CondicionDecisionFuncional)
    adaptacion = fk('biblioteca.AdaptacionPerfilFuncional')

    class Meta(DocumentoFuncionalPendiente.Meta):
        abstract = False
        constraints = [models.UniqueConstraint(fields=['alcance', 'adaptacion'], name='b23_adaptacion_unica')]


class ReferenciaEvidenciaFuncional(DocumentoFuncionalPendiente):
    version = models.ForeignKey(PropuestaDecisionFuncionalVersion, on_delete=models.PROTECT, related_name='evidencias')
    referencia = models.UUIDField()
    huella_documento = models.CharField(max_length=64)
    # Identificador opaco del registro de custodia externo; no URL/ruta/nombre.
    registro_custodia = models.UUIDField()

    class Meta(DocumentoFuncionalPendiente.Meta):
        abstract = False
        constraints = [models.UniqueConstraint(fields=['version', 'referencia'], name='b23_evidencia_unica'),
            models.CheckConstraint(condition=Q(huella_documento__regex=r'^[0-9a-f]{64}$'), name='b23_evidencia_huella')]


class EventoExpedienteFuncional(DocumentoFuncionalPendiente):
    expediente = models.ForeignKey(ExpedienteAutorizacionFuncional, on_delete=models.PROTECT, related_name='eventos')
    version = fk(PropuestaDecisionFuncionalVersion)
    numero = models.PositiveIntegerField()
    anterior = models.OneToOneField('self', null=True, on_delete=models.PROTECT, related_name='siguiente')
    accion = models.CharField(max_length=12, choices=[(x, x) for x in ('propuesta', 'revision', 'retiro')])
    actor = fk(settings.AUTH_USER_MODEL)
    persona_actor = fk('cuentas.Persona')
    enlace_actor = fk('cuentas.EnlaceIdentidad')
    version_enlace_actor = models.PositiveIntegerField()
    evidencia_actor = models.UUIDField()
    clave = models.UUIDField()
    huella = models.CharField(max_length=64)
    registrada_en = models.DateTimeField(auto_now_add=True)

    class Meta(DocumentoFuncionalPendiente.Meta):
        abstract = False
        constraints = [models.UniqueConstraint(fields=['expediente', 'numero'], name='b23_evento_numero'),
            models.UniqueConstraint(fields=['actor', 'clave'], name='b23_evento_clave'),
            models.CheckConstraint(condition=Q(version_enlace_actor__gte=1, huella__regex=r'^[0-9a-f]{64}$'), name='b23_evento_datos'),
            models.CheckConstraint(condition=Q(numero=1, anterior__isnull=True, accion='propuesta') |
                Q(numero__gt=1, anterior__isnull=False, accion__in=['propuesta', 'revision', 'retiro']), name='b23_evento_cadena')]
