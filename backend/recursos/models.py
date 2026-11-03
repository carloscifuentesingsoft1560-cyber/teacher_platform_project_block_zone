import uuid as uuidlib
from django.conf import settings
from django.db import models
from django.db.models import Q


class Identidad(models.Model):
    uuid = models.UUIDField(default=uuidlib.uuid4, unique=True, editable=False)
    codigo = models.SlugField(max_length=80, unique=True)
    nombre = models.CharField(max_length=200)
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class Edicion(models.Model):
    NATURALEZAS = [(x, x) for x in ('original_institucional', 'propuesta_revisada', 'adaptacion_docente')]
    ESTADOS = [(x, x) for x in ('borrador', 'en_revision', 'aprobado', 'retirado')]
    uuid = models.UUIDField(default=uuidlib.uuid4, unique=True, editable=False)
    numero = models.PositiveIntegerField(default=1)
    revision = models.PositiveIntegerField(default=1)
    naturaleza = models.CharField(max_length=30, choices=NATURALEZAS, default='propuesta_revisada')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='borrador')
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    creada_en = models.DateTimeField(auto_now_add=True)
    revisor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name='+')
    revisada_en = models.DateTimeField(null=True)
    vigente = models.BooleanField(default=False)
    derivada_de = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True)
    clave_derivacion = models.UUIDField(null=True, unique=True, editable=False)
    derechos = models.TextField(blank=True)
    observaciones_revision = models.TextField(blank=True)

    class Meta:
        abstract = True


class Evento(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    accion = models.CharField(max_length=30)
    clave = models.UUIDField(default=uuidlib.uuid4)
    huella = models.CharField(max_length=64)
    fecha = models.DateTimeField(auto_now_add=True)
    motivo = models.CharField(max_length=500, blank=True)
    revision_resultante = models.PositiveIntegerField()

    class Meta:
        abstract = True


class ArchivoPrivado(models.Model):
    uuid = models.UUIDField(default=uuidlib.uuid4, unique=True, editable=False)
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    nombre = models.CharField(max_length=200)
    clave = models.UUIDField(default=uuidlib.uuid4, unique=True, editable=False)
    sha256 = models.CharField(max_length=64)
    bytes = models.PositiveIntegerField()
    tipo = models.CharField(max_length=100)
    finalidad = models.CharField(max_length=40, default='material_docente')
    creada_en = models.DateTimeField(auto_now_add=True)


class FuenteDocumento(models.Model):
    uuid = models.UUIDField(default=uuidlib.uuid4, unique=True, editable=False)
    titulo = models.CharField(max_length=240)
    referencia = models.TextField(blank=True)
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class FuenteVersion(models.Model):
    uuid = models.UUIDField(default=uuidlib.uuid4, unique=True, editable=False)
    fuente = models.ForeignKey(FuenteDocumento, on_delete=models.PROTECT, related_name='versiones')
    numero = models.PositiveIntegerField(default=1)
    archivo = models.ForeignKey(ArchivoPrivado, on_delete=models.PROTECT, null=True)
    referencia_externa = models.URLField(blank=True)
    licencia = models.TextField()
    sha256 = models.CharField(max_length=64, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['fuente', 'numero'], name='fuente_edicion_unica'),
            models.CheckConstraint(condition=(Q(archivo__isnull=False, referencia_externa='') | (Q(archivo__isnull=True) & ~Q(referencia_externa=''))), name='fuente_un_soporte')]


class FragmentoFuente(models.Model):
    fuente = models.ForeignKey(FuenteVersion, on_delete=models.PROTECT, related_name='fragmentos')
    localizador = models.CharField(max_length=240)
    hoja = models.CharField(max_length=120, blank=True)
    celda = models.CharField(max_length=40, blank=True)
    rango = models.CharField(max_length=40, blank=True)
    texto_original = models.TextField(blank=True)
    formula_original = models.TextField(blank=True)
    contexto = models.JSONField(default=dict)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['fuente', 'localizador'], name='fragmento_localizador_unico')]
