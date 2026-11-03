from datetime import timedelta
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied
from cuentas.models import Usuario
from organizacion.models import Grupo, Asignacion
from organizacion.alcance import en_fecha, grupos_permitidos
from organizacion.servicios import bloquear_usuarios
from auditoria.servicios import registrar
from deportistas.models import Deportista
from deportistas.permisos import usuario_actual, deportistas_visibles, esquema_disponible
from deportistas.servicios import Conflicto, version_valida
from .models import Inscripcion, ReservaCupo, EventoInscripcion, Propuesta

def evento(inscripcion,actor,tipo,motivo,anterior="",fecha=None):
    EventoInscripcion.objects.create(inscripcion=inscripcion,actor=actor,tipo=tipo,
        motivo=motivo,estado_anterior=anterior,estado_resultante=inscripcion.estado,
        fecha_efectiva=fecha or timezone.localdate())
    registrar(actor,inscripcion,tipo,["estado"])

def intervalo(inscripcion,reservas=None):
    fin=inscripcion.fecha_salida or inscripcion.grupo.periodo.fecha_fin+timedelta(days=1)
    fin=min(fin,inscripcion.grupo.periodo.fecha_fin+timedelta(days=1))
    if inscripcion.estado=="suspendida":
        reserva=(next((r for r in reservas if r.liberada_en is None),None) if reservas is not None
                 else inscripcion.reservas.filter(liberada_en__isnull=True).first())
        if reserva:
            fin=min(fin,reserva.fecha_vencimiento+timedelta(days=1))
        else:
            fin=inscripcion.fecha_ingreso
    return inscripcion.fecha_ingreso,fin

def cruzan(g1,g2,inicio,fin):
    for a in g1.horarios.filter(activo=True):
        for b in g2.horarios.filter(activo=True,dia=a.dia):
            primer=inicio+timedelta(days=(a.dia-inicio.weekday())%7)
            if primer<fin and a.hora_inicio<b.hora_fin and b.hora_inicio<a.hora_fin:
                return True
    return False

def ocupacion_maxima(grupo,inicio=None,fin=None,excluir=None,inscripciones=None):
    inicio=inicio or grupo.periodo.fecha_inicio
    fin=fin or grupo.periodo.fecha_fin+timedelta(days=1)
    puntos=[]
    datos=grupo.inscripciones.exclude(pk=excluir).select_related("grupo__periodo") if inscripciones is None else inscripciones
    for i in datos:
        if i.pk==excluir:
            continue
        a,b=intervalo(i,i.reservas.all() if inscripciones is not None else None)
        a,b=max(a,inicio),min(b,fin)
        if a<b:
            puntos.extend([(a,1),(b,-1)])
    actual=maximo=0
    for _,delta in sorted(puntos):
        actual+=delta
        maximo=max(maximo,actual)
    return maximo

def validar_nueva(persona,grupo,inicio,fin=None,excluir=None,permitir_nivel=False):
    fin=fin or grupo.periodo.fecha_fin+timedelta(days=1)
    if grupo.nivel.disciplina_id!=grupo.disciplina_id:
        raise ValidationError("Nivel ajeno a la disciplina del grupo.")
    if persona.estado!="activo" or not all([grupo.activo,grupo.periodo.activo,grupo.disciplina.activo,grupo.nivel.activo]):
        raise ValidationError("Deportista o estructura de grupo inactivos.")
    if not grupo.periodo.fecha_inicio<=inicio<=grupo.periodo.fecha_fin or fin<=inicio or fin>grupo.periodo.fecha_fin+timedelta(days=1):
        raise ValidationError("Fechas fuera del periodo.")
    if not grupo.horarios.filter(activo=True).exists():
        raise ValidationError("El grupo necesita horarios.")
    if ocupacion_maxima(grupo,inicio,fin,excluir)>=grupo.cupo_maximo:
        raise Conflicto("No hay cupo disponible durante la vigencia solicitada.")
    for otra in persona.inscripciones.exclude(pk=excluir).select_related("grupo__periodo"):
        a,b=intervalo(otra)
        a,b=max(a,inicio),min(b,fin)
        if a>=b:
            continue
        if otra.grupo_id==grupo.pk:
            raise Conflicto("Ya existe una inscripción solapada.")
        if not permitir_nivel and otra.grupo.disciplina_id==grupo.disciplina_id and otra.grupo.nivel_id!=grupo.nivel_id:
            raise ValidationError("El cambio de nivel requiere decisión pedagógica.")
        if cruzan(grupo,otra.grupo,a,b):
            raise ValidationError("El deportista tiene horarios incompatibles.")

