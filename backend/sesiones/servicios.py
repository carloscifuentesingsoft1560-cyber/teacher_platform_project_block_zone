"""Comandos atómicos. Orden de bloqueo: usuarios por PK, grupo, sesión.

Los bloqueos del profesor serializan el límite diario incluso sin sesiones previas.
La API adapta estos comandos; la ejecución HTTP de tareas continúa bloqueada.
"""
from datetime import date, time
from zoneinfo import ZoneInfo
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied, APIException
from cuentas.models import Usuario
from organizacion.models import Grupo, Asignacion
from organizacion.permisos import puede_gestionar_operacion
from inscripciones.models import Inscripcion
from .models import Sesion, PlanSesion, TareaSesion, Asistencia, EventoSesion, CompetenciaPlan
from .curricular import resolver_plan, validar_ejercicios


class Conflicto(APIException):
    status_code = 409
    default_detail = 'Versión o clave en conflicto.'


def _usuarios(actor, profesor_id):
    usuarios = {u.pk: u for u in Usuario.objects.select_for_update().filter(pk__in=[actor.pk, profesor_id]).order_by('pk')}
    if actor.pk not in usuarios or profesor_id not in usuarios:
        raise PermissionDenied()
    return usuarios[actor.pk], usuarios[profesor_id]


def _autorizar(actor, profesor, grupo, fecha, exigir_docencia=True):
    if not actor.is_active or not (puede_gestionar_operacion(actor) or (actor.pk == profesor.pk and actor.tiene_rol('profesor'))):
        raise PermissionDenied()
    if not exigir_docencia and puede_gestionar_operacion(actor):
        return
    if not profesor.is_active or not profesor.tiene_rol('profesor'):
        raise ValidationError('Profesor no vigente.')
    if not Asignacion.objects.filter(grupo=grupo, usuario=profesor, tipo='profesor', fecha_inicio__lte=fecha).filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha)).exists():
        raise PermissionDenied('Sin asignación docente vigente en la fecha.')


def _reintento(actor, clave, operacion, solicitud):
    evento = EventoSesion.objects.filter(actor=actor, clave=clave).first()
    if evento:
        if evento.operacion != operacion or evento.solicitud != solicitud:
            raise Conflicto()
        return evento.sesion


def _evento(sesion, actor, clave, operacion, solicitud, detalle=None):
    EventoSesion.objects.create(sesion=sesion, actor=actor, clave=clave, operacion=operacion, solicitud=solicitud, version=sesion.version, detalle=detalle or {})


def _franja(grupo, profesor, fecha, inicio, fin, excluir=None):
    if not grupo.activo or not grupo.periodo.activo or not grupo.periodo.fecha_inicio <= fecha <= grupo.periodo.fecha_fin:
        raise ValidationError('Grupo o período no disponible.')
    if fin <= inicio:
        raise ValidationError('Franja inválida.')
    existentes = Sesion.objects.exclude(estado='cancelada').filter(fecha=fecha).exclude(pk=excluir)
    if existentes.filter(profesor=profesor).count() >= 2:
        raise ValidationError('Máximo dos sesiones diarias por profesor.')
    if existentes.filter(Q(profesor=profesor) | Q(grupo=grupo), hora_inicio__lt=fin, hora_fin__gt=inicio).exists():
        raise ValidationError('Franja solapada de grupo o profesor.')


@transaction.atomic
def crear_sesion(*, actor, clave, grupo_id, profesor_id, fecha, hora_inicio, hora_fin):
    fecha = date.fromisoformat(str(fecha))
    inicio, fin = time.fromisoformat(str(hora_inicio)), time.fromisoformat(str(hora_fin))
    actor, profesor = _usuarios(actor, profesor_id)
    grupo = Grupo.objects.select_for_update().get(pk=grupo_id)
    _autorizar(actor, profesor, grupo, fecha)
    datos = dict(grupo=grupo_id, profesor=profesor_id, fecha=str(fecha), inicio=str(inicio), fin=str(fin))
    anterior = _reintento(actor, clave, 'crear', datos)
    if anterior:
        return anterior
    _franja(grupo, profesor, fecha, inicio, fin)
    sesion = Sesion.objects.create(grupo=grupo, profesor=profesor, fecha=fecha, hora_inicio=inicio, hora_fin=fin, creado_por=actor, actualizado_por=actor)
    # Padrón histórico por intervalo [ingreso, salida); no se recalcula al cerrar.
    padron = Inscripcion.objects.filter(grupo=grupo, fecha_ingreso__lte=fecha).filter(Q(fecha_salida__isnull=True) | Q(fecha_salida__gt=fecha))
    Asistencia.objects.bulk_create([Asistencia(sesion=sesion, inscripcion=i) for i in padron])
    _evento(sesion, actor, clave, 'crear', datos)
    return sesion


