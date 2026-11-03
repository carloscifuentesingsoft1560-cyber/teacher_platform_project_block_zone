from cuentas.autorizacion import usuarios_con_rol
from django.db.models import Q
from django.utils import timezone
from cuentas.models import Usuario
from .models import Grupo, Asignacion
from .permisos import es_coordinador_activo

def en_fecha(fecha=None):
    fecha = fecha or timezone.localdate()
    return Q(fecha_inicio__lte=fecha, grupo__periodo__fecha_inicio__lte=fecha, grupo__periodo__fecha_fin__gte=fecha) & (Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha))

def grupos_permitidos(usuario):
    grupos = Grupo.objects.select_related("disciplina", "nivel", "periodo").prefetch_related("horarios")
    if (usuario.tiene_rol(Usuario.Rol.ADMINISTRADOR)) or es_coordinador_activo(usuario):
        return grupos
    if (not usuario.tiene_rol(Usuario.Rol.PROFESOR)):
        return grupos.none()
    ids = Asignacion.objects.filter(en_fecha(), usuario=usuario, tipo="profesor").values("grupo_id")
    return grupos.filter(pk__in=ids)

def asignaciones_permitidas(usuario):
    datos = Asignacion.objects.select_related("grupo", "usuario")
    if (usuario.tiene_rol(Usuario.Rol.ADMINISTRADOR)):
        return datos
    if (usuario.tiene_rol(Usuario.Rol.PROFESOR)):
        return datos.filter(en_fecha(), usuario=usuario, tipo="profesor")
    return datos.filter(tipo="profesor") if es_coordinador_activo(usuario) else datos.none()
