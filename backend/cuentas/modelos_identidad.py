import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q


class Persona(models.Model):
    identificador = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    creada_en = models.DateTimeField(auto_now_add=True)
    creada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    version = models.PositiveIntegerField(default=1)


class EnlaceIdentidad(models.Model):
    persona = models.ForeignKey(Persona, on_delete=models.PROTECT, related_name='enlaces')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='enlaces_identidad')
    deportista = models.ForeignKey('deportistas.Deportista', null=True, blank=True, on_delete=models.PROTECT, related_name='enlaces_identidad')
    acudiente = models.ForeignKey('deportistas.Acudiente', null=True, blank=True, on_delete=models.PROTECT, related_name='enlaces_identidad')
    evidencia = models.UUIDField()
    acreditado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    acreditado_en = models.DateTimeField(auto_now_add=True)
    vigente = models.BooleanField(default=True)
    revocado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    revocado_en = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(Q(usuario__isnull=False, deportista__isnull=True, acudiente__isnull=True) |
                Q(usuario__isnull=True, deportista__isnull=False, acudiente__isnull=True) |
                Q(usuario__isnull=True, deportista__isnull=True, acudiente__isnull=False)), name='identidad_un_perfil_por_enlace'),
            models.CheckConstraint(condition=Q(vigente=True, revocado_por__isnull=True, revocado_en__isnull=True) |
                Q(vigente=False, revocado_por__isnull=False, revocado_en__isnull=False), name='identidad_revocacion_coherente'),
            *[models.UniqueConstraint(fields=[campo], condition=Q(vigente=True), name='identidad_perfil_unico_'+campo)
              for campo in ('usuario', 'deportista', 'acudiente')],
            *[models.UniqueConstraint(fields=['persona'], condition=Q(vigente=True, **{campo+'__isnull': False}),
                name='identidad_persona_un_'+campo) for campo in ('usuario', 'deportista', 'acudiente')],
        ]
