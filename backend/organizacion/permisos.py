from rest_framework.permissions import BasePermission
from cuentas.models import Usuario


def es_coordinador_activo(usuario):
    if not (usuario.is_authenticated and usuario.is_active and (usuario.tiene_rol(Usuario.Rol.COORDINADOR))):
        return False
    # Verificar también la identidad vigente evita reutilizar un actor en caché
    # después de un relevo, aunque ahora exista otro coordinador activo.
    from cuentas.autorizacion import usuarios_con_rol
    titulares = list(usuarios_con_rol('coordinador').filter(is_active=True).order_by('pk').values_list('pk',flat=True)[:2])
    return titulares == [usuario.pk]



def puede_gestionar_operacion(usuario):
    return bool(usuario.is_authenticated and usuario.is_active and (
        (usuario.tiene_rol(Usuario.Rol.ADMINISTRADOR)) or es_coordinador_activo(usuario)
    ))


class LecturaOOperacion(BasePermission):
    def has_permission(self, request, view):
        usuario = request.user
        if not usuario.is_authenticated or not usuario.is_active or not any(usuario.tiene_rol(r) for r in ("administrador","coordinador","profesor")):
            return False
        if (usuario.tiene_rol(Usuario.Rol.COORDINADOR)) and not es_coordinador_activo(usuario):
            return False
        return request.method in ("GET", "HEAD", "OPTIONS") or puede_gestionar_operacion(usuario)
