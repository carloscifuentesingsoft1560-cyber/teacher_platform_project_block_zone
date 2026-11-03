"""Lectura operativa y evidencia de cambios; nunca sincroniza inscripciones."""
import hashlib
import json
from django.utils import timezone
from django.core.exceptions import ValidationError as ErrorModelo
from rest_framework.exceptions import APIException
from .consultas_ascensos import validar_nivel_propuesto
from .modelos_ascensos import ExcepcionPedagogica


def huella(datos):
    return hashlib.sha256(json.dumps(datos, sort_keys=True, default=str).encode()).hexdigest()


def datos_grupo(g):
    return {'id': g.pk, 'disciplina': g.disciplina_id, 'nivel': g.nivel_id, 'periodo': g.periodo_id,
        'activo': g.activo, 'cupo': g.cupo_maximo,
        'periodo_datos': [g.periodo.fecha_inicio.isoformat(), g.periodo.fecha_fin.isoformat(), g.periodo.activo],
        'horarios': list(g.horarios.order_by('pk').values('id', 'dia', 'hora_inicio', 'hora_fin', 'activo'))}


def evidencia_contexto(p):
    from .servicios_ascensos import relevantes
    inscripciones = []
    for i in relevantes(p).order_by('pk').prefetch_related('reservas', 'grupo__horarios'):
        inscripciones.append({'id': i.pk, 'version': i.version, 'estado': i.estado,
            'inicio': i.fecha_ingreso.isoformat(), 'salida': i.fecha_salida,
            'grupo': datos_grupo(i.grupo),
            'reservas': list(i.reservas.order_by('pk').values('id', 'fecha_inicio', 'fecha_vencimiento',
                'autorizada_por_id', 'liberada_en', 'liberada_por_id'))})
    datos = {'persona_activa': p.deportista.estado == 'activo', 'disciplina_activa': p.disciplina.activo,
        'niveles': list(p.disciplina.niveles.order_by('pk').values('id', 'codigo', 'orden', 'activo')),
        'inscripciones': inscripciones}
    # Convertir Date/Time a un formato estable idéntico al almacenado en JSONField.
    return json.loads(json.dumps(datos, sort_keys=True, default=str))


def evidencia_destinos(p):
    return {str(a.pk): json.loads(json.dumps(datos_grupo(a.destino), default=str))
        for a in p.afectaciones.filter(destino__isnull=False).select_related('destino__periodo')}


def advertencias_revision(p):
    from .servicios_ascensos import comprobar_conjunto, verificar_referencia
    from deportistas.permisos import usuario_actual
    avisos = []
    def agregar(codigo, mensaje, bloquea_rechazo=True):
        avisos.append({'codigo': codigo, 'mensaje': mensaje, 'bloquea_aprobar': True,
            'bloquea_rechazar': bloquea_rechazo})
    if p.estado_decision != 'pendiente':
        agregar('decision_resuelta', 'La decisión pedagógica ya fue registrada.')
    try:
        p.full_clean()
    except ErrorModelo:
        agregar('estructura_invalida', 'La estructura de la progresión requiere revisión.')
    try:
        validar_nivel_propuesto(p.nivel_origen, p.nivel_destino)
    except APIException as e:
        agregar('niveles_incompatibles', str(e.detail))
    if p.deportista.estado != 'activo' or not p.disciplina.activo:
        agregar('estructura_inactiva', 'El deportista o la disciplina no están activos.')
    try:
        comprobar_conjunto(p)
    except APIException as e:
        agregar('inscripciones_desactualizadas', str(e.detail))
    evento = p.eventos.filter(tipo='proponer_ascenso').order_by('pk').first()
    base = evento.datos.get('contexto_revision') if evento else None
    if base is None:
        agregar('sin_evidencia_material', 'Falta evidencia histórica suficiente de grupos y reservas; requiere revisión del plan.')
    elif huella(base) != huella(evidencia_contexto(p)):
        agregar('contexto_modificado', 'Cambió el contexto de grupos, periodos, horarios, cupos, reservas o inscripciones desde la propuesta. Revisa el plan; no se sincroniza automáticamente.')
    try:
        verificar_referencia(usuario_actual(p.creado_por), p.inscripcion_referencia)
    except APIException:
        agregar('autor_sin_asignacion', 'El profesor proponente ya no tiene una referencia activa autorizada.', False)
    if p.afectaciones.exclude(inscripcion__grupo__nivel=p.nivel_origen).exists():
        agregar('niveles_mixtos', 'Hay inscripciones de distintos niveles; requiere revisión institucional.', False)
    for a in p.afectaciones.select_related('destino__periodo', 'destino__nivel', 'destino__disciplina'):
        if a.disposicion == 'revisar':
            agregar('disposicion_sin_revisar', f'La inscripción {a.inscripcion_id} necesita una disposición expresa; puede quedar pendiente de reubicación.', False)
        if a.disposicion == 'continuidad' and not any(e.situacion == 'vigente' for e in a.excepciones.all()):
            agregar('excepcion_no_vigente', f'La continuidad de la inscripción {a.inscripcion_id} no tiene excepción vigente.', False)
        if a.destino_id:
            try:
                a.full_clean()
            except ErrorModelo:
                agregar('destino_incompatible', 'Un destino del plan ya no corresponde a la progresión.')
            if not all((a.destino.activo, a.destino.periodo.activo, a.destino.nivel.activo, a.destino.disciplina.activo)):
                agregar('destino_inactivo', 'Un destino del plan ya no está activo.')
            revision = next((ev for ev in p.eventos.filter(tipo='revisar_plan').order_by('-pk')
                if (ev.datos.get('referencia') or {}).get('afectacion') == a.pk), None)
            anterior = revision.datos.get('contexto_destinos', {}).get(str(a.pk)) if revision else None
            if anterior is None or huella(anterior) != huella(json.loads(json.dumps(datos_grupo(a.destino), default=str))):
                agregar('destino_desactualizado', 'El destino cambió o no tiene evidencia de revisión suficiente.')
    return {'version': p.version, 'advertencias': avisos,
        'puede_preparar': not any(a['bloquea_rechazar'] for a in avisos),
        'puede_aprobar': not any(a['bloquea_aprobar'] for a in avisos),
        'puede_rechazar': not any(a['bloquea_rechazar'] for a in avisos),
        'ejecucion_habilitada': False}


