from rest_framework.permissions import BasePermission


class TieneRolDelPanel(BasePermission):
    message = "No tienes permiso para acceder a este panel."

    def has_permission(self, request, view):
        usuario = request.user
        return bool(usuario.is_authenticated and usuario.is_active and (usuario.tiene_rol(view.rol_requerido)))
