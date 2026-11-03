"""Registro retrospectivo, cierre de asistencia y corrección administrativa.

No se infiere permiso de práctica de un consentimiento ni de la asistencia.
"""
from zoneinfo import ZoneInfo
from django.db import transaction
from django.db.models import Q, Count
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError, PermissionDenied
from organizacion.models import Grupo
from inscripciones.models import Inscripcion
from auditoria.servicios import registrar
from .models import Sesion, Asistencia, PlanSesion, EjecucionSesion, ActividadEjecutada, CorreccionAsistencia, EventoSesion
from .permisos import sesiones_visibles, asignaciones_actuales
from .servicios import _usuarios, _reintento, _evento, Conflicto

ESTADOS = ('asistio', 'no_asistio', 'tarde', 'excusa', 'retiro')


def elegibles(sesion):
    return Inscripcion.objects.filter(grupo_id=sesion.grupo_id, fecha_ingreso__lte=sesion.fecha).filter(Q(fecha_salida__isnull=True) | Q(fecha_salida__gt=sesion.fecha)).select_related('deportista').order_by('pk')


def padron_actual(sesion):
    filas = list(elegibles(sesion))
    personas = [i.deportista_id for i in filas]
    if len(set(personas)) != len(personas):
        raise ValidationError('Inscripciones superpuestas para un deportista: revisar matrícula antes del cierre.')
    return filas


def exigir_padron(sesion):
    actual = {(i.pk, i.deportista_id) for i in padron_actual(sesion)}
    guardado = set(sesion.asistencias.values_list('inscripcion_id', 'deportista_id'))
    if actual != guardado:
        raise ValidationError('Cambió la matrícula de referencia; prepara explícitamente el padrón antes de guardar o cerrar.')


def verificar_autorizacion_funcional(sesion, ejecucion):
    """Frontera cerrada: falta fuente institucional competente, no hay bypass cliente."""
    raise PermissionDenied('Validación a realizada pendiente: no existe contrato institucional de autorización funcional por participante y actividad.')


def datos_asistencia(sesion):
    guardado = list(sesion.asistencias.select_related('deportista').order_by('pk'))
    filas = guardado if sesion.asistencia_confirmada else padron_actual(sesion)
    estados = {a.inscripcion_id: a.estado for a in guardado}
    participantes = []
    for fila in filas:
        persona = fila.deportista
        inscripcion_id = fila.inscripcion_id if isinstance(fila, Asistencia) else fila.pk
        participantes.append(dict(inscripcion=inscripcion_id, deportista=persona.pk, nombres=persona.nombres, apellidos=persona.apellidos, estado=estados.get(inscripcion_id, '')))
    return dict(version=sesion.version, cerrada=sesion.asistencia_confirmada, requiere_preparacion=not sesion.asistencia_confirmada and {(i.pk, i.deportista_id) for i in filas} != {(a.inscripcion_id, a.deportista_id) for a in guardado}, participantes=participantes)


def resumen_asistencia(sesion):
    conteos = {estado: 0 for estado in ('', *ESTADOS)}
    for fila in sesion.asistencias.values('estado').annotate(total=Count('pk')):
        conteos[fila['estado']] = fila['total']
    requiere = not sesion.asistencia_confirmada and {(i.pk, i.deportista_id) for i in padron_actual(sesion)} != set(sesion.asistencias.values_list('inscripcion_id', 'deportista_id'))
    return dict(version=sesion.version, cerrada=sesion.asistencia_confirmada, requiere_preparacion=requiere, total=sum(conteos.values()), sin_registrar=conteos.pop(''), estados=conteos)


def exigir_docente(actor, sesion):
    if actor.pk != sesion.profesor_id or not actor.is_active or not actor.tiene_rol('profesor'):
        raise PermissionDenied('Se requiere el profesor responsable con facultad docente vigente.')
    if not asignaciones_actuales(actor).filter(grupo_id=sesion.grupo_id, fecha_inicio__lte=sesion.fecha).filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=sesion.fecha)).exists():
        raise PermissionDenied('Asignación docente revocada o fuera de fecha.')


