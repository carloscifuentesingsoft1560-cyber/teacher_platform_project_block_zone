from django.conf import settings
from django.db import models
from django.db.models import Q, F
from django.utils import timezone

ROLES = [(r, r.capitalize()) for r in ('administrador','coordinador','profesor','routesetter','deportista','acudiente')]


class PertenenciaRol(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='pertenencias')
    rol = models.CharField(max_length=20, choices=ROLES)
    vigente = models.BooleanField(default=True)
    fecha_inicio = models.DateTimeField(default=timezone.now)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(rol__in=[r[0] for r in ROLES]), name='pertenencia_rol_valido'),
            models.CheckConstraint(condition=Q(vigente=True, fecha_fin__isnull=True) |
                Q(vigente=False, fecha_fin__isnull=False, fecha_fin__gte=F('fecha_inicio')), name='pertenencia_estado_coherente'),
            models.UniqueConstraint(fields=['usuario','rol'], condition=Q(vigente=True), name='pertenencia_vigente_unica'),
            models.UniqueConstraint(fields=['rol'], condition=Q(rol='coordinador', vigente=True), name='pertenencia_coordinador_unico'),
        ]


class EventoRol(models.Model):
    pertenencia = models.ForeignKey(PertenenciaRol, on_delete=models.PROTECT, related_name='eventos')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    accion = models.CharField(max_length=20)
    motivo = models.CharField(max_length=240)
    fecha = models.DateTimeField(auto_now_add=True)
    version = models.PositiveIntegerField()

    def save(self, *args, **kwargs):
        if not self._state.adding:
            from django.core.exceptions import ValidationError
            raise ValidationError('El historial de roles es inmutable.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        raise ValidationError('El historial de roles no se elimina.')
