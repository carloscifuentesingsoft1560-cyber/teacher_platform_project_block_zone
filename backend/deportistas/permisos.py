from django.db import connection
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.permissions import BasePermission
from cuentas.models import Usuario
from organizacion.alcance import grupos_permitidos

class EsquemaPendiente(APIException):
    status_code = 503
    default_detail = "La Fase 3 requiere migraciones pendientes de autorización."

class IdentificacionPendiente(APIException):
    status_code = 503
    default_detail = "La identificación documental requiere una migración pendiente de autorización. No se han cambiado los registros existentes."

def documentos_disponibles():
    tablas=set(connection.introspection.table_names())
    if not {"deportistas_tipodocumento","deportistas_cambiodocumentodeportista"}.issubset(tablas):
        return False
    with connection.cursor() as cursor:
        columnas={c.name for c in connection.introspection.get_table_description(cursor,"deportistas_deportista")}
    return {"tipo_documento_id","numero_documento","pais_emisor"}.issubset(columnas)

def esquema_disponible():
    requeridas = {"deportistas_deportista","deportistas_acudiente","deportistas_vinculoacudiente",
        "deportistas_tipoautorizacion","deportistas_autorizacion","deportistas_politicadatos",
        "inscripciones_inscripcion","inscripciones_eventoinscripcion","inscripciones_reservacupo","inscripciones_propuesta"}
    return requeridas.issubset(set(connection.introspection.table_names()))

def usuario_actual(actor):
    actual = Usuario.objects.filter(pk=actor.pk,is_active=True).first()
    if actual is None:
        raise PermissionDenied("La cuenta ya no está activa.")
    return actual

def es_gestor(actor):
    from organizacion.permisos import puede_gestionar_operacion
    return puede_gestionar_operacion(usuario_actual(actor))

class AccesoFase3(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated or not request.user.is_active:
            return False
        usuario_actual(request.user)
        if not esquema_disponible():
            raise EsquemaPendiente()
        if not documentos_disponibles():
            raise IdentificacionPendiente()
        return True

def inscripciones_visibles(actor):
    from inscripciones.models import Inscripcion
    datos = Inscripcion.objects.select_related("deportista","grupo__nivel","grupo__disciplina","grupo__periodo")
    if es_gestor(actor):
        return datos
    actual = usuario_actual(actor)
    if (not actual.tiene_rol("profesor")):
        return datos.none()
    hoy = timezone.localdate()
    return datos.filter(grupo__in=grupos_permitidos(actual),grupo__activo=True,
        grupo__periodo__activo=True,fecha_ingreso__lte=hoy).filter(
        Q(fecha_salida__isnull=True)|Q(fecha_salida__gt=hoy)).filter(
        Q(estado="activa")|Q(estado="suspendida",reservas__fecha_vencimiento__gte=hoy,reservas__liberada_en__isnull=True)).distinct()

def deportistas_visibles(actor):
    from .models import Deportista
    if es_gestor(actor):
        return Deportista.objects.all()
    return Deportista.objects.filter(inscripciones__in=inscripciones_visibles(actor)).distinct()

class SoloGestion(BasePermission):
    """Rechaza antes de validar cuerpos o consultar relaciones privadas."""
    def has_permission(self, request, view):
        if not es_gestor(request.user):
            return False
        from .models import TipoAutorizacion, PoliticaDatos
        modelo=view.serializer_class.Meta.model
        if request.method not in ("GET","HEAD","OPTIONS") and modelo in (TipoAutorizacion,PoliticaDatos):
            return (usuario_actual(request.user).tiene_rol("administrador"))
        return True
