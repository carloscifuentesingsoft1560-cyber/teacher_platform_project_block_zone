"""Persistencia de Etapa 4. Las escrituras de dominio pasan por servicios."""
import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q, F
from deportistas.models import Registro


class Sesion(Registro):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    grupo = models.ForeignKey('organizacion.Grupo', on_delete=models.PROTECT)
    profesor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='sesiones_docentes')
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    estado = models.CharField(max_length=16, default='planificada', choices=[(x, x) for x in ('planificada', 'realizada', 'cancelada')])
    asistencia_confirmada = models.BooleanField(default=False)
    plan_ejecutado = models.ForeignKey('PlanSesion', null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    inicio_real = models.DateTimeField(null=True, blank=True)
    fin_real = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(hora_fin__gt=F('hora_inicio')), name='sesion_horas_validas'),
            models.CheckConstraint(condition=Q(estado__in=['planificada', 'realizada', 'cancelada']), name='sesion_estado_valido'),
            models.CheckConstraint(condition=Q(asistencia_confirmada=False) | ~Q(estado='cancelada'), name='sesion_asistencia_no_cancelada'),
            models.CheckConstraint(condition=Q(inicio_real__isnull=True, fin_real__isnull=True, estado__in=['planificada', 'cancelada']) | Q(estado='realizada', inicio_real__isnull=False, fin_real__gt=F('inicio_real')), name='sesion_ejecucion_coherente'),
            models.UniqueConstraint(fields=['grupo', 'fecha', 'hora_inicio'], condition=~Q(estado='cancelada'), name='sesion_grupo_franja_unica'),
        ]
        indexes = [models.Index(fields=['profesor', 'fecha'], name='sesion_profesor_dia')]


class PlanSesion(models.Model):
    sesion = models.ForeignKey(Sesion, on_delete=models.PROTECT, related_name='planes')
    numero = models.PositiveIntegerField()
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado_en = models.DateTimeField(auto_now_add=True)
    objetivo = models.TextField()
    malla_version = models.ForeignKey('curriculo.MallaVersion', null=True, blank=True, on_delete=models.PROTECT)
    clase = models.ForeignKey('curriculo.ClasePrevista', null=True, blank=True, on_delete=models.PROTECT)
    programa = models.ForeignKey('curriculo.ProgramaFormativo', null=True, blank=True, on_delete=models.PROTECT)
    fase_curricular = models.ForeignKey('curriculo.FaseCurricular', null=True, blank=True, on_delete=models.PROTECT)
    semana = models.ForeignKey('curriculo.SemanaCurricular', null=True, blank=True, on_delete=models.PROTECT)
    competencias = models.ManyToManyField('curriculo.ElementoCurricular', through='CompetenciaPlan', blank=True)
    revision_anterior = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='revisiones')
    sellado = models.BooleanField(default=False, editable=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['sesion', 'numero'], name='plan_sesion_numero_unico'), models.CheckConstraint(condition=Q(numero__gte=1), name='plan_numero_positivo')]


class TareaSesion(models.Model):
    plan = models.ForeignKey(PlanSesion, on_delete=models.PROTECT, related_name='tareas')
    orden = models.PositiveSmallIntegerField()
    fase = models.CharField(max_length=10, choices=[(x, x) for x in ('inicial', 'central', 'final')])
    minutos = models.PositiveSmallIntegerField()
    instrucciones = models.TextField()
    objetivo = models.TextField(blank=True)
    ejercicio_version = models.ForeignKey('biblioteca.EjercicioVersion', null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        ordering = ['orden']
        constraints = [models.UniqueConstraint(fields=['plan', 'orden'], name='tarea_plan_orden_unico'), models.CheckConstraint(condition=Q(orden__gte=1, minutos__gte=1), name='tarea_orden_minutos_positivos'), models.CheckConstraint(condition=Q(fase__in=['inicial', 'central', 'final']), name='tarea_fase_valida')]


class CompetenciaPlan(models.Model):
    plan = models.ForeignKey(PlanSesion, on_delete=models.PROTECT)
    competencia = models.ForeignKey('curriculo.ElementoCurricular', on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['plan', 'competencia'], name='plan_competencia_unica')]


