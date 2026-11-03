import uuid as uuidlib
from django.conf import settings
from django.db import models
from django.db.models import Q, F
from recursos.models import Identidad, Edicion, Evento


class ProgramaFormativo(models.Model):
    uuid = models.UUIDField(default=uuidlib.uuid4, unique=True, editable=False)
    nivel = models.OneToOneField('organizacion.Nivel', on_delete=models.PROTECT)
    modalidad = models.CharField(max_length=20, choices=[(x, x) for x in ('curricular', 'mixta', 'individual')], default='curricular')
    formalizado = models.BooleanField(default=False)


class Malla(Identidad):
    programa = models.ForeignKey(ProgramaFormativo, on_delete=models.PROTECT)


class MallaVersion(Edicion):
    original_cerrado = models.BooleanField(default=False)
    identidad = models.ForeignKey(Malla, on_delete=models.PROTECT, related_name='versiones')
    semanas_esperadas = models.PositiveSmallIntegerField(null=True, blank=True)
    clases_esperadas = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['identidad', 'numero'], name='malla_numero_unico'), models.UniqueConstraint(fields=['identidad'], condition=Q(vigente=True), name='malla_vigente_unica'), models.CheckConstraint(condition=Q(vigente=False) | Q(estado='aprobado'), name='malla_vigente_aprobada')]


class FaseCurricular(models.Model):
    uuid = models.UUIDField(default=uuidlib.uuid4, unique=True, editable=False)
    version = models.ForeignKey(MallaVersion, on_delete=models.PROTECT, related_name='fases')
    clave_logica = models.UUIDField(default=uuidlib.uuid4)
    codigo = models.SlugField(max_length=40)
    nombre = models.CharField(max_length=160)
    fuente = models.ForeignKey('recursos.FragmentoFuente', on_delete=models.PROTECT, null=True)
    orden = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ['orden']
        constraints = [models.UniqueConstraint(fields=['version', 'orden'], name='fase_orden_unico'), models.UniqueConstraint(fields=['version', 'clave_logica'], name='fase_logica_unica'), models.CheckConstraint(condition=Q(orden__gte=1), name='fase_orden_positivo')]


class SemanaCurricular(models.Model):
    uuid = models.UUIDField(default=uuidlib.uuid4, unique=True, editable=False)
    version = models.ForeignKey(MallaVersion, on_delete=models.PROTECT, related_name='semanas')
    fase = models.ForeignKey(FaseCurricular, on_delete=models.PROTECT, related_name='semanas')
    clave_logica = models.UUIDField(default=uuidlib.uuid4)
    ordinal = models.PositiveSmallIntegerField()
    fuente = models.ForeignKey('recursos.FragmentoFuente', on_delete=models.PROTECT, null=True)

    class Meta:
        ordering = ['ordinal']
        constraints = [models.UniqueConstraint(fields=['version', 'ordinal'], name='semana_ordinal_unica'), models.CheckConstraint(condition=Q(ordinal__gte=1), name='semana_positiva')]


class ClasePrevista(models.Model):
    uuid = models.UUIDField(default=uuidlib.uuid4, unique=True, editable=False)
    semana = models.ForeignKey(SemanaCurricular, on_delete=models.PROTECT, related_name='clases')
    clave_logica = models.UUIDField(default=uuidlib.uuid4)
    ordinal = models.PositiveSmallIntegerField()
    fuente = models.ForeignKey('recursos.FragmentoFuente', on_delete=models.PROTECT, null=True)

    class Meta:
        ordering = ['ordinal']
        constraints = [models.UniqueConstraint(fields=['semana', 'ordinal'], name='clase_semana_ordinal_unica'), models.CheckConstraint(condition=Q(ordinal__gte=1), name='clase_positiva')]


