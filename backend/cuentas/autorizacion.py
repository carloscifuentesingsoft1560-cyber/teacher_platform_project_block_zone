"""Facultades vigentes; el rol principal no concede acceso tras la transición."""
from django.apps import apps
from django.utils import timezone

ACCIONES = {
    'contenido.crear': ('administrador', 'coordinador', 'profesor', 'routesetter'),
    'contenido.revisar': ('coordinador',),
    'cuentas.gestionar': ('administrador',),
    'identidad.gestionar': ('administrador',),
    'organizacion.gestionar': ('administrador', 'coordinador'),
    'ascensos.proponer': ('profesor',),
    'ascensos.revisar': ('coordinador',),
    'ascensos.formalizar': ('administrador',),
}


def roles_vigentes(usuario):
    if not getattr(usuario, 'is_authenticated', False) or not usuario.pk:
        return []
    Rol = apps.get_model('cuentas', 'PertenenciaRol')
    return list(Rol.objects.filter(usuario_id=usuario.pk, usuario__is_active=True, vigente=True,
        fecha_inicio__lte=timezone.now()).order_by('rol').values_list('rol', flat=True))



def tiene_rol(usuario, rol):
    return rol in roles_vigentes(usuario)


def puede(usuario, accion):
    return bool(set(roles_vigentes(usuario)).intersection(ACCIONES.get(accion, ())))


def usuarios_con_rol(rol):
    Usuario = apps.get_model('cuentas', 'Usuario')
    return Usuario.objects.filter(pertenencias__rol=rol, pertenencias__vigente=True,
        pertenencias__fecha_inicio__lte=timezone.now()).distinct()