def actor_minimo(actor):
    return {'id': actor.pk, 'nombre': actor.get_full_name().strip() or f'Usuario {actor.pk}'} if actor else None


def detalle_revision(p):
    from .servicios_ascensos import relevantes, situacion
    from .serializers_ascensos import AscensoCoordinacionSerializer
    actuales = {i.pk: i for i in relevantes(p)}
    originales = {a.inscripcion_id: a for a in p.afectaciones.select_related('inscripcion__grupo__nivel',
        'inscripcion__grupo__periodo')}
    filas = []
    for pk in sorted(set(actuales) | set(originales)):
        a = originales.get(pk)
        i = actuales.get(pk) or a.inscripcion
        reservas = [{'id': r.pk, 'inicio': r.fecha_inicio, 'vencimiento': r.fecha_vencimiento}
            for r in i.reservas.filter(liberada_en__isnull=True, fecha_inicio__lte=timezone.localdate(), fecha_vencimiento__gte=timezone.localdate())]
        filas.append({'afectacion': a.pk if a else None, 'inscripcion': i.pk, 'version_actual': i.version,
            'version_observada': a.version_observada if a else None, 'en_conjunto_actual': pk in actuales,
            'incorporada_despues': a is None, 'estado': i.estado,
            'situacion_actual': 'finalizada' if i.estado == 'finalizada' else 'periodo_finalizado' if i.grupo.periodo.fecha_fin < timezone.localdate() else situacion(i),
            'situacion_observada': a.situacion_observada if a else None, 'fecha_ingreso': i.fecha_ingreso,
            'fecha_salida': i.fecha_salida, 'grupo': {'id': i.grupo_id, 'codigo': i.grupo.codigo, 'nombre': i.grupo.nombre},
            'nivel': {'id': i.grupo.nivel_id, 'nombre': i.grupo.nivel.nombre},
            'periodo': {'id': i.grupo.periodo_id, 'nombre': i.grupo.periodo.nombre,
                'inicio': i.grupo.periodo.fecha_inicio, 'fin': i.grupo.periodo.fecha_fin},
            'reservas_vigentes': reservas, 'disposicion': a.disposicion if a else 'no_incorporada',
            'destino_propuesto': a.destino_id if a else None, 'motivo': a.motivo if a else '',
            'requiere_revision': a is None or a.disposicion == 'revisar',
            'reubicacion_pendiente': bool(a and a.disposicion == 'pendiente')})
    datos = dict(AscensoCoordinacionSerializer(p).data)
    datos.update(inscripciones=filas, revision=advertencias_revision(p),
        decision={'estado': p.estado_decision, 'responsable': actor_minimo(p.decidida_por),
            'fecha': p.decidida_en, 'resolucion': p.resolucion},
        excepciones=[{'id': e.pk, 'afectacion': e.afectacion_id, 'situacion': e.situacion,
            'motivo': e.motivo, 'inicio': e.fecha_inicio, 'limite': e.fecha_limite,
            'responsable': actor_minimo(e.creado_por), 'revocada_por': actor_minimo(e.revocada_por),
            'revocada_en': e.revocada_en, 'motivo_revocacion': e.motivo_revocacion}
            for e in ExcepcionPedagogica.objects.filter(afectacion__progresion=p).select_related('creado_por', 'revocada_por')],
        eventos=[{'id': e.pk, 'tipo': e.tipo, 'version': e.version, 'fecha': e.registrado_en,
            'responsable': actor_minimo(e.actor), 'motivo': e.motivo} for e in p.eventos.select_related('actor')])
    return datos