@transaction.atomic
def comandar(*, actor, sesion_id, version, clave, operacion, datos):
    """Entrada de dominio estricta; datos JSON, autor y timestamps son del servidor."""
    referencia = Sesion.objects.get(pk=sesion_id)
    actor, profesor = _usuarios(actor, referencia.profesor_id)
    grupo = Grupo.objects.select_for_update().get(pk=referencia.grupo_id)
    sesion = Sesion.objects.select_for_update().get(pk=sesion_id)
    _autorizar(actor, profesor, grupo, sesion.fecha, exigir_docencia=operacion in ('planificar', 'realizar'))
    solicitud = dict(sesion=sesion_id, version=version, datos=datos)
    anterior = _reintento(actor, clave, operacion, solicitud)
    if anterior:
        return anterior
    if sesion.version != version:
        raise Conflicto()
    detalle = {}
    if operacion == 'planificar':
        if sesion.estado != 'planificada' or set(datos) - {'objetivo', 'tareas', 'malla_version_id', 'clase_id', 'programa_id', 'fase_curricular_id', 'semana_id', 'competencias_ids'}:
            raise ValidationError('Plan no editable o campos desconocidos.')
        if not datos.get('objetivo', '').strip() or not datos.get('tareas'):
            raise ValidationError('Objetivo y tareas requeridos.')
        referencias, competencias = resolver_plan(actor, grupo, datos)
        validar_ejercicios(actor, grupo, datos['tareas'])
        anterior_plan = sesion.planes.order_by('-numero').first()
        plan = PlanSesion(sesion=sesion, numero=sesion.planes.count()+1, autor=actor, objetivo=datos['objetivo'], revision_anterior=anterior_plan, **referencias)
        plan.full_clean()
        if plan.malla_version_id and (plan.malla_version.estado != 'aprobado' or plan.malla_version.identidad.programa.nivel_id != grupo.nivel_id):
            raise ValidationError('Malla no aprobada o de otro nivel.')
        if plan.clase_id and (not plan.malla_version_id or plan.clase.semana.version_id != plan.malla_version_id):
            raise ValidationError('Clase ajena a la versión de malla.')
        plan.save()
        tareas = []
        fases = []
        for orden, entrada in enumerate(datos['tareas'], 1):
            if set(entrada) - {'fase', 'minutos', 'instrucciones', 'ejercicio_version_id', 'objetivo'}:
                raise ValidationError('Campos de tarea desconocidos.')
            tarea = TareaSesion(plan=plan, orden=orden, **entrada)
            tarea.full_clean()
            if tarea.ejercicio_version_id and (tarea.ejercicio_version.estado != 'aprobado' or tarea.ejercicio_version.disciplina_id != grupo.disciplina_id):
                raise ValidationError('Ejercicio no aprobado o de otra disciplina.')
            tareas.append(tarea)
            fases.append(['inicial', 'central', 'final'].index(tarea.fase))
        minutos = (sesion.hora_fin.hour*60+sesion.hora_fin.minute)-(sesion.hora_inicio.hour*60+sesion.hora_inicio.minute)
        if sum(t.minutos for t in tareas) != minutos or fases != sorted(fases) or set(fases) != {0, 1, 2}:
            raise ValidationError('Las tres fases secuenciales deben completar la duración de la sesión.')
        TareaSesion.objects.bulk_create(tareas)
        CompetenciaPlan.objects.bulk_create([CompetenciaPlan(plan=plan, competencia=c) for c in competencias])
        plan.sellado = True
        plan.save(update_fields=['sellado'])
    elif operacion == 'realizar':
        if sesion.estado != 'planificada' or not sesion.planes.exists() or set(datos) != {'inicio', 'fin'}:
            raise ValidationError('Transición de ejecución inválida.')
        from django.utils.dateparse import parse_datetime
        inicio, fin = parse_datetime(datos['inicio']), parse_datetime(datos['fin'])
        if not inicio or not fin or timezone.is_naive(inicio) or timezone.is_naive(fin) or fin <= inicio or inicio.astimezone(ZoneInfo('America/Bogota')).date() != sesion.fecha:
            raise ValidationError('Intervalo real inválido; requiere zona y fecha de sesión.')
        sesion.estado, sesion.inicio_real, sesion.fin_real = 'realizada', inicio, fin
        sesion.plan_ejecutado = sesion.planes.order_by('-numero').first()
    elif operacion == 'cancelar':
        if sesion.estado != 'planificada' or set(datos) != {'motivo'} or not datos['motivo'].strip():
            raise ValidationError('Cancelación inválida.')
        sesion.estado = 'cancelada'
    elif operacion in ('confirmar_asistencia', 'corregir_asistencia'):
        correccion = operacion == 'corregir_asistencia'
        if sesion.estado != 'realizada' or sesion.asistencia_confirmada != correccion:
            raise ValidationError('Estado de asistencia incompatible.')
        if set(datos) != ({'registros', 'motivo'} if correccion else {'registros'}):
            raise ValidationError('Campos de asistencia inválidos.')
        if correccion and (not puede_gestionar_operacion(actor) or not datos['motivo'].strip()):
            raise PermissionDenied('Corrección extraordinaria requiere gestor y motivo.')
        registros = list(sesion.asistencias.select_for_update().order_by('pk'))
        valores = datos['registros']
        if set(valores) != {str(r.inscripcion_id) for r in registros} or any(v not in {'asistio', 'no_asistio', 'tarde', 'excusa', 'retiro'} for v in valores.values()):
            raise ValidationError('Debe registrar exactamente el padrón completo.')
        detalle = {'anterior': {str(r.inscripcion_id): r.estado for r in registros}, 'evento_anterior': sesion.eventos.filter(operacion__in=['confirmar_asistencia', 'corregir_asistencia']).order_by('-pk').values_list('pk', flat=True).first()}
        for registro in registros:
            registro.estado = valores[str(registro.inscripcion_id)]
        Asistencia.objects.bulk_update(registros, ['estado'])
        sesion.asistencia_confirmada = True
    else:
        raise ValidationError('Operación desconocida.')
    sesion.version += 1
    sesion.actualizado_por = actor
    sesion.full_clean()
    sesion.save()
    _evento(sesion, actor, clave, operacion, solicitud, detalle)
    return sesion
