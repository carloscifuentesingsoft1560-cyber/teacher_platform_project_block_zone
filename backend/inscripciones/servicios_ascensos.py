"""Servicios internos B1. No crean, cierran ni actualizan inscripciones."""
from django.core.exceptions import ValidationError as ErrorModelo
from django.db import transaction, IntegrityError
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from cuentas.models import Usuario
from deportistas.models import Deportista
from deportistas.permisos import usuario_actual, inscripciones_visibles, deportistas_visibles
from deportistas.servicios import Conflicto
from organizacion.models import Grupo, Nivel
from organizacion.permisos import es_coordinador_activo
from auditoria.servicios import registrar
from .models import Inscripcion, Propuesta
from .modelos_ascensos import ProgresionInstitucional, AfectacionInscripcion, ExcepcionPedagogica, EventoProgresion


def bloquear_actor(actor, coordinador=False):
    # Conservar el orden global de los servicios anteriores, incluido relevo.
    list(Usuario.objects.select_for_update().order_by('pk'))
    actor = usuario_actual(actor)
    if coordinador and not es_coordinador_activo(actor):
        raise PermissionDenied('Solo el coordinador activo puede decidir o revisar progresiones.')
    return actor


def progresiones_visibles(actor):
    actor = usuario_actual(actor)
    datos = ProgresionInstitucional.objects.all()
    if (actor.tiene_rol('administrador')) or es_coordinador_activo(actor):
        return datos
    if (actor.tiene_rol('profesor')):
        return datos.filter(creado_por=actor, deportista__in=deportistas_visibles(actor),
            inscripcion_referencia__in=inscripciones_visibles(actor))
    return datos.none()


def leer_progresion(actor, identificador):
    """Proyección docente deliberadamente sin el plan institucional ajeno."""
    actor = usuario_actual(actor)
    p = progresiones_visibles(actor).filter(pk=identificador).first()
    if p is None:
        raise PermissionDenied('Progresión fuera de su ámbito vigente.')
    datos = {'id': p.pk, 'deportista': p.deportista_id, 'disciplina': p.disciplina_id,
        'nivel_origen': p.nivel_origen_id, 'nivel_destino': p.nivel_destino_id,
        'estado_decision': p.estado_decision, 'estado_plan': p.estado_plan, 'version': p.version}
    if (actor.tiene_rol('administrador')) or es_coordinador_activo(actor):
        datos['afectaciones'] = list(p.afectaciones.values('id', 'inscripcion_id', 'version_observada',
            'situacion_observada', 'disposicion', 'destino_id', 'motivo'))
        datos['excepciones'] = [{'id': e.pk, 'afectacion': e.afectacion_id, 'situacion': e.situacion,
            'inicio': e.fecha_inicio, 'limite': e.fecha_limite, 'motivo': e.motivo}
            for e in ExcepcionPedagogica.objects.filter(afectacion__progresion=p)]
    return datos


def guardar_validado(objeto):
    try:
        objeto.save()
    except ErrorModelo as error:
        # Mensaje de dominio sin serializar valores personales de restricciones.
        raise ValidationError('Estructura de progresión inválida o duplicada.') from error


def registrar_evento(p, actor, tipo, motivo, referencia=None):
    from .revision_ascensos import evidencia_contexto, evidencia_destinos
    EventoProgresion.objects.create(progresion=p, actor=actor, tipo=tipo, version=p.version, motivo=motivo,
        datos={'decision': p.estado_decision, 'plan': p.estado_plan, 'referencia': referencia,
            'contexto_revision': evidencia_contexto(p), 'contexto_destinos': evidencia_destinos(p),
            'afectaciones': list(p.afectaciones.values('id', 'inscripcion_id', 'version_observada',
                'situacion_observada', 'disposicion', 'destino_id', 'motivo')),
            'excepciones': [{'id': e.pk, 'estado': e.estado, 'inicio': e.fecha_inicio.isoformat(),
                'limite': e.fecha_limite.isoformat(), 'responsable': e.creado_por_id, 'motivo': e.motivo,
                'revocada_por': e.revocada_por_id,
                'revocada_en': e.revocada_en.isoformat() if e.revocada_en else None,
                'motivo_revocacion': e.motivo_revocacion}
                for e in ExcepcionPedagogica.objects.filter(afectacion__progresion=p)]})
    registrar(actor, p, tipo, ['estado_decision', 'estado_plan', 'version'])


def relevantes(p):
    """Incluye suspendidas sin reserva vigente para disposición explícita."""
    hoy = timezone.localdate()
    return Inscripcion.objects.filter(deportista=p.deportista, grupo__disciplina=p.disciplina,
        fecha_salida__isnull=True, grupo__periodo__fecha_fin__gte=hoy).select_related('grupo__periodo')


