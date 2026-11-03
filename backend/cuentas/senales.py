"""Auditoría mínima de autenticación sin contraseñas, nombres ingresados ni IP."""
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from .models import EventoAcceso


@receiver(user_logged_in)
def registrar_ingreso(sender, request, user, **kwargs):
    EventoAcceso.objects.create(usuario=user, tipo=EventoAcceso.Tipo.INGRESO)


@receiver(user_logged_out)
def registrar_salida(sender, request, user, **kwargs):
    if user is not None and user.pk:
        EventoAcceso.objects.create(usuario=user, tipo=EventoAcceso.Tipo.SALIDA)


@receiver(user_login_failed)
def registrar_fallo(sender, credentials, request, **kwargs):
    EventoAcceso.objects.create(tipo=EventoAcceso.Tipo.FALLO)