def liberar_vencidas_bajo_bloqueo(actor):
    hoy=timezone.localdate()
    reservas=ReservaCupo.objects.select_for_update().filter(liberada_en__isnull=True,fecha_vencimiento__lt=hoy).select_related("inscripcion")
    cantidad=0
    for r in reservas:
        i=Inscripcion.objects.select_for_update().get(pk=r.inscripcion_id)
        r.liberada_en=timezone.now()
        r.liberada_por=actor
        r.save(update_fields=["liberada_en","liberada_por"])
        if i.estado=="suspendida":
            i.estado="finalizada"
            i.causa_salida="reserva_vencida"
            i.fecha_salida=r.fecha_vencimiento+timedelta(days=1)
            i.actualizado_por=actor
            i.version+=1
            i.save()
            evento(i,actor,"liberar_reserva","Vencimiento autorizado de reserva","suspendida",i.fecha_salida)
        cantidad+=1
    return cantidad

@transaction.atomic
def liberar_vencidas(actor):
    bloquear_usuarios(actor,permitir_coordinador=True)
    return liberar_vencidas_bajo_bloqueo(usuario_actual(actor))

def contexto(actor,persona_id,grupos):
    bloquear_usuarios(actor,permitir_coordinador=True)
    actor=usuario_actual(actor)
    liberar_vencidas_bajo_bloqueo(actor)
    persona=Deportista.objects.select_for_update().get(pk=persona_id)
    list(Grupo.objects.select_for_update().filter(pk__in=grupos).order_by("pk"))
    return actor,persona

def crear_bajo_bloqueo(persona,grupo,inicio,actor,motivo,anterior=None,permitir_nivel=False):
    validar_nueva(persona,grupo,inicio,permitir_nivel=permitir_nivel)
    i=Inscripcion.objects.create(deportista=persona,grupo=grupo,fecha_ingreso=inicio,
        inscripcion_anterior=anterior,creado_por=actor,actualizado_por=actor)
    evento(i,actor,"ingreso",motivo)
    return i

@transaction.atomic
def inscribir(persona,grupo,inicio,actor,motivo):
    actor,persona=contexto(actor,persona.pk,[grupo.pk])
    grupo=Grupo.objects.select_related("periodo","nivel","disciplina").get(pk=grupo.pk)
    return crear_bajo_bloqueo(persona,grupo,inicio,actor,motivo)

@transaction.atomic
def cambiar_estado(inscripcion,actor,datos,accion):
    actor,_=contexto(actor,inscripcion.deportista_id,[inscripcion.grupo_id])
    i=Inscripcion.objects.select_for_update().select_related("grupo__periodo","deportista").get(pk=inscripcion.pk)
    version_valida(i,datos)
    hoy=timezone.localdate()
    if not datos.get("motivo"):
        raise ValidationError({"motivo":"Obligatorio."})
    if not i.fecha_ingreso<=hoy<=i.grupo.periodo.fecha_fin or i.estado=="finalizada":
        raise Conflicto("La inscripción no está vigente.")
    anterior=i.estado
    if accion=="suspender":
        if i.estado!="activa":
            raise Conflicto()
        vencimiento=datos.get("fecha_vencimiento")
        if not vencimiento or not hoy<=vencimiento<=i.grupo.periodo.fecha_fin:
            raise ValidationError({"fecha_vencimiento":"Define el último día autorizado dentro del periodo."})
        ReservaCupo.objects.create(inscripcion=i,autorizada_por=actor,fecha_inicio=hoy,fecha_vencimiento=vencimiento,motivo=datos["motivo"])
        i.estado="suspendida"
    elif accion=="reanudar":
        if i.estado!="suspendida":
            raise Conflicto()
        validar_nueva(i.deportista,i.grupo,hoy,excluir=i.pk,permitir_nivel=True)
        i.reservas.filter(liberada_en__isnull=True).update(liberada_en=timezone.now(),liberada_por=actor)
        i.estado="activa"
    elif accion=="retirar":
        if hoy<=i.fecha_ingreso:
            raise ValidationError("El retiro requiere un tramo previo de al menos un día.")
        i.reservas.filter(liberada_en__isnull=True).update(liberada_en=timezone.now(),liberada_por=actor)
        i.estado="finalizada"
        i.fecha_salida=hoy
        i.causa_salida="retiro"
    else:
        raise ValidationError("Acción no válida.")
    i.version+=1
    i.actualizado_por=actor
    i.save()
    evento(i,actor,accion,datos["motivo"],anterior)
    return i

