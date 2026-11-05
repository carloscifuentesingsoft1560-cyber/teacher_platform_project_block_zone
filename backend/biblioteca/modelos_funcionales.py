"""B2.2: catálogo propuesto, sin aprobación institucional ni autorización personal."""
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class HistorialFuncional(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('El catálogo funcional es inmutable.')

    def delete(self):
        raise ValidationError('El catálogo funcional no se elimina.')

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError('El catálogo funcional es inmutable.')


class RegistroFuncional(models.Model):
    objects = HistorialFuncional.as_manager()

    class Meta:
        abstract = True
        default_permissions = ('view',)

    def save(self, *args, **kwargs):
        if not self._state.adding or self.pk is not None:
            raise ValidationError('El catálogo funcional es inmutable.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('El catálogo funcional no se elimina.')


class PerfilFuncional(RegistroFuncional):
    identificador = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    disciplina = models.ForeignKey('organizacion.Disciplina', on_delete=models.PROTECT)
    creada_en = models.DateTimeField(auto_now_add=True)


class VersionFuncional(RegistroFuncional):
    numero = models.PositiveIntegerField()
    anterior = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='siguiente')
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta(RegistroFuncional.Meta):
        abstract = True
        constraints = [models.CheckConstraint(condition=Q(numero=1, anterior__isnull=True) | Q(numero__gt=1, anterior__isnull=False), name='%(class)s_origen')]


class PerfilFuncionalVersion(VersionFuncional):
    perfil = models.ForeignKey(PerfilFuncional, on_delete=models.PROTECT, related_name='versiones')
    nombre = models.CharField(max_length=200)
    alcance = models.TextField()

    class Meta(VersionFuncional.Meta):
        constraints = VersionFuncional.Meta.constraints + [
            models.UniqueConstraint(fields=['perfil', 'numero'], name='pf_version_numero'),
            models.CheckConstraint(condition=Q(nombre__regex=r'\S', alcance__regex=r'\S'), name='pf_version_contenido')]


class ExigenciaPerfilFuncional(RegistroFuncional):
    version = models.ForeignKey(PerfilFuncionalVersion, on_delete=models.PROTECT, related_name='exigencias')
    termino = models.ForeignKey('biblioteca.TerminoActividad', on_delete=models.PROTECT)
    codigo_historico = models.CharField(max_length=80)
    nombre_historico = models.CharField(max_length=120)
    significado = models.TextField()
    estado_dato = models.CharField(max_length=20, choices=[(x, x) for x in ('conocido', 'desconocido', 'requiere_revision')])
    tipo = models.CharField(max_length=12, choices=[(x, x) for x in ('numero', 'booleano', 'texto', 'desconocido')])
    operador = models.CharField(max_length=8, choices=[(x, x) for x in ('eq', 'lte', 'gte', 'sin_dato')])
    valor_numero = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    valor_booleano = models.BooleanField(null=True, blank=True)
    valor_texto = models.CharField(max_length=240, blank=True)
    unidad_propuesta = models.CharField(max_length=40, blank=True)

    class Meta(RegistroFuncional.Meta):
        constraints = [models.UniqueConstraint(fields=['version', 'termino'], name='pf_exigencia_termino'),
            models.CheckConstraint(condition=Q(significado__regex=r'\S'), name='pf_exigencia_significado'),
            models.CheckConstraint(condition=Q(estado_dato__in=['conocido', 'desconocido', 'requiere_revision']), name='pf_exigencia_estado'),
            models.CheckConstraint(condition=(
                Q(estado_dato__in=['desconocido', 'requiere_revision'], tipo='desconocido', operador='sin_dato', valor_numero__isnull=True, valor_booleano__isnull=True, valor_texto='', unidad_propuesta='') |
                (Q(estado_dato='conocido') & (
                    Q(tipo='numero', operador__in=['eq', 'lte', 'gte'], valor_numero__isnull=False, valor_booleano__isnull=True, valor_texto='', unidad_propuesta__regex=r'\S') |
                    Q(tipo='booleano', operador='eq', valor_numero__isnull=True, valor_booleano__isnull=False, valor_texto='', unidad_propuesta='') |
                    Q(tipo='texto', operador='eq', valor_numero__isnull=True, valor_booleano__isnull=True, valor_texto__regex=r'\S', unidad_propuesta='')))), name='pf_exigencia_tipo_valor')]


class CondicionPerfilFuncional(RegistroFuncional):
    version = models.ForeignKey(PerfilFuncionalVersion, on_delete=models.PROTECT, related_name='condiciones')
    exigencia = models.ForeignKey(ExigenciaPerfilFuncional, on_delete=models.PROTECT)
    descripcion = models.TextField()
    metodo_verificacion = models.TextField()

    class Meta(RegistroFuncional.Meta):
        constraints = [models.CheckConstraint(condition=Q(descripcion__regex=r'\S', metodo_verificacion__regex=r'\S'), name='pf_condicion_contenido')]


class AdaptacionPerfilFuncional(RegistroFuncional):
    version = models.ForeignKey(PerfilFuncionalVersion, on_delete=models.PROTECT, related_name='adaptaciones')
    condicion = models.ForeignKey(CondicionPerfilFuncional, on_delete=models.PROTECT)
    alternativa = models.TextField()
    limites = models.TextField()

    class Meta(RegistroFuncional.Meta):
        constraints = [models.CheckConstraint(condition=Q(alternativa__regex=r'\S', limites__regex=r'\S'), name='pf_adaptacion_contenido')]


class ProcedenciaPerfilFuncional(RegistroFuncional):
    version = models.ForeignKey(PerfilFuncionalVersion, on_delete=models.PROTECT, related_name='procedencias')
    fragmento = models.ForeignKey('recursos.FragmentoFuente', on_delete=models.PROTECT)
    justificacion = models.TextField()

    class Meta(RegistroFuncional.Meta):
        constraints = [models.UniqueConstraint(fields=['version', 'fragmento'], name='pf_procedencia_unica'),
            models.CheckConstraint(condition=Q(justificacion__regex=r'\S'), name='pf_procedencia_contenido')]


class CorrespondenciaFuncional(RegistroFuncional):
    identificador = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    ejercicio = models.ForeignKey('biblioteca.EjercicioVersion', null=True, blank=True, on_delete=models.PROTECT)
    tarea = models.ForeignKey('sesiones.TareaSesion', null=True, blank=True, on_delete=models.PROTECT)
    actividad = models.ForeignKey('sesiones.ActividadEjecutada', null=True, blank=True, on_delete=models.PROTECT)

    class Meta(RegistroFuncional.Meta):
        constraints = [models.CheckConstraint(condition=(
            Q(ejercicio__isnull=False, tarea__isnull=True, actividad__isnull=True) |
            Q(ejercicio__isnull=True, tarea__isnull=False, actividad__isnull=True) |
            Q(ejercicio__isnull=True, tarea__isnull=True, actividad__isnull=False)), name='pf_correspondencia_destino'),
            models.UniqueConstraint(fields=['ejercicio'], condition=Q(ejercicio__isnull=False), name='pf_destino_ejercicio'),
            models.UniqueConstraint(fields=['tarea'], condition=Q(tarea__isnull=False), name='pf_destino_tarea'),
            models.UniqueConstraint(fields=['actividad'], condition=Q(actividad__isnull=False), name='pf_destino_actividad')]


class CorrespondenciaFuncionalVersion(VersionFuncional):
    correspondencia = models.ForeignKey(CorrespondenciaFuncional, on_delete=models.PROTECT, related_name='versiones')
    perfil_version = models.ForeignKey(PerfilFuncionalVersion, on_delete=models.PROTECT)
    evento_perfil = models.ForeignKey('EventoPerfilFuncional', on_delete=models.PROTECT)
    contexto = models.JSONField()
    justificacion = models.TextField()
    adaptacion = models.ForeignKey(AdaptacionPerfilFuncional, null=True, blank=True, on_delete=models.PROTECT)

    class Meta(VersionFuncional.Meta):
        constraints = VersionFuncional.Meta.constraints + [
            models.UniqueConstraint(fields=['correspondencia', 'numero'], name='pf_correspondencia_numero'),
            models.CheckConstraint(condition=Q(justificacion__regex=r'\S'), name='pf_correspondencia_motivo')]


class EventoFuncional(RegistroFuncional):
    numero = models.PositiveIntegerField()
    anterior = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='siguiente')
    accion = models.CharField(max_length=12, choices=[(x, x) for x in ('propuesta', 'revision', 'retiro')])
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    persona_actor = models.ForeignKey('cuentas.Persona', on_delete=models.PROTECT, related_name='+')
    enlace_actor = models.ForeignKey('cuentas.EnlaceIdentidad', on_delete=models.PROTECT, related_name='+')
    version_enlace_actor = models.PositiveIntegerField()
    evidencia_actor = models.UUIDField()
    clave = models.UUIDField()
    solicitud = models.JSONField()
    motivo = models.CharField(max_length=500)
    registrada_en = models.DateTimeField(auto_now_add=True)

    class Meta(RegistroFuncional.Meta):
        abstract = True
        constraints = [
            models.UniqueConstraint(fields=['actor', 'clave'], name='%(class)s_clave'),
            models.CheckConstraint(condition=Q(motivo__regex=r'\S', version_enlace_actor__gte=1), name='%(class)s_datos'),
            models.CheckConstraint(condition=Q(numero=1, accion='propuesta', anterior__isnull=True) | Q(numero__gt=1, accion__in=['revision', 'retiro'], anterior__isnull=False), name='%(class)s_cadena')]


class EventoPerfilFuncional(EventoFuncional):
    version = models.ForeignKey(PerfilFuncionalVersion, on_delete=models.PROTECT, related_name='eventos')

    class Meta(EventoFuncional.Meta):
        constraints = EventoFuncional.Meta.constraints + [models.UniqueConstraint(fields=['version', 'numero'], name='pf_evento_numero')]


class EventoCorrespondenciaFuncional(EventoFuncional):
    version = models.ForeignKey(CorrespondenciaFuncionalVersion, on_delete=models.PROTECT, related_name='eventos')

    class Meta(EventoFuncional.Meta):
        constraints = EventoFuncional.Meta.constraints + [models.UniqueConstraint(fields=['version', 'numero'], name='cf_evento_numero')]