class Asistencia(models.Model):
    sesion = models.ForeignKey(Sesion, on_delete=models.PROTECT, related_name='asistencias')
    inscripcion = models.ForeignKey('inscripciones.Inscripcion', on_delete=models.PROTECT)
    deportista = models.ForeignKey('deportistas.Deportista', on_delete=models.PROTECT)
    # Vacío significa sin registrar; nunca se interpreta como ausencia.
    estado = models.CharField(max_length=12, blank=True, default='', choices=[(x, x) for x in ('', 'asistio', 'no_asistio', 'tarde', 'excusa', 'retiro')])

    class Meta:
        constraints = [models.UniqueConstraint(fields=['sesion', 'inscripcion'], name='asistencia_sesion_inscripcion'), models.UniqueConstraint(fields=['sesion', 'deportista'], name='asistencia_sesion_persona_unica'), models.CheckConstraint(condition=Q(estado__in=['', 'asistio', 'no_asistio', 'tarde', 'excusa', 'retiro']), name='asistencia_estado_valido')]


class EjecucionSesion(models.Model):
    sesion = models.OneToOneField(Sesion, on_delete=models.PROTECT, related_name='ejecucion')
    plan = models.ForeignKey(PlanSesion, on_delete=models.PROTECT)
    inicio = models.DateTimeField()
    fin = models.DateTimeField()
    observaciones = models.TextField(blank=True)
    incidencias_pedagogicas = models.TextField(blank=True)
    creada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    creada_en = models.DateTimeField(auto_now_add=True)
    finalizada_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    finalizada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(fin__gt=F('inicio')), name='ejecucion_intervalo_valido'), models.CheckConstraint(condition=Q(finalizada_en__isnull=True, finalizada_por__isnull=True) | Q(finalizada_en__isnull=False, finalizada_por__isnull=False), name='ejecucion_cierre_coherente')]


class ActividadEjecutada(models.Model):
    ejecucion = models.ForeignKey(EjecucionSesion, on_delete=models.PROTECT, related_name='actividades')
    tarea = models.ForeignKey(TareaSesion, on_delete=models.PROTECT)
    resultado = models.CharField(max_length=12, choices=[(x,x) for x in ('realizada', 'modificada', 'omitida')])
    minutos = models.PositiveSmallIntegerField()
    descripcion = models.TextField(blank=True)
    adaptacion_metodologica = models.TextField(blank=True)
    motivo_omision = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['ejecucion', 'tarea'], name='ejecucion_tarea_unica'), models.CheckConstraint(condition=Q(resultado='omitida', minutos=0) | Q(resultado__in=['realizada', 'modificada'], minutos__gte=1), name='actividad_real_resultado_valido')]


class CorreccionAsistencia(models.Model):
    asistencia = models.ForeignKey(Asistencia, on_delete=models.PROTECT, related_name='correcciones')
    anterior = models.CharField(max_length=12)
    nuevo = models.CharField(max_length=12)
    motivo = models.CharField(max_length=500)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    registrada_en = models.DateTimeField(auto_now_add=True)
    evento = models.OneToOneField('EventoSesion', on_delete=models.PROTECT)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(anterior__in=['asistio', 'no_asistio', 'tarde', 'excusa', 'retiro']) & Q(nuevo__in=['asistio', 'no_asistio', 'tarde', 'excusa', 'retiro']) & ~Q(anterior=F('nuevo')), name='correccion_asistencia_valores')]


class EventoSesion(models.Model):
    sesion = models.ForeignKey(Sesion, on_delete=models.PROTECT, related_name='eventos')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    clave = models.UUIDField()
    operacion = models.CharField(max_length=32)
    solicitud = models.JSONField()
    registrado_en = models.DateTimeField(auto_now_add=True)
    version = models.PositiveIntegerField()
    detalle = models.JSONField(default=dict)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['actor', 'clave'], name='evento_sesion_actor_clave')]

class SeguimientoPedagogico(models.Model):
    sesion = models.ForeignKey(Sesion, on_delete=models.PROTECT, related_name='seguimientos')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    registrado_en = models.DateTimeField(auto_now_add=True)
    comentario = models.TextField()
    recomendaciones = models.TextField(blank=True)
    anterior = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='siguiente')
    evento = models.OneToOneField(EventoSesion, on_delete=models.PROTECT)

    class Meta:
        ordering = ['pk']
