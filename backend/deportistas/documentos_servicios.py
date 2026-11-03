"""Escritura documental centralizada; solo se persiste el número vigente."""
from django.db import transaction,IntegrityError
from rest_framework.exceptions import ValidationError
from organizacion.servicios import bloquear_usuarios
from auditoria.servicios import registrar
from .models import Deportista,TipoDocumento,CambioDocumentoDeportista
from .documentos_reglas import normalizar_identificacion,enmascarar,MOTIVOS_CAMBIO,texto_canonico
from .servicios import version_valida,Conflicto

CAMPOS_DOCUMENTO={"tipo_documento","numero_documento","pais_emisor"}

def preparar_documento(datos, anterior=None):
    tipo=datos.get("tipo_documento")
    codigo=tipo.codigo if tipo is not None else None
    try:
        codigo,numero,pais=normalizar_identificacion(codigo,datos.get("numero_documento"),datos.get("pais_emisor"))
    except ValueError as error:
        raise ValidationError({"documento":str(error)})
    if codigo:
        tipo=TipoDocumento.objects.select_for_update().get(codigo=codigo)
        if not tipo.activo and codigo!=getattr(anterior,"tipo_documento_id",None):
            raise ValidationError({"tipo_documento":"El tipo documental no está habilitado."})
        consulta=Deportista.objects.filter(tipo_documento_id=codigo,numero_documento=numero,pais_emisor=pais)
        if anterior:
            consulta=consulta.exclude(pk=anterior.pk)
        if consulta.exists():
            raise Conflicto("La identificación indicada ya está registrada. Revisa la ficha existente.")
    return {"tipo_documento":tipo,"numero_documento":numero,"pais_emisor":pais}

def registrar_historia(persona,actor,motivo,antes):
    CambioDocumentoDeportista.objects.create(deportista=persona,actor=actor,motivo=motivo,
        tipo_anterior=antes[0] or "",pais_anterior=antes[2] or "",
        documento_anterior_enmascarado=enmascarar(antes[1]),
        tipo_nuevo=persona.tipo_documento_id or "",pais_nuevo=persona.pais_emisor or "",
        documento_nuevo_enmascarado=enmascarar(persona.numero_documento),
        version_resultante=persona.version)

@transaction.atomic
def cambiar_documento(persona,actor,datos):
    bloquear_usuarios(actor,permitir_coordinador=True)
    persona=Deportista.objects.select_for_update().get(pk=persona.pk)
    datos=dict(datos)
    version_valida(persona,datos)
    motivo=datos.pop("motivo",None)
    if motivo not in MOTIVOS_CAMBIO:
        raise ValidationError({"motivo":"Selecciona el motivo administrativo del cambio."})
    antes=(persona.tipo_documento_id,persona.numero_documento,persona.pais_emisor)
    nuevos=preparar_documento(datos,persona)
    despues=(getattr(nuevos["tipo_documento"],"codigo",None),nuevos["numero_documento"],nuevos["pais_emisor"])
    if antes==despues:
        return persona
    if antes[0] and not despues[0] and motivo!="anulacion_por_error":
        raise ValidationError({"motivo":"Una identificación conocida solo se retira por anulación de un dato erróneo."})
    for campo,valor in nuevos.items():
        setattr(persona,campo,valor)
    persona.version+=1
    persona.actualizado_por=actor
    try:
        with transaction.atomic():
            persona.save(update_fields=["tipo_documento","numero_documento","pais_emisor","version","actualizado_por","actualizado_en"])
    except IntegrityError:
        raise Conflicto("La identificación indicada ya está registrada o no cumple las reglas documentales.") from None
    registrar_historia(persona,actor,motivo,antes)
    registrar(actor,persona,"cambiar_documento",sorted(CAMPOS_DOCUMENTO))
    return persona

@transaction.atomic
def guardar_tipo(serializer,actor):
    bloquear_usuarios(actor)
    creando=serializer.instance is None
    if serializer.instance:
        anterior=TipoDocumento.objects.select_for_update().get(pk=serializer.instance.pk)
        serializer.instance=anterior
        version_valida(anterior,serializer.validated_data)
        if "codigo" in serializer.validated_data:
            raise ValidationError({"codigo":"El código documental es permanente."})
        objeto=serializer.save(version=anterior.version+1)
    else:
        serializer.validated_data.pop("version",None)
        objeto=serializer.save()
    registrar(actor,objeto,"crear_tipo_documento" if creando else "modificar_tipo_documento",["nombre","activo","referencia_aprobacion"])
    return objeto
