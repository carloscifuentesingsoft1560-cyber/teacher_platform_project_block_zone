"""Evidencia administrativa B3-B1, sin habilitar movimientos deportivos."""
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError
import re


def validar_disposiciones(filas):
    campos = {'afectacion', 'origen', 'version', 'deportista', 'disciplina', 'grupo', 'nivel',
        'periodo', 'situacion', 'disposicion', 'destino', 'motivo', 'huella_contexto'}
    enteros = campos - {'situacion', 'disposicion', 'destino', 'motivo', 'huella_contexto'}
    if not isinstance(filas, list) or not filas:
        raise ValidationError('La evidencia requiere una lista no vacía de filas completas.')
    vistos = set()
    for f in filas:
        if (not isinstance(f, dict) or set(f) != campos
                or any(type(f[k]) is not int or f[k] < 1 for k in enteros)
                or not isinstance(f['huella_contexto'], str) or not re.fullmatch('[0-9a-f]{64}', f['huella_contexto'])
                or not isinstance(f['motivo'], str) or not 1 <= len(f['motivo'].strip()) <= 500
                or not isinstance(f['situacion'], str) or f['situacion'] not in ('activa', 'reserva', 'futura', 'suspendida', 'finalizada')
                or not isinstance(f['disposicion'], str) or f['disposicion'] not in ('revisar', 'reubicar', 'pendiente', 'continuidad', 'reserva', 'futura')
                or (f['destino'] is not None and (type(f['destino']) is not int or f['destino'] < 1))
                or (f['disposicion'] == 'reubicar') != (f['destino'] is not None)):
            raise ValidationError('Evidencia administrativa incompleta o con tipos incompatibles; requiere revisión.')
        if f['afectacion'] in vistos:
            raise ValidationError('La evidencia contiene afectaciones duplicadas.')
        vistos.add(f['afectacion'])


class EvidenciaInmutable(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    registrada_en = models.DateTimeField(auto_now_add=True)
    motivo = models.CharField(max_length=500)
    version_progresion = models.PositiveIntegerField()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('La evidencia administrativa no puede reescribirse.')
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('La evidencia administrativa no puede eliminarse.')


class RevisionAdministrativa(EvidenciaInmutable):
    progresion = models.ForeignKey('inscripciones.ProgresionInstitucional', on_delete=models.PROTECT, related_name='revisiones_administrativas')
    numero = models.PositiveIntegerField()
    anterior = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='siguiente')
    disposiciones = models.JSONField()

    def clean(self):
        validar_disposiciones(self.disposiciones)

    class Meta:
        ordering = ['numero', 'id']
        constraints = [models.UniqueConstraint(fields=['progresion', 'numero'], name='revision_admin_numero_unico'),
            models.CheckConstraint(condition=Q(numero__gte=1), name='revision_admin_numero_positivo')]


class ResultadoAdministrativo(EvidenciaInmutable):
    revision = models.ForeignKey(RevisionAdministrativa, on_delete=models.PROTECT, related_name='resultados')
    afectacion = models.ForeignKey('inscripciones.AfectacionInscripcion', on_delete=models.PROTECT)
    origen = models.ForeignKey('inscripciones.Inscripcion', on_delete=models.PROTECT, related_name='+')
    destino = models.OneToOneField('inscripciones.Inscripcion', on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    estado = models.CharField(max_length=12, choices=[('pendiente', 'Pendiente'), ('resuelta', 'Situación final resuelta'), ('ejecutada', 'Ejecutada')])
    fecha_efectiva = models.DateField(null=True, blank=True)
    clave = models.UUIDField()
    evidencia_ejecucion = models.JSONField(default=dict, blank=True)

    def clean(self):
        # No confiar en un objeto relacionado en caché tras una escritura ORM directa.
        p, a = self.revision.progresion, self.afectacion
        i = self._meta.get_field('origen').remote_field.model.objects.select_related('grupo__nivel').get(pk=self.origen_id)
        if (a.progresion_id != p.pk or a.inscripcion_id != i.pk or i.deportista_id != p.deportista_id
                or i.grupo.disciplina_id != p.disciplina_id or i.grupo.nivel.disciplina_id != p.disciplina_id):
            raise ValidationError('Relaciones administrativas incompatibles; requiere revisión institucional.')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['revision', 'afectacion'], name='resultado_admin_fila_unica'),
            models.UniqueConstraint(fields=['revision', 'clave'], name='resultado_admin_clave_unica'),
            models.UniqueConstraint(fields=['afectacion'], condition=Q(estado='ejecutada'), name='movimiento_afectacion_unico'),
            models.UniqueConstraint(fields=['origen'], condition=Q(estado='ejecutada'), name='movimiento_origen_unico'),
            models.CheckConstraint(condition=Q(estado='pendiente', destino__isnull=True, fecha_efectiva__isnull=True, evidencia_ejecucion={}) |
                Q(estado='resuelta', destino__isnull=True, fecha_efectiva__isnull=False, evidencia_ejecucion={}) |
                (Q(estado='ejecutada', destino__isnull=False, fecha_efectiva__isnull=False) & ~Q(evidencia_ejecucion={})), name='resultado_admin_estado_coherente')]