class ElementoCurricular(models.Model):
    TIPOS = [(x, x) for x in ('competencia', 'objetivo', 'contenido', 'desempeno')]
    uuid = models.UUIDField(default=uuidlib.uuid4, unique=True, editable=False)
    version = models.ForeignKey(MallaVersion, on_delete=models.PROTECT, related_name='elementos')
    clave_logica = models.UUIDField(default=uuidlib.uuid4)
    tipo = models.CharField(max_length=20, choices=TIPOS)
    texto = models.TextField()
    dimension = models.CharField(max_length=40, blank=True)
    subdimension = models.CharField(max_length=40, blank=True)
    padre = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True)
    instrumento_propuesto = models.TextField(blank=True)
    fase = models.ForeignKey(FaseCurricular, on_delete=models.PROTECT, null=True, blank=True)
    semana = models.ForeignKey(SemanaCurricular, on_delete=models.PROTECT, null=True, blank=True)
    clase = models.ForeignKey(ClasePrevista, on_delete=models.PROTECT, null=True, blank=True, related_name='elementos')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['version', 'clave_logica'], name='elemento_logico_unico'), models.CheckConstraint(condition=Q(tipo__in=['competencia', 'objetivo', 'contenido', 'desempeno']), name='elemento_tipo_valido'), models.CheckConstraint(condition=(Q(fase__isnull=True, semana__isnull=True) | Q(fase__isnull=True, clase__isnull=True) | Q(semana__isnull=True, clase__isnull=True)), name='elemento_un_ambito')]


class ProcedenciaCurricular(models.Model):
    elemento = models.ForeignKey(ElementoCurricular, on_delete=models.PROTECT, related_name='procedencias')
    fragmento = models.ForeignKey('recursos.FragmentoFuente', on_delete=models.PROTECT)
    transformacion = models.CharField(max_length=20, default='copia')
    observacion = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['elemento', 'fragmento'], name='procedencia_elemento_unica')]


class UbicacionCurricular(models.Model):
    elemento = models.ForeignKey(ElementoCurricular, on_delete=models.PROTECT, related_name='ubicaciones')
    fase = models.ForeignKey(FaseCurricular, on_delete=models.PROTECT, null=True, blank=True)
    semana = models.ForeignKey(SemanaCurricular, on_delete=models.PROTECT, null=True, blank=True)
    clase = models.ForeignKey(ClasePrevista, on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=(Q(fase__isnull=True, semana__isnull=True) | Q(fase__isnull=True, clase__isnull=True) | Q(semana__isnull=True, clase__isnull=True)), name='ubicacion_un_ambito'), models.UniqueConstraint(fields=['elemento','fase'], condition=Q(fase__isnull=False), name='ubicacion_fase_unica'), models.UniqueConstraint(fields=['elemento','semana'], condition=Q(semana__isnull=False), name='ubicacion_semana_unica'), models.UniqueConstraint(fields=['elemento','clase'], condition=Q(clase__isnull=False), name='ubicacion_clase_unica'), models.UniqueConstraint(fields=['elemento'], condition=Q(fase__isnull=True,semana__isnull=True,clase__isnull=True), name='ubicacion_malla_unica')]


class LoteImportacion(models.Model):
    uuid = models.UUIDField(default=uuidlib.uuid4, unique=True, editable=False)
    fuente = models.ForeignKey('recursos.FuenteVersion', on_delete=models.PROTECT)
    perfil = models.CharField(max_length=60, default='mallas-zdb-v1')
    clave = models.UUIDField()
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    estado = models.CharField(max_length=20, default='extraido')
    vista_previa = models.JSONField(default=dict)
    resultado = models.JSONField(default=list)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['autor', 'clave'], name='importacion_clave_unica'), models.UniqueConstraint(fields=['fuente', 'perfil'], name='importacion_fuente_perfil_unica')]


class EventoMalla(Evento):
    version = models.ForeignKey(MallaVersion, on_delete=models.PROTECT, related_name='eventos')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['actor', 'clave'], name='evento_malla_clave_unica')]


class ActividadCurricular(models.Model):
    elemento = models.ForeignKey(ElementoCurricular, on_delete=models.PROTECT)
    ejercicio_version = models.ForeignKey('biblioteca.EjercicioVersion', on_delete=models.PROTECT)
    finalidad = models.CharField(max_length=200)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['elemento', 'ejercicio_version'], name='actividad_curricular_unica')]
