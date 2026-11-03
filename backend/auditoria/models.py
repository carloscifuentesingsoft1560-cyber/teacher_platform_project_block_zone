from django.conf import settings
from django.db import models

class CambioAdministrativo(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cambios_realizados")
    entidad = models.CharField(max_length=60)
    identificador = models.PositiveBigIntegerField()
    accion = models.CharField(max_length=40)
    campos = models.JSONField(default=list)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-id"]
