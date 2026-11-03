from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError, APIException
from organizacion.servicios import bloquear_usuarios
from auditoria.servicios import registrar
from .models import Deportista, Acudiente, VinculoAcudiente, TipoAutorizacion, Autorizacion, PoliticaDatos
from .permisos import usuario_actual

class Conflicto(APIException):
    status_code = 409
    default_detail = "El registro cambió o la operación entra en conflicto. Actualiza la información."

def version_valida(objeto, datos):
    version = datos.pop("version", None)
    if version is None:
        raise ValidationError({"version":"Obligatoria para modificar."})
    if version != objeto.version:
        raise Conflicto()

def solapan(a,b,c,d):
    return a < d and c < b

@transaction.atomic
def guardar(serializer, actor):
    bloquear_usuarios(actor, permitir_coordinador=True)
    actor = usuario_actual(actor)
    modelo = serializer.Meta.model
    if modelo in (TipoAutorizacion,PoliticaDatos) and (not actor.tiene_rol("administrador")):
        raise PermissionDenied("Solo administración define políticas y tipos.")
    anterior = serializer.instance
    if anterior:
        anterior = modelo.objects.select_for_update().get(pk=anterior.pk)
        serializer.instance = anterior
        version_valida(anterior,serializer.validated_data)
        if modelo == Autorizacion:
            raise ValidationError("Las autorizaciones no se editan: revoca y registra una nueva.")
        if modelo == VinculoAcudiente and any(k in serializer.validated_data for k in ("deportista","acudiente","fecha_inicio")):
            raise ValidationError("No se cambia la identidad de un vínculo histórico.")
        if modelo == TipoAutorizacion:
            from .facultades import esquema_facultades
            usado = Autorizacion.objects.filter(tipo=anterior).exists()
            if esquema_facultades():
                usado = usado or anterior.comprobaciones_facultad.exists()
            if usado and set(serializer.validated_data)-{"activo"}:
                raise ValidationError("Crea una versión nueva del texto utilizado.")
    else:
        serializer.validated_data.pop("version",None)
    datos = serializer.validated_data
    valor = lambda k,default=None: datos.get(k,getattr(anterior,k,default))
    hoy = timezone.localdate()
    if modelo == Deportista:
        from .documentos_servicios import CAMPOS_DOCUMENTO,preparar_documento
        if anterior and CAMPOS_DOCUMENTO.intersection(datos):
            raise ValidationError("Utiliza el cambio documental con motivo y versión.")
        if not anterior:
            datos.update(preparar_documento(datos))
        if valor("fecha_nacimiento") > hoy:
            raise ValidationError({"fecha_nacimiento":"No puede ser futura."})
        if anterior and valor("estado") != "activo" and anterior.inscripciones.filter(fecha_salida__isnull=True,grupo__periodo__fecha_fin__gte=hoy).exists():
            raise ValidationError("Finaliza primero sus inscripciones.")
    if modelo == Acudiente and anterior and valor("activo") is False and anterior.vinculos.filter(fecha_inicio__lte=hoy).filter(Q(fecha_fin__isnull=True)|Q(fecha_fin__gt=hoy)).exists():
        raise ValidationError("Finaliza primero los vínculos vigentes.")
    if modelo == VinculoAcudiente:
        persona,contacto = valor("deportista"),valor("acudiente")
        inicio,fin = valor("fecha_inicio"),valor("fecha_fin")
        if not contacto.activo or (fin and fin<=inicio):
            raise ValidationError("Contacto inactivo o fechas inválidas.")
        for otro in VinculoAcudiente.objects.filter(deportista=persona).exclude(pk=getattr(anterior,"pk",None)):
            if solapan(inicio,fin or hoy.max,otro.fecha_inicio,otro.fecha_fin or hoy.max):
                if otro.acudiente_id == contacto.pk or (otro.es_contacto_principal and valor("es_contacto_principal",False)):
                    raise ValidationError("Vínculo o contacto principal solapado.")
    if modelo == Autorizacion:
        vinculo = valor("vinculo_acudiente")
        if valor("otorgante")=="acudiente":
            if not vinculo or vinculo.deportista_id != valor("deportista").pk:
                raise ValidationError("El vínculo no acredita facultad para autorizar.")
            from .facultades import acreditar_otorgante
            datos['comprobacion_facultad'] = acreditar_otorgante(vinculo, datos)
            if not vinculo.acudiente.activo or vinculo.fecha_inicio>valor("vigente_desde") or (vinculo.fecha_fin and (not valor("vigente_hasta") or valor("vigente_hasta")>=vinculo.fecha_fin)):
                raise ValidationError("Vigencia fuera del vínculo acreditado.")
        elif valor("otorgante")=="deportista":
            if vinculo:
                raise ValidationError("Otorgante y vínculo incompatibles.")
            edades = list(PoliticaDatos.objects.filter(activo=True,edad_autonomia__isnull=False).values_list("edad_autonomia",flat=True))
            if len(set(edades))!=1:
                raise ValidationError("Define una política institucional de autonomía antes de registrar autorización personal.")
            nacimiento=valor("deportista").fecha_nacimiento
            declaracion=timezone.localtime(valor("declarada_en")).date()
            edad=declaracion.year-nacimiento.year-((declaracion.month,declaracion.day)<(nacimiento.month,nacimiento.day))
            if edad<edades[0]:
                raise ValidationError("Requiere facultad acreditada de acudiente.")
        if valor("vigente_hasta") and valor("vigente_hasta")<valor("vigente_desde"):
            raise ValidationError("Vigencia inválida.")
        if valor("declarada_en")>timezone.now() or not valor("tipo").activo:
            raise ValidationError("Declaración futura o tipo inactivo.")
        if valor("decision")=="otorgada" and not valor("referencia_evidencia"):
            raise ValidationError("Indica referencia privada de la evidencia.")
        otras=Autorizacion.objects.filter(deportista=valor("deportista"),tipo__codigo=valor("tipo").codigo,revocada_en__isnull=True)
        for otra in otras:
            if otra.otorgante==valor("otorgante") and otra.vinculo_acudiente_id==getattr(vinculo,"pk",None) and valor("vigente_desde") <= (otra.vigente_hasta or hoy.max) and otra.vigente_desde <= (valor("vigente_hasta") or hoy.max):
                raise ValidationError("Revoca la declaración anterior antes de sustituirla.")
    campos=list(datos)
    if anterior:
        objeto=serializer.save(actualizado_por=actor,version=anterior.version+1)
    else:
        objeto=serializer.save(creado_por=actor,actualizado_por=actor)
    registrar(actor,objeto,"modificar" if anterior else "crear",campos)
    if modelo == Deportista and not anterior and objeto.numero_documento:
        from .documentos_servicios import registrar_historia
        registrar_historia(objeto,actor,"registro_inicial",(None,None,None))
    return objeto

@transaction.atomic
def verificar_vinculo(objeto, actor, datos):
    from .facultades import comprobar_facultad
    return comprobar_facultad(objeto, actor, datos).vinculo

@transaction.atomic
def revocar(objeto,actor,datos):
    bloquear_usuarios(actor,permitir_coordinador=True)
    objeto=Autorizacion.objects.select_for_update().get(pk=objeto.pk)
    version_valida(objeto,datos)
    if objeto.revocada_en:
        raise Conflicto()
    if not datos.get("motivo"):
        raise ValidationError({"motivo":"Obligatorio."})
    objeto.revocada_en=timezone.now()
    objeto.motivo_revocacion=datos["motivo"]
    objeto.actualizado_por=actor
    objeto.version+=1
    objeto.save()
    registrar(actor,objeto,"revocar",["revocada_en","motivo_revocacion"])
    return objeto