def mensaje_integridad_historial(permite_nivel=False):
    operacion = "El cambio de nivel" if permite_nivel else "El traslado al mismo nivel"
    return (f"{operacion} no puede ejecutarse el mismo día del ingreso por integridad del historial. "
            "La fecha efectiva debe ser posterior a la fecha de ingreso y la inscripción debe estar activa.")


def trasladar_bajo_bloqueo(origen,destino,fecha,actor,motivo,permite_nivel=False):
    if permite_nivel:
        from .compatibilidad_propuestas import bloquear_nivel_antiguo
        bloquear_nivel_antiguo('nivel')
    if origen.estado!="activa" or fecha<=origen.fecha_ingreso or fecha!=timezone.localdate():
        raise ValidationError(mensaje_integridad_historial(permite_nivel))
    if origen.grupo_id==destino.pk or origen.grupo.disciplina_id!=destino.disciplina_id:
        raise ValidationError("Destino distinto y de la misma disciplina requerido.")
    if origen.grupo.nivel_id!=destino.nivel_id and not permite_nivel:
        raise ValidationError("El cambio de nivel requiere propuesta docente y aprobación coordinadora.")
    origen.fecha_salida=fecha
    origen.estado="finalizada"
    origen.causa_salida="cambio_nivel" if permite_nivel else "traslado"
    origen.version+=1
    origen.actualizado_por=actor
    origen.save()
    resultado=crear_bajo_bloqueo(origen.deportista,destino,fecha,actor,motivo,origen,permite_nivel)
    evento(origen,actor,"traslado_origen",motivo,"activa",fecha)
    return resultado

@transaction.atomic
def trasladar(origen,destino,actor,datos):
    actor,_=contexto(actor,origen.deportista_id,[origen.grupo_id,destino.pk])
    origen=Inscripcion.objects.select_for_update().select_related("grupo","deportista").get(pk=origen.pk)
    version_valida(origen,datos)
    return trasladar_bajo_bloqueo(origen,destino,timezone.localdate(),actor,datos["motivo"])

def docente_en_grupo(actor,grupo,fecha):
    return Asignacion.objects.filter(en_fecha(fecha),usuario=actor,tipo="profesor",grupo=grupo).exists()

@transaction.atomic
def proponer(serializer,actor):
    # Mismo bloqueo global que decisiones y cambios de cuenta.
    list(Usuario.objects.select_for_update().order_by("pk"))
    actor=usuario_actual(actor)
    if (not actor.tiene_rol("profesor")):
        raise PermissionDenied("La propuesta pedagógica corresponde al profesor.")
    d=serializer.validated_data
    from .compatibilidad_propuestas import bloquear_nivel_antiguo
    bloquear_nivel_antiguo(d['tipo'])
    persona=d["deportista"]
    destino=Grupo.objects.select_related('periodo','nivel','disciplina').get(pk=d['grupo_destino'].pk)
    fecha=d["fecha_efectiva"]
    from .compatibilidad_propuestas import contexto_docente, validar_destino
    persona,origen=contexto_docente(actor,persona,d['tipo'],fecha,d.get('inscripcion_origen'))
    validar_destino(persona,d['tipo'],fecha,origen,destino)
    if origen:
        d["version_origen"]=origen.version
        d['inscripcion_origen']=origen
    d['deportista']=persona
    d['grupo_destino']=destino
    d.pop("version",None)
    try:
        with transaction.atomic():
            objeto=serializer.save(creado_por=actor,actualizado_por=actor)
    except IntegrityError:
        raise Conflicto('La propuesta entra en conflicto con otra pendiente. Actualiza la consulta.') from None
    registrar(actor,objeto,"proponer",["tipo","grupo_destino","justificacion"])
    return objeto