def registrar_ejecucion(sesion, actor, datos):
    plan = get_object_or_404(PlanSesion, pk=datos['plan'], sesion=sesion, sellado=True)
    inicio, fin = parse_datetime(datos['inicio']), parse_datetime(datos['fin'])
    if not inicio or not fin or timezone.is_naive(inicio) or timezone.is_naive(fin) or fin <= inicio or fin > timezone.now() or inicio.astimezone(ZoneInfo('America/Bogota')).date() != sesion.fecha:
        raise ValidationError('Intervalo real inválido, futuro o sin zona; el inicio debe corresponder al día de sesión.')
    if (fin-inicio).total_seconds() > 86400:
        raise ValidationError('El intervalo de sesión no puede superar 24 horas.')
    actividades = datos['actividades']
    tareas = set(plan.tareas.values_list('pk', flat=True))
    if len(actividades) != len(tareas) or {a['tarea'] for a in actividades} != tareas:
        raise ValidationError('Registra exactamente todas las tareas del plan elegido, sin duplicados ni tareas ajenas.')
    for a in actividades:
        resultado = a['resultado']
        if resultado == 'omitida':
            if a['minutos'] != 0 or not a.get('motivo_omision', '').strip() or a.get('adaptacion_metodologica'):
                raise ValidationError('Actividad omitida requiere cero minutos y motivo, sin adaptación ejecutada.')
        elif resultado in ('realizada', 'modificada'):
            if a['minutos'] < 1 or not a.get('descripcion', '').strip() or a.get('motivo_omision'):
                raise ValidationError('Actividad ejecutada requiere duración y descripción, sin motivo de omisión.')
            if (resultado == 'modificada') != bool(a.get('adaptacion_metodologica', '').strip()):
                raise ValidationError('Una adaptación ejecutada debe marcarse como actividad modificada y describirse.')
        else:
            raise ValidationError('Resultado de actividad inválido.')
    if sum(a['minutos'] for a in actividades)*60 > (fin-inicio).total_seconds():
        raise ValidationError('Las actividades exceden la duración real registrada.')
    existente = EjecucionSesion.objects.filter(sesion=sesion).first()
    if existente and existente.finalizada_en:
        raise ValidationError('La ejecución registrada ya está finalizada.')
    ejecucion, _ = EjecucionSesion.objects.update_or_create(sesion=sesion, defaults=dict(plan=plan, inicio=inicio, fin=fin, observaciones=datos.get('observaciones', ''), incidencias_pedagogicas=datos.get('incidencias_pedagogicas', '')), create_defaults=dict(plan=plan, inicio=inicio, fin=fin, observaciones=datos.get('observaciones', ''), incidencias_pedagogicas=datos.get('incidencias_pedagogicas', ''), creada_por=actor))
    ejecucion.actividades.all().delete()
    ActividadEjecutada.objects.bulk_create([ActividadEjecutada(ejecucion=ejecucion, tarea_id=a['tarea'], **{k:v for k,v in a.items() if k != 'tarea'}) for a in actividades])
    return ejecucion


