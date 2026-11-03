from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied,ValidationError
from cuentas.models import Usuario
from deportistas.permisos import usuario_actual,es_gestor,deportistas_visibles
from deportistas.servicios import version_valida,Conflicto
from auditoria.servicios import registrar
from .models import Propuesta

@transaction.atomic
def cancelar(propuesta,actor,datos):
    list(Usuario.objects.select_for_update().order_by("pk"))
    actor=usuario_actual(actor)
    p=Propuesta.objects.select_for_update().get(pk=propuesta.pk)
    if not es_gestor(actor) and (p.creado_por_id!=actor.pk or not deportistas_visibles(actor).filter(pk=p.deportista_id).exists()):
        raise PermissionDenied()
    version_valida(p,datos)
    if p.estado!="pendiente":
        raise Conflicto()
    if not datos.get("resolucion"):
        raise ValidationError({"resolucion":"Indica el motivo de cancelación."})
    p.estado="cancelada"
    p.resuelta_por=actor
    p.resuelta_en=timezone.now()
    p.resolucion=datos["resolucion"]
    p.actualizado_por=actor
    p.version+=1
    p.save()
    registrar(actor,p,"cancelar",["estado","resolucion"])
    return p