@transaction.atomic
def resolver(propuesta,actor,datos,aprobar):
    bloquear_usuarios(actor,permitir_coordinador=True)
    actor=usuario_actual(actor)
    p=Propuesta.objects.select_for_update(of=("self",)).select_related("deportista","grupo_destino__periodo","grupo_destino__nivel","grupo_destino__disciplina","inscripcion_origen__grupo","creado_por").get(pk=propuesta.pk)
    version_valida(p,datos)
    if p.estado!="pendiente":
        raise Conflicto("La propuesta ya fue resuelta.")
    if p.tipo=="nivel" and (not actor.tiene_rol("coordinador")):
        raise PermissionDenied("Solo el coordinador activo decide cambios de nivel.")
    if aprobar:
        from .compatibilidad_propuestas import bloquear_nivel_antiguo
        bloquear_nivel_antiguo(p.tipo)
    if not datos.get("resolucion"):
        raise ValidationError({"resolucion":"Obligatoria."})
    if aprobar:
        autor=usuario_actual(p.creado_por)
        if p.fecha_efectiva!=timezone.localdate():
            raise Conflicto("La fecha de propuesta venció; debe presentarse una nueva.")
        actor,persona=contexto(actor,p.deportista_id,[p.grupo_destino_id]+([p.inscripcion_origen.grupo_id] if p.inscripcion_origen_id else []))
        origen=None
        if p.inscripcion_origen_id:
            origen=Inscripcion.objects.select_for_update().select_related('grupo__periodo','grupo__nivel','grupo__disciplina','deportista').get(pk=p.inscripcion_origen_id)
            if origen.version!=p.version_origen:
                raise Conflicto('La inscripción de origen cambió. Revisa la propuesta.')
        from .compatibilidad_propuestas import contexto_docente, validar_destino
        persona,origen=contexto_docente(autor,persona,p.tipo,p.fecha_efectiva,origen,propuesta=p)
        validar_destino(persona,p.tipo,p.fecha_efectiva,origen,p.grupo_destino,propuesta=p)
        if p.tipo=="inscripcion":
            resultado=crear_bajo_bloqueo(persona,p.grupo_destino,p.fecha_efectiva,actor,p.justificacion)
        else:
            resultado=trasladar_bajo_bloqueo(origen,p.grupo_destino,p.fecha_efectiva,actor,p.justificacion,p.tipo=="nivel")
        p.inscripcion_resultante=resultado
    p.estado="aplicada" if aprobar else "rechazada"
    p.resuelta_por=actor
    p.resuelta_en=timezone.now()
    p.resolucion=datos["resolucion"]
    p.actualizado_por=actor
    p.version+=1
    p.save()
    registrar(actor,p,"aprobar_aplicar" if aprobar else "rechazar",["estado","resolucion"])
    return p

def validar_grupo_con_inscritos(grupo):
    if not esquema_disponible():
        return
    hoy=timezone.localdate()
    if grupo.inscripciones.exists():
        from deportistas.permisos import documentos_disponibles, IdentificacionPendiente
        if not documentos_disponibles():
            raise IdentificacionPendiente()
        if not grupo.activo and grupo.inscripciones.filter(fecha_salida__isnull=True,grupo__periodo__fecha_fin__gte=hoy).exists():
            raise ValidationError("Finaliza las inscripciones antes de archivar el grupo.")
        if ocupacion_maxima(grupo,inicio=hoy)>grupo.cupo_maximo:
            raise ValidationError("El cupo es inferior a las inscripciones y reservas existentes.")
        for i in grupo.inscripciones.select_related("grupo__periodo","deportista"):
            a,b=intervalo(i)
            a=max(a,hoy)
            if a>=b:
                continue
            if not grupo.horarios.filter(activo=True).exists():
                raise ValidationError("No se pueden retirar todos los horarios.")
            for otra in i.deportista.inscripciones.exclude(grupo=grupo).select_related("grupo__periodo"):
                c,d=intervalo(otra)
                if max(a,c)<min(b,d) and cruzan(grupo,otra.grupo,max(a,c),min(b,d)):
                    raise ValidationError("El horario entra en conflicto con otra inscripción o reserva.")
