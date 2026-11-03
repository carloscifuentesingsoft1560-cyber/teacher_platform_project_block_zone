from django.db.models import Q
from rest_framework.exceptions import PermissionDenied, ValidationError
from collections.abc import Mapping
from rest_framework.permissions import BasePermission
from cuentas.autorizacion import roles_vigentes, puede
from organizacion.alcance import grupos_permitidos


def roles(actor):
    return set(roles_vigentes(actor))


def custodio(actor):
    return bool(roles(actor) & {'administrador', 'coordinador'})


def exigir_editor(actor):
    if not puede(actor, 'contenido.crear'):
        raise PermissionDenied('Se requieren facultades docentes vigentes.')


class AccesoContenido(BasePermission):
    def has_permission(self, request, view):
        permitido = bool(request.user.is_authenticated and roles(request.user) & {'administrador', 'coordinador', 'profesor', 'routesetter'})
        if permitido and request.method not in ('GET','HEAD','OPTIONS') and not isinstance(request.data, Mapping):
            raise ValidationError('Se requiere un objeto de campos, no una lista o valor aislado.')
        return permitido


def programas_visibles(actor):
    from curriculo.models import ProgramaFormativo
    if custodio(actor):
        return ProgramaFormativo.objects.all()
    if 'profesor' in roles(actor):
        return ProgramaFormativo.objects.filter(nivel__in=grupos_permitidos(actor).values('nivel_id'))
    return ProgramaFormativo.objects.none()


def versiones_visibles(actor, queryset, tipo):
    if custodio(actor):
        return queryset
    r = roles(actor)
    if not r & {'profesor', 'routesetter'}:
        return queryset.none()
    propio = Q(autor=actor)
    if tipo == 'malla':
        if 'profesor' not in r:
            return queryset.none()
        return queryset.filter(propio | Q(estado='aprobado', vigente=True, identidad__programa__in=programas_visibles(actor))).distinct()
    docente = Q(estado='aprobado', vigente=True, programas__in=programas_visibles(actor))
    if 'routesetter' in r:
        docente |= Q(estado='aprobado', vigente=True, acceso_tecnico=True)
    return queryset.filter(propio | docente).distinct()