def situacion(i):
    if i.fecha_ingreso > timezone.localdate():
        return 'futura'
    if i.estado == 'suspendida':
        return 'reserva' if i.reservas.filter(liberada_en__isnull=True,
            fecha_vencimiento__gte=timezone.localdate()).exists() else 'suspendida'
    return 'activa'


def verificar_referencia(actor, referencia):
    from .consultas_ascensos import referencias_docentes
    if not referencias_docentes(actor).filter(pk=referencia.pk).exists():
        raise PermissionDenied('La propuesta requiere una inscripción activa de su asignación vigente.')


def comprobar_conjunto(p):
    actuales = {i.pk: i for i in relevantes(p)}
    detalles = list(p.afectaciones.all())
    if set(actuales) != {a.inscripcion_id for a in detalles}:
        raise Conflicto('Cambió el conjunto de inscripciones; debe revisarse antes de decidir.')
    for a in detalles:
        i = actuales[a.inscripcion_id]
        if i.version != a.version_observada or situacion(i) != a.situacion_observada:
            raise Conflicto('Una inscripción o su reserva cambió; debe revisarse antes de decidir.')
    return detalles


def actualizar_plan(p):
    detalles = list(p.afectaciones.all())
    # Preparado significa destinos propuestos para todos, nunca viabilidad ni cupo garantizados.
    p.estado_plan = ('preparado' if detalles and all(a.disposicion == 'reubicar' for a in detalles)
        else 'parcial' if any(a.disposicion != 'revisar' for a in detalles) else 'pendiente')


@transaction.atomic
def proponer_progresion(actor, referencia_id, nivel_destino, justificacion):
    actor = bloquear_actor(actor)
    referencia = Inscripcion.objects.select_related('grupo__periodo', 'grupo__nivel', 'deportista').get(pk=referencia_id)
    verificar_referencia(actor, referencia)
    Deportista.objects.select_for_update().get(pk=referencia.deportista_id)
    nivel_destino = Nivel.objects.select_related('disciplina').get(pk=nivel_destino.pk)
    from .consultas_ascensos import validar_nivel_propuesto
    validar_nivel_propuesto(referencia.grupo.nivel, nivel_destino)
    if not justificacion or not justificacion.strip():
        raise ValidationError('Justificación obligatoria.')
    if Propuesta.objects.filter(deportista=referencia.deportista, estado='pendiente', tipo='nivel',
            inscripcion_origen__grupo__disciplina=referencia.grupo.disciplina).exists():
        raise Conflicto('Existe una propuesta anterior de nivel pendiente; resuélvala antes de abrir una progresión.')
    if ProgresionInstitucional.objects.filter(deportista=referencia.deportista,
            disciplina=referencia.grupo.disciplina, estado_decision__in=['pendiente', 'aprobada']).exists():
        raise Conflicto('Existe una progresión abierta para esta disciplina. Solicita revisión a coordinación.')
    p = ProgresionInstitucional(deportista=referencia.deportista, disciplina=referencia.grupo.disciplina,
        nivel_origen=referencia.grupo.nivel, nivel_destino=nivel_destino, periodo=referencia.grupo.periodo,
        inscripcion_referencia=referencia, justificacion=justificacion.strip(), creado_por=actor, actualizado_por=actor)
    if not referencia.deportista.estado == 'activo' or not all((referencia.grupo.activo,
            referencia.grupo.periodo.activo, referencia.grupo.nivel.activo, referencia.grupo.disciplina.activo,
            nivel_destino.activo)):
        raise ValidationError('La persona y la estructura deportiva deben estar activas.')
    try:
        with transaction.atomic():
            guardar_validado(p)
    except IntegrityError as error:
        if getattr(getattr(error, '__cause__', None), 'diag', None) is not None and error.__cause__.diag.constraint_name == 'ascenso_abierto_unico':
            raise Conflicto('Existe una progresión abierta para esta disciplina. Solicita revisión a coordinación.') from None
        raise
    for i in relevantes(p):
        guardar_validado(AfectacionInscripcion(progresion=p, inscripcion=i, version_observada=i.version,
            situacion_observada=situacion(i)))
    registrar_evento(p, actor, 'proponer_ascenso', justificacion.strip())
    return p


def obtener_bloqueada(actor, identificador, version):
    actor = bloquear_actor(actor, coordinador=True)
    p = ProgresionInstitucional.objects.select_for_update().get(pk=identificador)
    Deportista.objects.select_for_update().get(pk=p.deportista_id)
    if p.version != version:
        raise Conflicto()
    if p.estado_decision == 'rechazada' or p.estado_plan == 'ejecutado':
        raise Conflicto('La progresión está cerrada.')
    return actor, p


