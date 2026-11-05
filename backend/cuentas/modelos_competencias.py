"""B1: propuestas de competencia; ningún registro concede facultades operativas."""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class HistorialCompetenciaQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('La evidencia de competencia es inmutable.')

    def delete(self):
        raise ValidationError('La evidencia de competencia no se elimina.')

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError('La evidencia de competencia es inmutable.')


class EvidenciaCompetencia(models.Model):
    objects = HistorialCompetenciaQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding or self.pk is not None:
            raise ValidationError('La evidencia de competencia es inmutable.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('La evidencia de competencia no se elimina.')


class CompetenciaEmisora(EvidenciaCompetencia):
    """Identidad y ámbito propuestos, nunca una designación aprobada."""
    identificador = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    persona = models.ForeignKey('cuentas.Persona', on_delete=models.PROTECT)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    enlace_identidad = models.ForeignKey('cuentas.EnlaceIdentidad', on_delete=models.PROTECT)
    version_enlace = models.PositiveIntegerField()
    evidencia_identidad = models.UUIDField()
    disciplina = models.ForeignKey('organizacion.Disciplina', on_delete=models.PROTECT)
    alcance_propuesto = models.CharField(max_length=240)
    registrada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    registrada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ('view',)
        indexes = [models.Index(fields=['persona', 'disciplina'], name='competencia_persona_disciplina')]
        constraints = [
            models.CheckConstraint(condition=Q(version_enlace__gte=1), name='competencia_enlace_version'),
            models.CheckConstraint(condition=Q(alcance_propuesto__regex=r'\S'), name='competencia_alcance_no_vacio'),
        ]


class EventoCompetenciaEmisora(EvidenciaCompetencia):
    """Cadena de propuestas/revisiones/retiro. B1 no admite aprobar ni activar."""
    competencia = models.ForeignKey(CompetenciaEmisora, on_delete=models.PROTECT, related_name='eventos')
    numero = models.PositiveIntegerField()
    anterior = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='siguiente')
    accion = models.CharField(max_length=12, choices=[(x, x) for x in ('propuesta', 'revision', 'retiro')])
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    clave = models.UUIDField()
    motivo = models.CharField(max_length=500)
    referencia_evidencia = models.UUIDField()
    vigente_desde_propuesta = models.DateTimeField()
    vigente_hasta_propuesta = models.DateTimeField(null=True, blank=True)
    registrada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ('view',)
        ordering = ['numero']
        constraints = [
            models.UniqueConstraint(fields=['competencia', 'numero'], name='competencia_evento_numero'),
            models.UniqueConstraint(fields=['actor', 'clave'], name='competencia_evento_clave'),
            models.CheckConstraint(condition=Q(numero__gte=1), name='competencia_numero_positivo'),
            models.CheckConstraint(condition=Q(accion__in=['propuesta', 'revision', 'retiro']), name='competencia_accion_borrador'),
            models.CheckConstraint(condition=Q(motivo__regex=r'\S'), name='competencia_motivo_no_vacio'),
            models.CheckConstraint(condition=Q(vigente_hasta_propuesta__isnull=True) | Q(vigente_hasta_propuesta__gt=F('vigente_desde_propuesta')), name='competencia_intervalo_propuesto'),
            models.CheckConstraint(condition=Q(numero=1, accion='propuesta', anterior__isnull=True) | (Q(numero__gt=1, accion__in=['revision', 'retiro'], anterior__isnull=False)), name='competencia_evento_origen'),
        ]
