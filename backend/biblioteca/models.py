from django.db import models
from django.db.models import Q, F
from recursos.models import Identidad, Edicion, Evento


class TerminoActividad(models.Model):
    namespace = models.CharField(max_length=40, choices=[(x, x) for x in ('capacidad', 'estilo', 'movimiento', 'geometria', 'implemento', 'instalacion', 'exigencia_funcional')])
    codigo = models.SlugField(max_length=80)
    nombre = models.CharField(max_length=120)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['namespace', 'codigo'], name='termino_namespace_unico')]


class Ejercicio(Identidad):
    pass


class EjercicioVersion(Edicion):
    identidad = models.ForeignKey(Ejercicio, on_delete=models.PROTECT, related_name='versiones')
    disciplina = models.ForeignKey('organizacion.Disciplina', on_delete=models.PROTECT)
    programas = models.ManyToManyField('curriculo.ProgramaFormativo', blank=True)
    etiquetas = models.ManyToManyField(TerminoActividad, blank=True)
    nombre = models.CharField(max_length=200)
    objetivo = models.TextField()
    poblacion = models.TextField()
    metodologia = models.TextField()
    descripcion = models.TextField()
    organizacion = models.TextField(blank=True)
    prerrequisitos = models.TextField(blank=True)
    riesgos = models.TextField()
    controles = models.TextField()
    edad_min = models.PositiveSmallIntegerField(null=True, blank=True)
    edad_max = models.PositiveSmallIntegerField(null=True, blank=True)
    duracion_min = models.PositiveSmallIntegerField(null=True, blank=True)
    duracion_max = models.PositiveSmallIntegerField(null=True, blank=True)
    acceso_tecnico = models.BooleanField(default=False)
    exigencias_conocidas = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['identidad', 'numero'], name='ejercicio_numero_unico'), models.UniqueConstraint(fields=['identidad'], condition=Q(vigente=True), name='ejercicio_vigente_unico'), models.CheckConstraint(condition=Q(vigente=False) | Q(estado='aprobado'), name='ejercicio_vigente_aprobado'), models.CheckConstraint(condition=Q(edad_min__isnull=True) | Q(edad_max__isnull=True) | Q(edad_min__lte=F('edad_max')), name='ejercicio_edades_coherentes'), models.CheckConstraint(condition=Q(duracion_min__isnull=True) | Q(duracion_max__isnull=True) | Q(duracion_min__lte=F('duracion_max')), name='ejercicio_duracion_coherente')]


class PasoEjercicio(models.Model):
    version = models.ForeignKey(EjercicioVersion, on_delete=models.PROTECT, related_name='pasos')
    orden = models.PositiveSmallIntegerField()
    instrucciones = models.TextField()

    class Meta:
        ordering = ['orden']
        constraints = [models.UniqueConstraint(fields=['version', 'orden'], name='paso_orden_unico'), models.CheckConstraint(condition=Q(orden__gte=1), name='paso_positivo')]


class AdaptacionEjercicio(models.Model):
    version = models.ForeignKey(EjercicioVersion, on_delete=models.PROTECT, related_name='adaptaciones')
    condicion = models.TextField()
    alternativa = models.TextField()
    limites = models.TextField()


class ExigenciaEjercicio(models.Model):
    version = models.ForeignKey(EjercicioVersion, on_delete=models.PROTECT, related_name='exigencias')
    termino = models.ForeignKey(TerminoActividad, on_delete=models.PROTECT)
    descripcion = models.TextField()
    estado_dato = models.CharField(max_length=20, choices=[(x, x) for x in ('conocido', 'desconocido', 'requiere_revision')], default='requiere_revision')


class ProcedenciaEjercicio(models.Model):
    version = models.ForeignKey(EjercicioVersion, on_delete=models.PROTECT, related_name='procedencias')
    fragmento = models.ForeignKey('recursos.FragmentoFuente', on_delete=models.PROTECT)
    adaptacion = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['version', 'fragmento'], name='ejercicio_fuente_unica')]


class MaterialDocente(Identidad):
    pass


class MaterialDocenteVersion(Edicion):
    identidad = models.ForeignKey(MaterialDocente, on_delete=models.PROTECT, related_name='versiones')
    titulo = models.CharField(max_length=200)
    resumen = models.TextField()
    archivo = models.ForeignKey('recursos.ArchivoPrivado', on_delete=models.PROTECT, null=True, blank=True)
    referencia_externa = models.URLField(blank=True)
    programas = models.ManyToManyField('curriculo.ProgramaFormativo', blank=True)
    acceso_tecnico = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['identidad', 'numero'], name='material_numero_unico'), models.UniqueConstraint(fields=['identidad'], condition=Q(vigente=True), name='material_vigente_unico'), models.CheckConstraint(condition=Q(vigente=False) | Q(estado='aprobado'), name='material_vigente_aprobado'), models.CheckConstraint(condition=(Q(archivo__isnull=False, referencia_externa='') | (Q(archivo__isnull=True) & ~Q(referencia_externa=''))), name='material_un_soporte')]


class MaterialEjercicio(models.Model):
    version = models.ForeignKey(EjercicioVersion, on_delete=models.PROTECT, related_name='materiales')
    material = models.ForeignKey(MaterialDocenteVersion, on_delete=models.PROTECT)
    finalidad = models.CharField(max_length=200)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['version', 'material'], name='material_ejercicio_unico')]


class CandidatoBiblioteca(models.Model):
    fragmento = models.OneToOneField('recursos.FragmentoFuente', on_delete=models.PROTECT)
    titulo = models.CharField(max_length=240)
    naturaleza = models.CharField(max_length=60, default='candidato_sin_validar')
    observaciones = models.TextField(blank=True)
    # No FK de publicación ni conversión automática a ejercicio.


class EventoEjercicio(Evento):
    version = models.ForeignKey(EjercicioVersion, on_delete=models.PROTECT, related_name='eventos')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['actor', 'clave'], name='evento_ejercicio_clave_unica')]


class EventoMaterial(Evento):
    version = models.ForeignKey(MaterialDocenteVersion, on_delete=models.PROTECT, related_name='eventos')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['actor', 'clave'], name='evento_material_clave_unica')]


from .modelos_funcionales import (PerfilFuncional, PerfilFuncionalVersion,
    ExigenciaPerfilFuncional, CondicionPerfilFuncional, AdaptacionPerfilFuncional,
    ProcedenciaPerfilFuncional, EventoPerfilFuncional, CorrespondenciaFuncional,
    CorrespondenciaFuncionalVersion, EventoCorrespondenciaFuncional)  # noqa: E402,F401
