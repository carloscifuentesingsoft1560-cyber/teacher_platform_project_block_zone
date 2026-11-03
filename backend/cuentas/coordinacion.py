"""Cargo único e historial mediante los modelos existentes."""
from django.db import transaction
from rest_framework.exceptions import APIException, ValidationError
from auditoria.models import CambioAdministrativo
from organizacion.servicios import bloquear_usuarios
from .models import Usuario, PertenenciaRol, EventoRol
from .autorizacion import usuarios_con_rol
from django.utils import timezone
from auditoria.servicios import registrar
from .serializers import UsuarioSerializer
from .serializers_usuarios import AdministracionUsuarioSerializer
from .servicios_usuarios import guardar_usuario


class ConflictoCoordinacion(APIException):
    status_code = 409
    default_detail = "La coordinación cambió. Actualiza la información antes de confirmar."


def coordinador_actual():
    cuentas = list(usuarios_con_rol("coordinador").filter(is_active=True).order_by("pk")[:2])
    if len(cuentas) > 1:
        raise ConflictoCoordinacion("Hay más de un coordinador activo. Administración debe resolverlo antes del relevo.")
    return cuentas[0] if cuentas else None


@transaction.atomic
def relevar_coordinador(actor, usuario, coordinador_actual_id):
    bloquear_usuarios(actor)
    saliente = coordinador_actual()
    if (saliente.pk if saliente else None) != coordinador_actual_id:
        raise ConflictoCoordinacion()
    entrante = Usuario.objects.select_for_update().get(pk=usuario.pk)
    if saliente and saliente.pk == entrante.pk:
        raise ValidationError("La persona seleccionada ya ocupa el cargo.")
    if entrante.pk == actor.pk:
        raise ValidationError("No puedes cambiar tu propio rol administrativo.")
    if not entrante.is_active:
        raise ValidationError('Activa la cuenta antes de nombrar al coordinador.')
    if saliente:
        r=PertenenciaRol.objects.select_for_update().get(usuario=saliente,rol='coordinador',vigente=True)
        r.vigente=False;r.fecha_fin=timezone.now();r.version+=1;r.save()
        EventoRol.objects.create(pertenencia=r,actor=actor,accion='revocar',motivo='Relevo institucional',version=r.version)
        registrar(actor,saliente,'coordinacion_fin',['rol'])
        if saliente.rol=='coordinador':
            otra=PertenenciaRol.objects.filter(usuario=saliente,vigente=True).order_by('id').first()
            if otra:saliente.rol=otra.rol
            else:saliente.is_active=False
            saliente.save(update_fields=['rol','is_active'])
    r=PertenenciaRol.objects.create(usuario=entrante,rol='coordinador')
    EventoRol.objects.create(pertenencia=r,actor=actor,accion='otorgar',motivo='Relevo institucional',version=1)
    registrar(actor,entrante,'coordinacion_inicio',['rol'])
    return entrante



def eventos_cargo():
    return CambioAdministrativo.objects.filter(
        entidad="cuentas.usuario", accion__in=["coordinacion_inicio", "coordinacion_fin"]
    ).select_related("actor").order_by("-fecha", "-id")