def bloquear_contexto(p, destino_id=None):
    """Orden compartido por revisión y decisión; no modifica el contexto deportivo."""
    ids = set(relevantes(p).values_list('pk', flat=True)) | set(p.afectaciones.values_list('inscripcion_id', flat=True))
    inscripciones = list(Inscripcion.objects.select_for_update().filter(pk__in=ids).order_by('pk'))
    grupos = {i.grupo_id for i in inscripciones} | set(p.afectaciones.exclude(destino=None).values_list('destino_id', flat=True))
    if destino_id:
        grupos.add(destino_id)
    list(Grupo.objects.select_for_update().filter(pk__in=grupos).order_by('pk'))
    from .models import ReservaCupo
    list(ReservaCupo.objects.select_for_update().filter(inscripcion_id__in=ids).order_by('pk'))


@transaction.atomic
def disponer_inscripcion(actor, identificador, version, afectacion_id, disposicion, motivo, destino_id=None):
    actor, p = obtener_bloqueada(actor, identificador, version)
    if not motivo or not motivo.strip():
        raise ValidationError('Motivo obligatorio.')
    if p.estado_decision != 'pendiente':
        raise Conflicto('La preparación para revisión requiere una progresión pendiente de decisión.')
    bloquear_contexto(p, destino_id)
    from .revision_ascensos import advertencias_revision
    bloqueos = [a['mensaje'] for a in advertencias_revision(p)['advertencias'] if a['bloquea_rechazar']]
    if bloqueos:
        raise Conflicto(' '.join(dict.fromkeys(bloqueos)))
    comprobar_conjunto(p)
    a = p.afectaciones.select_for_update().filter(pk=afectacion_id).first()
    if a is None:
        from rest_framework.exceptions import NotFound
        raise NotFound('Afectación no disponible en esta progresión.')
    if disposicion not in dict(AfectacionInscripcion._meta.get_field('disposicion').choices):
        raise ValidationError('Disposición no permitida.')
    if (disposicion == 'reubicar') != (destino_id is not None):
        raise ValidationError('Solo reubicar exige y admite un destino propuesto.')
    anterior = {'disposicion': a.disposicion, 'destino': a.destino_id, 'motivo': a.motivo}
    if disposicion == 'continuidad':
        if not any(e.situacion == 'vigente' for e in a.excepciones.all()):
            raise ValidationError('Continuidad requiere una excepción temporal vigente.')
    if disposicion == 'reserva' and a.situacion_observada != 'reserva':
        raise ValidationError('La inscripción no tiene una reserva vigente observada.')
    if disposicion == 'futura' and a.situacion_observada != 'futura':
        raise ValidationError('La inscripción no es futura.')
    a.disposicion, a.destino_id, a.motivo = disposicion, destino_id, motivo.strip()
    if destino_id:
        destino = Grupo.objects.select_related('periodo', 'nivel', 'disciplina').filter(pk=destino_id).first()
        if destino is None:
            from rest_framework.exceptions import NotFound
            raise NotFound('Destino no disponible.')
        if not all((destino.activo, destino.periodo.activo, destino.nivel.activo, destino.disciplina.activo)):
            raise ValidationError('Destino inactivo.')
        origen = a.inscripcion
        if (max(timezone.localdate(), origen.fecha_ingreso, origen.grupo.periodo.fecha_inicio,
                destino.periodo.fecha_inicio) > min(origen.grupo.periodo.fecha_fin, destino.periodo.fecha_fin)
                or not destino.horarios.filter(activo=True).exists()):
            raise ValidationError('Destino sin vigencia temporal común o sin horarios activos.')
    guardar_validado(a)
    actualizar_plan(p)
    p.version += 1
    p.actualizado_por = actor
    guardar_validado(p)
    registrar_evento(p, actor, 'revisar_plan', motivo.strip(), {
        'afectacion': a.pk, 'disposicion': disposicion, 'anterior': anterior})
    return p


