from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from auditoria.servicios import registrar
from organizacion.servicios import bloquear_usuarios
from .models import Usuario
from .autorizacion import usuarios_con_rol, roles_vigentes


@transaction.atomic
def guardar_usuario(serializer, actor):
    bloquear_usuarios(actor)
    anterior = serializer.instance
    if anterior:
        anterior = Usuario.objects.select_for_update().get(pk=anterior.pk)
        serializer.instance = anterior
        rol = serializer.validated_data.get("rol", anterior.rol)
        activo = serializer.validated_data.get("is_active", anterior.is_active)
        if activo and not anterior.is_active and not anterior.pertenencias.filter(vigente=True).exists():
            raise ValidationError({'is_active':'Otorga una facultad explícita antes de reactivar. El cargo coordinador se nombra mediante relevo.'})
        if anterior.pk == actor.pk and (rol != anterior.rol or not activo):
            raise ValidationError("No puedes desactivar tu cuenta ni modificar tu propio rol.")
        if anterior.is_active and anterior.tiene_rol("administrador") and (rol != "administrador" or not activo):
            if not usuarios_con_rol("administrador").filter(is_active=True).exclude(pk=anterior.pk).exists():
                raise ValidationError("Debe conservarse al menos un administrador activo.")
        if rol != anterior.rol and len(roles_vigentes(anterior))>1:
            raise ValidationError({"rol":"Gestiona las pertenencias por el flujo de roles múltiples."})
        if rol != anterior.rol and anterior.asignaciones.filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=timezone.localdate()), grupo__periodo__fecha_fin__gte=timezone.localdate()).exists():
            raise ValidationError({"rol": "Finaliza primero las asignaciones vigentes o futuras antes de cambiar el rol."})
    era_coordinador = bool(anterior and anterior.tiene_rol("coordinador"))
    activo_propuesto=serializer.validated_data.get("is_active", anterior.is_active if anterior else True)
    rol_propuesto=serializer.validated_data.get("rol", anterior.rol if anterior else "profesor")
    sera_coordinador = activo_propuesto and (rol_propuesto=="coordinador" or
        (era_coordinador and anterior is not None and rol_propuesto==anterior.rol))
    if sera_coordinador and usuarios_con_rol("coordinador").filter(is_active=True).exclude(pk=anterior.pk if anterior else None).exists():
        raise ValidationError({"rol": "Ya existe un coordinador activo. Utiliza el relevo de coordinación."})
    campos = [campo for campo in serializer.validated_data if campo != "contrasena"]
    contrasena = serializer.validated_data.pop("contrasena", None)
    usuario = serializer.save()
    if not anterior or contrasena:
        if contrasena:
            usuario.set_password(contrasena)
        else:
            usuario.set_unusable_password()
        usuario.save(update_fields=["password"])
    # Una cuenta degradada no conserva privilegios técnicos de Django.
    if not usuario.pertenencias.filter(rol="administrador",vigente=True).exists() and (usuario.is_staff or usuario.is_superuser):
        usuario.is_staff = False
        usuario.is_superuser = False
        usuario.save(update_fields=["is_staff", "is_superuser"])
    registrar(actor, usuario, "modificar" if anterior else "crear", campos)
    if era_coordinador and not sera_coordinador:
        registrar(actor, usuario, "coordinacion_fin", ["rol", "is_active"])
    elif sera_coordinador and not era_coordinador:
        registrar(actor, usuario, "coordinacion_inicio", ["rol", "is_active"])
    return usuario
