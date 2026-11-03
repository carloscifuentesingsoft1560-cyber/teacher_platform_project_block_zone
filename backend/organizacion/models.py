from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Q, F

class Disciplina(models.Model):
    codigo = models.SlugField(max_length=40, unique=True)
    nombre = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre", "id"]

    def __str__(self):
        return self.nombre

class Nivel(models.Model):
    disciplina = models.ForeignKey(Disciplina, on_delete=models.PROTECT, related_name="niveles")
    codigo = models.SlugField(max_length=40)
    nombre = models.CharField(max_length=140)
    orden = models.PositiveSmallIntegerField(default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["orden", "nombre", "id"]
        constraints = [models.UniqueConstraint(fields=["disciplina", "codigo"], name="nivel_codigo_por_disciplina")]

    def __str__(self):
        return self.nombre

class Periodo(models.Model):
    codigo = models.SlugField(max_length=40, unique=True)
    nombre = models.CharField(max_length=100)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["-fecha_inicio", "id"]
        constraints = [models.CheckConstraint(condition=Q(fecha_fin__gte=F("fecha_inicio")), name="periodo_fechas_ordenadas")]

class Grupo(models.Model):
    codigo = models.SlugField(max_length=40, unique=True)
    nombre = models.CharField(max_length=120)
    disciplina = models.ForeignKey(Disciplina, on_delete=models.PROTECT, related_name="grupos")
    nivel = models.ForeignKey(Nivel, on_delete=models.PROTECT, related_name="grupos")
    periodo = models.ForeignKey(Periodo, on_delete=models.PROTECT, related_name="grupos")
    activo = models.BooleanField(default=True)
    cupo_maximo = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        ordering = ["nombre", "id"]
        constraints = [models.CheckConstraint(condition=Q(cupo_maximo__gte=1), name="grupo_cupo_positivo")]

class Horario(models.Model):
    grupo = models.ForeignKey(Grupo, on_delete=models.PROTECT, related_name="horarios")
    dia = models.PositiveSmallIntegerField(validators=[MaxValueValidator(6)])
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["dia", "hora_inicio", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(dia__lte=6), name="horario_dia_valido"),
            models.CheckConstraint(condition=Q(hora_fin__gt=F("hora_inicio")), name="horario_horas_ordenadas"),
            models.UniqueConstraint(fields=["grupo", "dia", "hora_inicio"], condition=Q(activo=True), name="horario_activo_unico"),
        ]

    @property
    def duracion_minutos(self):
        return (self.hora_fin.hour * 60 + self.hora_fin.minute) - (self.hora_inicio.hour * 60 + self.hora_inicio.minute)

class Asignacion(models.Model):
    class Tipo(models.TextChoices):
        PROFESOR = "profesor", "Profesor"
        COORDINADOR = "coordinador", "Coordinador"

    grupo = models.ForeignKey(Grupo, on_delete=models.PROTECT, related_name="asignaciones")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="asignaciones")
    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_inicio", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=F("fecha_inicio")), name="asignacion_fechas_ordenadas"),
            models.CheckConstraint(condition=Q(tipo__in=["profesor", "coordinador"]), name="asignacion_tipo_valido"),
            models.UniqueConstraint(fields=["grupo", "usuario", "tipo", "fecha_inicio"], name="asignacion_inicio_unico"),
        ]