@transaction.atomic
def decidir_progresion(actor, identificador, version, aprobar, resolucion):
    actor, p = obtener_bloqueada(actor, identificador, version)
    if p.estado_decision != 'pendiente':
        raise Conflicto('La decisión pedagógica ya fue registrada.')
    if not resolucion or not resolucion.strip():
        raise ValidationError('Resolución obligatoria.')
    if aprobar:
        verificar_referencia(usuario_actual(p.creado_por), p.inscripcion_referencia)
    # Todos los escritores de la aplicación empiezan por el bloqueo global de usuarios.
    # Bloquear también las filas implicadas antes de reconstruir la evidencia.
    bloquear_contexto(p)
    from .revision_ascensos import advertencias_revision
    revision = advertencias_revision(p)
    bloqueos = [a['mensaje'] for a in revision['advertencias'] if a['bloquea_aprobar' if aprobar else 'bloquea_rechazar']]
    if bloqueos:
        # Conservar 400 de disposición incompleta previsto por B1; cambios materiales son 409.
        if aprobar and all(a['codigo'] in ('disposicion_sin_revisar',) for a in revision['advertencias']):
            raise ValidationError(bloqueos[0])
        raise Conflicto(' '.join(dict.fromkeys(bloqueos)))
    if aprobar:
        verificar_referencia(usuario_actual(p.creado_por), p.inscripcion_referencia)
        detalles = comprobar_conjunto(p)
        if any(a.disposicion == 'revisar' for a in detalles):
            raise ValidationError('Cada inscripción necesita una disposición expresa; puede indicar reubicación pendiente.')
        for a in detalles:
            if a.disposicion == 'continuidad' and not any(e.situacion == 'vigente' for e in a.excepciones.all()):
                raise Conflicto('La excepción temporal ya no está vigente.')
        if relevantes(p).exclude(grupo__nivel=p.nivel_origen).exists():
            raise Conflicto('Hay inscripciones de niveles distintos; requiere revisión institucional antes de aprobar.')
    p.estado_decision = 'aprobada' if aprobar else 'rechazada'
    if not aprobar:
        for e in ExcepcionPedagogica.objects.filter(afectacion__progresion=p, estado='autorizada'):
            e.estado, e.actualizado_por = 'revocada', actor
            e.revocada_por, e.revocada_en, e.motivo_revocacion = actor, timezone.now(), resolucion.strip()
            e.version += 1
            guardar_validado(e)
        for a in p.afectaciones.filter(disposicion='continuidad'):
            a.disposicion = 'pendiente'
            guardar_validado(a)
        actualizar_plan(p)
    p.decidida_por, p.decidida_en, p.resolucion = actor, timezone.now(), resolucion.strip()
    p.actualizado_por = actor
    p.version += 1
    guardar_validado(p)
    registrar_evento(p, actor, 'aprobar_ascenso' if aprobar else 'rechazar_ascenso', resolucion.strip())
    return p


@transaction.atomic
def autorizar_excepcion(actor, identificador, version, afectacion_id, motivo, inicio, limite):
    actor, p = obtener_bloqueada(actor, identificador, version)
    comprobar_conjunto(p)
    if not motivo or not motivo.strip() or inicio is None or limite is None:
        raise ValidationError('Motivo, inicio y vencimiento son obligatorios.')
    a = p.afectaciones.select_for_update().get(pk=afectacion_id)
    if a.situacion_observada != 'activa':
        raise ValidationError('La permanencia temporal requiere inscripción activa; no reactiva reservas ni anticipa ingresos.')
    if inicio < timezone.localdate():
        raise ValidationError('No se autorizan excepciones retroactivas.')
    if a.excepciones.filter(estado='autorizada').exists():
        raise Conflicto('Revoque la excepción anterior antes de registrar otra.')
    e = ExcepcionPedagogica(afectacion=a, motivo=motivo.strip(), fecha_inicio=inicio, fecha_limite=limite,
        creado_por=actor, actualizado_por=actor)
    guardar_validado(e)
    p.version += 1
    p.actualizado_por = actor
    guardar_validado(p)
    registrar_evento(p, actor, 'autorizar_excepcion', motivo.strip(), {'excepcion': e.pk})
    return e


@transaction.atomic
def revocar_excepcion(actor, identificador, version, excepcion_id, motivo):
    actor, p = obtener_bloqueada(actor, identificador, version)
    if not motivo or not motivo.strip():
        raise ValidationError('Motivo obligatorio.')
    e = ExcepcionPedagogica.objects.select_for_update().get(pk=excepcion_id, afectacion__progresion=p)
    if e.estado != 'autorizada':
        raise Conflicto('La excepción ya fue revocada.')
    e.estado, e.actualizado_por = 'revocada', actor
    e.revocada_por, e.revocada_en, e.motivo_revocacion = actor, timezone.now(), motivo.strip()
    e.version += 1
    guardar_validado(e)
    a = e.afectacion
    if a.disposicion == 'continuidad':
        a.disposicion = 'pendiente'
        guardar_validado(a)
    actualizar_plan(p)
    p.version += 1
    p.actualizado_por = actor
    guardar_validado(p)
    registrar_evento(p, actor, 'revocar_excepcion', motivo.strip(), {'excepcion': e.pk})
    return e
