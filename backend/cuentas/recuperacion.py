import hashlib
import secrets
from datetime import timedelta
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as ErrorDjango
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from auditoria.servicios import registrar
from organizacion.servicios import bloquear_usuarios
from .models import Usuario, SolicitudRestablecimiento

def resumen_token(token):
    return hashlib.sha256(token.encode()).hexdigest()

@transaction.atomic
def solicitar_restablecimiento(usuario_id, actor, contrasena_actual):
    bloquear_usuarios(actor)
    administrador = Usuario.objects.get(pk=actor.pk)
    if not administrador.is_active or (not administrador.tiene_rol("administrador")) or not administrador.check_password(contrasena_actual):
        raise ValidationError({"contrasena_actual": "No se pudo verificar tu contraseña actual."})
    usuario = Usuario.objects.select_for_update().get(pk=usuario_id)
    if not usuario.is_active:
        raise ValidationError("Activa la cuenta antes de restablecer su acceso.")
    ahora = timezone.now()
    SolicitudRestablecimiento.objects.filter(usuario=usuario, fecha_uso__isnull=True, fecha_expira__gt=ahora).update(fecha_expira=ahora)
    token = secrets.token_urlsafe(32)
    solicitud = SolicitudRestablecimiento.objects.create(usuario=usuario, solicitado_por=actor,
        token_hash=resumen_token(token), fecha_expira=ahora + timedelta(minutes=30))
    registrar(actor, usuario, "solicitar_restablecimiento")
    return token, solicitud.fecha_expira

@transaction.atomic
def confirmar_restablecimiento(token, contrasena):
    bloquear_usuarios()
    solicitud = SolicitudRestablecimiento.objects.select_for_update().filter(token_hash=resumen_token(token)).first()
    if not solicitud or solicitud.fecha_uso or solicitud.fecha_expira <= timezone.now():
        raise ValidationError("El enlace es inválido, ya se utilizó o venció.")
    usuario = Usuario.objects.select_for_update().get(pk=solicitud.usuario_id)
    if not usuario.is_active:
        raise ValidationError("El enlace es inválido, ya se utilizó o venció.")
    try:
        validate_password(contrasena, usuario)
    except ErrorDjango as error:
        raise ValidationError({"contrasena": error.messages}) from error
    usuario.set_password(contrasena)
    usuario.save(update_fields=["password"])
    solicitud.fecha_uso = timezone.now()
    solicitud.save(update_fields=["fecha_uso"])
    registrar(solicitud.solicitado_por, usuario, "restablecimiento_completado")
    # El cambio de hash de contraseña invalida todas las sesiones anteriores.