@transaction.atomic
def operar(*, actor, sesion_id, version, clave, operacion, datos):
    referencia = get_object_or_404(sesiones_visibles(actor), pk=sesion_id)
    actor, _ = _usuarios(actor, referencia.profesor_id)
    Grupo.objects.select_for_update().get(pk=referencia.grupo_id)
    sesion = get_object_or_404(sesiones_visibles(actor).select_for_update(), pk=sesion_id)
    if operacion == 'corregir_asistencia':
        if not actor.is_active or not actor.tiene_rol('administrador'):
            raise PermissionDenied('La corrección excepcional exige administración vigente; coordinación no basta.')
    else:
        exigir_docente(actor, sesion)
    solicitud = dict(sesion=sesion.pk, version=version, datos=datos)
    previo = _reintento(actor, clave, operacion, solicitud)
    if previo:
        return previo
    if sesion.version != version:
        raise Conflicto()
    if sesion.estado == 'cancelada':
        raise ValidationError('Sesión cancelada.')
    detalle = {}
    if operacion == 'preparar_asistencia':
        if sesion.asistencia_confirmada:
            raise ValidationError('Padrón cerrado e inmutable.')
        filas = padron_actual(sesion)
        esperadas = {i.pk for i in filas}
        personas = {i.pk: i.deportista_id for i in filas}
        if any(a.inscripcion_id in personas and personas[a.inscripcion_id] != a.deportista_id for a in sesion.asistencias.all()):
            raise ValidationError('Cambió la identidad de una inscripción histórica; revisar matrícula sin reasignar asistencia.')
        sobrantes = sesion.asistencias.exclude(inscripcion_id__in=esperadas)
        if sobrantes.exclude(estado='').exists():
            raise ValidationError('Hay registros guardados fuera del padrón; revisar matrícula sin perder asistencia.')
        detalle = {'padron_anterior': list(sesion.asistencias.values_list('inscripcion_id', flat=True)), 'padron_resultante': sorted(esperadas)}
        sobrantes.delete()
        existentes = set(sesion.asistencias.values_list('inscripcion_id', flat=True))
        Asistencia.objects.bulk_create([Asistencia(sesion=sesion, inscripcion=i, deportista_id=i.deportista_id) for i in filas if i.pk not in existentes])
    elif operacion == 'guardar_asistencia':
        if sesion.asistencia_confirmada:
            raise ValidationError('Asistencia cerrada: utiliza corrección administrativa excepcional.')
        exigir_padron(sesion)
        registros = list(sesion.asistencias.select_for_update().order_by('pk'))
        valores = datos['registros']
        if set(valores) != {str(a.inscripcion_id) for a in registros} or any(v not in ('', *ESTADOS) for v in valores.values()):
            raise ValidationError('Registra exactamente el padrón de la sesión con estados válidos.')
        for registro in registros:
            registro.estado = valores[str(registro.inscripcion_id)]
        Asistencia.objects.bulk_update(registros, ['estado'])
    elif operacion in ('cerrar_asistencia', 'finalizar_ejecucion'):
        if sesion.fecha > timezone.localdate():
            raise ValidationError('No se cierra asistencia ni ejecución de una fecha futura.')
        if operacion == 'cerrar_asistencia' and sesion.asistencia_confirmada:
            raise ValidationError('La asistencia ya está cerrada.')
        if not sesion.asistencia_confirmada:
            exigir_padron(sesion)
            if sesion.asistencias.filter(estado='').exists():
                raise ValidationError('Completa el estado de todos los participantes antes del cierre.')
            sesion.asistencia_confirmada = True
        if operacion == 'finalizar_ejecucion':
            ejecucion = get_object_or_404(EjecucionSesion.objects.select_for_update(), sesion=sesion)
            if ejecucion.finalizada_en:
                raise ValidationError('La ejecución ya está finalizada.')
            ejecucion.finalizada_en = timezone.now()
            ejecucion.finalizada_por = actor
            # La asistencia se guarda primero; el trigger de cierre verifica ambas.
            sesion.save(update_fields=['asistencia_confirmada'])
            ejecucion.save(update_fields=['finalizada_en', 'finalizada_por'])
            detalle = {'plan': ejecucion.plan_id, 'validacion_funcional': 'pendiente'}
    elif operacion == 'guardar_ejecucion':
        if sesion.estado != 'planificada':
            raise ValidationError('La sesión ya tiene una ejecución validada.')
        ejecucion = registrar_ejecucion(sesion, actor, datos)
        detalle = {'plan': ejecucion.plan_id}
    elif operacion == 'validar_realizada':
        ejecucion = get_object_or_404(EjecucionSesion, sesion=sesion, finalizada_en__isnull=False)
        if sesion.estado != 'planificada' or not sesion.asistencia_confirmada:
            raise ValidationError('Se requiere ejecución finalizada y asistencia cerrada sin validación previa incompatible.')
        verificar_autorizacion_funcional(sesion, ejecucion)
        sesion.estado = 'realizada'
        sesion.plan_ejecutado = ejecucion.plan
        sesion.inicio_real, sesion.fin_real = ejecucion.inicio, ejecucion.fin
    elif operacion == 'corregir_asistencia':
        if not sesion.asistencia_confirmada:
            raise ValidationError('La corrección exige asistencia cerrada.')
        asistencia = get_object_or_404(Asistencia.objects.select_for_update(), sesion=sesion, deportista_id=datos['deportista'])
        if asistencia.estado != datos['anterior']:
            raise Conflicto('El valor anterior no coincide con la asistencia actual.')
        if datos['nuevo'] not in ESTADOS or datos['nuevo'] == asistencia.estado or not datos['motivo'].strip():
            raise ValidationError('Se requiere otro estado válido y motivo obligatorio.')
        anterior_evento = asistencia.correcciones.order_by('-pk').values_list('evento_id', flat=True).first() or sesion.eventos.filter(operacion__in=['cerrar_asistencia', 'finalizar_ejecucion', 'confirmar_asistencia']).order_by('-pk').values_list('pk', flat=True).first()
        detalle = {'deportista': asistencia.deportista_id, 'inscripcion': asistencia.inscripcion_id, 'anterior': asistencia.estado, 'nuevo': datos['nuevo'], 'evento_anterior': anterior_evento}
        # El trigger de corrección cambia la proyección de asistencia, nunca un UPDATE ordinario.
        sesion.version += 1
        sesion.actualizado_por = actor
        sesion.save()
        _evento(sesion, actor, clave, operacion, solicitud, detalle)
        evento = EventoSesion.objects.get(actor=actor, clave=clave)
        correccion = CorreccionAsistencia.objects.create(asistencia=asistencia, anterior=datos['anterior'], nuevo=datos['nuevo'], motivo=datos['motivo'], actor=actor, evento=evento)
        registrar(actor, correccion, 'corregir_asistencia', ['anterior', 'nuevo', 'motivo'])
        return sesion
    else:
        raise ValidationError('Operación no disponible.')
    sesion.version += 1
    sesion.actualizado_por = actor
    sesion.full_clean()
    sesion.save()
    _evento(sesion, actor, clave, operacion, solicitud, detalle)
    return sesion
