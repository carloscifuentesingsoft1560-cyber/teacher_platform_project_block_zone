from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import EventoAcceso, Usuario


@admin.register(Usuario)
class AdministracionUsuario(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Zona de Bloque", {"fields": ("rol",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Zona de Bloque", {"fields": ("rol",)}),)
    list_display = ("username", "rol", "is_active", "is_staff")
    list_filter = ("rol", "is_active")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # Las escrituras se centralizan en React/API con auditoría y validaciones.
        return False

    def has_delete_permission(self, request, obj=None):
        return False


def acceso_administracion(request):
    usuario = request.user
    return usuario.is_active and usuario.is_staff and (usuario.tiene_rol(Usuario.Rol.ADMINISTRADOR))


admin.site.has_permission = acceso_administracion
admin.site.site_header = "Zona de Bloque | Administración"
admin.site.site_title = "Zona de Bloque"


@admin.register(EventoAcceso)
class AdministracionEventoAcceso(admin.ModelAdmin):
    list_display = ("fecha", "tipo", "usuario")
    list_filter = ("tipo",)
    readonly_fields = ("fecha", "tipo", "usuario")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False