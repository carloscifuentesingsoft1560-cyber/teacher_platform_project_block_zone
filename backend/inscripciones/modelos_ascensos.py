"""Estructura institucional. No ejecuta movimientos de inscripciones."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, F
from django.utils import timezone
from deportistas.models import Registro


class Validado(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class ProgresionInstitucional(Validado, Registro):
    deportista = models.ForeignKey('deportistas.Deportista', on_delete=models.PROTECT)
    disciplina = models.ForeignKey('organizacion.Disciplina', on_delete=models.PROTECT)
    nivel_origen = models.ForeignKey('organizacion.Nivel', on_delete=models.PROTECT, related_name='+')
    nivel_destino = models.ForeignKey('organizacion.Nivel', on_delete=models.PROTECT, related_name='+')
    periodo = models.ForeignKey('organizacion.Periodo', on_delete=models.PROTECT)
    inscripcion_referencia = models.ForeignKey('inscripciones.Inscripcion', on_delete=models.PROTECT, related_name='+')
    justificacion = models.CharField(max_length=500)
    estado_decision = models.CharField(max_length=12, choices=[(x, x) for x in ('pendiente', 'aprobada', 'rechazada')], default='pendiente')
    estado_plan = models.CharField(max_length=12, choices=[(x, x) for x in ('pendiente', 'parcial', 'preparado')], default='pendiente')
    decidida_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    decidida_en = models.DateTimeField(null=True, blank=True)
    resolucion = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ['-creado_en', '-id']
        indexes = [models.Index(fields=['deportista', 'disciplina', 'estado_decision'], name='ascenso_persona_disciplina')]
        constraints = [
            models.CheckConstraint(condition=~Q(nivel_origen=F('nivel_destino')), name='ascenso_niveles_distintos'),
            models.CheckConstraint(condition=Q(estado_decision__in=['pendiente', 'aprobada', 'rechazada']), name='ascenso_decision_valida'),
            models.CheckConstraint(condition=Q(estado_plan__in=['pendiente', 'parcial', 'preparado']), name='ascenso_plan_valido'),
            models.CheckConstraint(condition=Q(estado_decision='pendiente', decidida_por__isnull=True, decidida_en__isnull=True, resolucion='') | (Q(estado_decision__in=['aprobada', 'rechazada'], decidida_por__isnull=False, decidida_en__isnull=False) & ~Q(resolucion='')), name='ascenso_decision_coherente'),
            models.UniqueConstraint(fields=['deportista', 'disciplina'], condition=Q(estado_decision__in=['pendiente', 'aprobada']), name='ascenso_abierto_unico'),
        ]

    def clean(self):
        if self.nivel_origen.disciplina_id != self.disciplina_id or self.nivel_destino.disciplina_id != self.disciplina_id:
            raise ValidationError('Los niveles deben pertenecer a la disciplina de la progresión.')
        origen = self.inscripcion_referencia
        if (origen.deportista_id != self.deportista_id or origen.grupo.disciplina_id != self.disciplina_id
                or origen.grupo.nivel_id != self.nivel_origen_id or origen.grupo.periodo_id != self.periodo_id):
            raise ValidationError('La inscripción de referencia no corresponde al deportista, disciplina, nivel y periodo.')


class AfectacionInscripcion(Validado, models.Model):
    progresion = models.ForeignKey(ProgresionInstitucional, on_delete=models.PROTECT, related_name='afectaciones')
    inscripcion = models.ForeignKey('inscripciones.Inscripcion', on_delete=models.PROTECT, related_name='+')
    version_observada = models.PositiveIntegerField()
    situacion_observada = models.CharField(max_length=12, choices=[(x, x) for x in ('activa', 'reserva', 'futura', 'suspendida')])
    disposicion = models.CharField(max_length=12, choices=[(x, x) for x in ('revisar', 'reubicar', 'pendiente', 'continuidad', 'reserva', 'futura')], default='revisar')
    destino = models.ForeignKey('organizacion.Grupo', null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    motivo = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['progresion', 'inscripcion'], name='ascenso_afectacion_unica'),
            models.CheckConstraint(condition=Q(situacion_observada__in=['activa', 'reserva', 'futura', 'suspendida']), name='ascenso_situacion_valida'),
            models.CheckConstraint(condition=Q(disposicion__in=['revisar', 'reubicar', 'pendiente', 'continuidad', 'reserva', 'futura']), name='ascenso_disposicion_valida'),
            models.CheckConstraint(condition=Q(disposicion='reubicar', destino__isnull=False) | (~Q(disposicion='reubicar') & Q(destino__isnull=True)), name='ascenso_destino_coherente'),
        ]

    def clean(self):
        p, i = self.progresion, self.inscripcion
        if i.deportista_id != p.deportista_id or i.grupo.disciplina_id != p.disciplina_id:
            raise ValidationError('La afectación debe pertenecer al deportista y disciplina de la progresión.')
        if self.destino_id and (self.destino.disciplina_id != p.disciplina_id or self.destino.nivel_id != p.nivel_destino_id or self.destino_id == i.grupo_id):
            raise ValidationError('Destino incompatible con la progresión.')


class ExcepcionPedagogica(Validado, Registro):
    afectacion = models.ForeignKey(AfectacionInscripcion, on_delete=models.PROTECT, related_name='excepciones')
    motivo = models.CharField(max_length=500)
    fecha_inicio = models.DateField()
    fecha_limite = models.DateField()
    estado = models.CharField(max_length=10, choices=[(x, x) for x in ('autorizada', 'revocada')], default='autorizada')
    revocada_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    revocada_en = models.DateTimeField(null=True, blank=True)
    motivo_revocacion = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(fecha_limite__gte=F('fecha_inicio')), name='ascenso_excepcion_fechas'),
            models.CheckConstraint(condition=Q(estado__in=['autorizada', 'revocada']), name='ascenso_excepcion_estado'),
            models.CheckConstraint(condition=Q(estado='autorizada', revocada_por__isnull=True, revocada_en__isnull=True, motivo_revocacion='') | (Q(estado='revocada', revocada_por__isnull=False, revocada_en__isnull=False) & ~Q(motivo_revocacion='')), name='ascenso_revocacion_coherente'),
            models.UniqueConstraint(fields=['afectacion'], condition=Q(estado='autorizada'), name='ascenso_excepcion_unica'),
        ]

    def clean(self):
        a = self.afectacion
        if a.inscripcion.grupo.nivel_id != a.progresion.nivel_origen_id:
            raise ValidationError('La excepción solo permite permanencia en el nivel de origen.')
        periodo = a.inscripcion.grupo.periodo
        if not periodo.fecha_inicio <= self.fecha_inicio <= self.fecha_limite <= periodo.fecha_fin:
            raise ValidationError('La excepción debe estar limitada al periodo de la inscripción.')

    @property
    def situacion(self):
        if self.estado == 'revocada':
            return 'revocada'
        hoy = timezone.localdate()
        return 'programada' if hoy < self.fecha_inicio else 'vencida' if hoy > self.fecha_limite else 'vigente'


class EventoProgresion(models.Model):
    progresion = models.ForeignKey(ProgresionInstitucional, on_delete=models.PROTECT, related_name='eventos')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    registrado_en = models.DateTimeField(auto_now_add=True)
    tipo = models.CharField(max_length=32)
    version = models.PositiveIntegerField()
    motivo = models.CharField(max_length=500)
    datos = models.JSONField(default=dict)

    class Meta:
        ordering = ['id']

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('El historial de progresión no se puede modificar.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('El historial de progresión no se puede eliminar.')
