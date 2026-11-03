"""Ámbito efectivo compartido por listas, detalle y comandos HTTP."""
from collections.abc import Mapping
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from rest_framework.permissions import BasePermission
from rest_framework.exceptions import ValidationError
from cuentas.models import Usuario
from organizacion.models import Asignacion, Grupo
from organizacion.permisos import puede_gestionar_operacion
from .models import Sesion


def actor_actual(actor):
    return Usuario.objects.filter(pk=actor.pk, is_active=True).first()


class AccesoSesiones(BasePermission):
    def has_permission(self, request, view):
        actor = actor_actual(request.user)
        if not actor or not (puede_gestionar_operacion(actor) or actor.tiene_rol('profesor')):
            return False
        if request.method in ('POST', 'PATCH') and not isinstance(request.data, Mapping):
            raise ValidationError('Se requiere un objeto JSON.')
        return True


def asignaciones_actuales(actor):
    hoy = timezone.localdate()
    return Asignacion.objects.filter(usuario=actor, tipo='profesor', fecha_inicio__lte=hoy).filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=hoy))


def sesiones_visibles(actor):
    actor = actor_actual(actor)
    datos = Sesion.objects.all()
    if not actor:
        return datos.none()
    if puede_gestionar_operacion(actor):
        return datos
    if not actor.tiene_rol('profesor'):
        return datos.none()
    asignacion = asignaciones_actuales(actor).filter(grupo_id=OuterRef('grupo_id'), fecha_inicio__lte=OuterRef('fecha')).filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=OuterRef('fecha')))
    return datos.filter(profesor=actor).annotate(asignado=Exists(asignacion)).filter(asignado=True)


def grupos_disponibles(actor, fecha=None):
    actor = actor_actual(actor)
    datos = Grupo.objects.filter(activo=True, periodo__activo=True)
    if not actor:
        return datos.none()
    if puede_gestionar_operacion(actor):
        return datos
    if not actor.tiene_rol('profesor'):
        return datos.none()
    asignaciones = asignaciones_actuales(actor)
    if fecha is not None:
        asignaciones = asignaciones.filter(fecha_inicio__lte=fecha).filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha))
    return datos.filter(pk__in=asignaciones.values('grupo_id'))
