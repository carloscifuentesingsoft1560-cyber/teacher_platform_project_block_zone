from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class GestorUsuarios(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields["rol"] = "administrador"
        return super().create_superuser(username, email, password, **extra_fields)


class Usuario(AbstractUser):
    class Rol(models.TextChoices):
        PROFESOR = "profesor", "Profesor"
        COORDINADOR = "coordinador", "Coordinador"
        ADMINISTRADOR = "administrador", "Administrador"
        ROUTESETTER = "routesetter", "Routesetter"
        DEPORTISTA = "deportista", "Deportista"
        ACUDIENTE = "acudiente", "Acudiente"

    rol = models.CharField("rol", max_length=20, choices=Rol.choices, default=Rol.PROFESOR)
    objects = GestorUsuarios()

    def tiene_rol(self, rol):
        from .autorizacion import tiene_rol
        return tiene_rol(self, rol)

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        constraints = [
            models.CheckConstraint(condition=models.Q(rol__in=["profesor", "coordinador", "administrador", "routesetter", "deportista", "acudiente"]), name="usuario_rol_valido"),
            models.UniqueConstraint(fields=["rol"], condition=models.Q(rol="coordinador", is_active=True), name="un_coordinador_activo"),
        ]


class EventoAcceso(models.Model):
    class Tipo(models.TextChoices):
        INGRESO = "ingreso", "Ingreso"
        SALIDA = "salida", "Salida"
        FALLO = "fallo", "Intento fallido"

    usuario = models.ForeignKey(Usuario, null=True, blank=True, on_delete=models.SET_NULL)
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "evento de acceso"
        verbose_name_plural = "eventos de acceso"
        ordering = ["-fecha"]

class SolicitudRestablecimiento(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="solicitudes_acceso")
    solicitado_por = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="recuperaciones_solicitadas")
    token_hash = models.CharField(max_length=64, unique=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_expira = models.DateTimeField()
    fecha_uso = models.DateTimeField(null=True, blank=True)
from .modelos_identidad import Persona, EnlaceIdentidad  # noqa: E402,F401
from .modelos_roles import PertenenciaRol, EventoRol  # noqa: E402,F401
