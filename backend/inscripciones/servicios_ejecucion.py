"""Servicios internos administrativos. Ninguno ejecuta ni cierra inscripciones."""
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError
from organizacion.models import Grupo
from organizacion.permisos import es_coordinador_activo
from deportistas.servicios import Conflicto
from .modelos_ascensos import ExcepcionPedagogica
from .modelos_ejecucion import RevisionAdministrativa, ResultadoAdministrativo
from .modelos_ejecucion import validar_disposiciones
from django.core.exceptions import ValidationError as ErrorModelo
from .servicios_ascensos import (bloquear_actor, bloquear_contexto,
    relevantes, situacion, guardar_validado, registrar_evento, progresiones_visibles)


def autorizado(actor):
    actor = bloquear_actor(actor)
    if not actor.tiene_rol('administrador'):
        raise PermissionDenied('Solo administracion vigente puede formalizar el plan administrativo.')
    return actor


def contexto_bloqueado(actor, identificador, version):
    from .modelos_ascensos import ProgresionInstitucional
    from deportistas.models import Deportista
    actor = autorizado(actor)
    p = ProgresionInstitucional.objects.select_for_update().get(pk=identificador)
    Deportista.objects.select_for_update().get(pk=p.deportista_id)
    if p.version != version or p.estado_decision != 'aprobada':
        raise Conflicto('Se requiere una aprobación pedagógica y versión vigente.')
    bloquear_contexto(p)
    return actor, p


def filas_actuales(p, disposiciones):
    if not isinstance(disposiciones, list):
        raise ValidationError('Se requiere una lista completa de disposiciones.')
    if any(not isinstance(d, dict) or not {'afectacion', 'disposicion', 'motivo'} <= set(d)
            or set(d) - {'afectacion', 'disposicion', 'motivo', 'destino'}
            or type(d['afectacion']) is not int or d['afectacion'] < 1
            or not isinstance(d['motivo'], str) or not 1 <= len(d['motivo'].strip()) <= 500
            or (d.get('destino') is not None and (type(d['destino']) is not int or d['destino'] < 1))
            for d in disposiciones):
        raise ValidationError('Disposición incompleta o con tipos incompatibles.')
    afectaciones = {a.pk: a for a in p.afectaciones.select_related('inscripcion__grupo__periodo')}
    ejecutadas = {r.afectacion_id: r for r in ResultadoAdministrativo.objects.filter(
        revision__progresion=p, estado='ejecutada').select_related('destino')}
    ids_actuales = set(relevantes(p).values_list('id', flat=True))
    if ids_actuales - {a.inscripcion_id for a in afectaciones.values()} - {r.destino_id for r in ejecutadas.values()}:
        raise Conflicto('Existen inscripciones nuevas sin afectación institucional; requiere revisión humana.')
    if len(disposiciones) != len(afectaciones) or {d.get('afectacion') for d in disposiciones if isinstance(d, dict)} != set(afectaciones):
        raise ValidationError('La revisión debe incluir cada afectación exactamente una vez.')
    filas = []
    for d in disposiciones:
        if set(d) - {'afectacion', 'disposicion', 'destino', 'motivo'} or not str(d.get('motivo', '')).strip():
            raise ValidationError('Disposición inválida o sin motivo.')
        a = afectaciones[d['afectacion']]
        opcion, destino = d.get('disposicion'), d.get('destino')
        if a.pk in ejecutadas and (opcion != 'reubicar' or destino != ejecutadas[a.pk].destino.grupo_id):
            raise Conflicto('Una ejecución confirmada no puede redefinirse en otra revisión.')
        if opcion not in ('revisar', 'reubicar', 'pendiente', 'continuidad', 'reserva', 'futura'):
            raise ValidationError('Disposición no permitida.')
        if (opcion == 'reubicar') != (destino is not None):
            raise ValidationError('Solo reubicar exige destino.')
        i = a.inscripcion
        if not relacion_coherente(p, a):
            raise Conflicto('Una inscripción afectada cambió de identidad o estructura; requiere revisión institucional.')
        s = 'finalizada' if i.estado == 'finalizada' else situacion(i)
        if opcion in ('reserva', 'futura') and opcion != s:
            raise ValidationError('La disposición no corresponde a la situación actual.')
        if opcion == 'continuidad' and not any(e.situacion == 'vigente' for e in a.excepciones.all()):
            raise ValidationError('Continuidad requiere autorización coordinadora expresa.')
        grupo_destino = obtener_destino_historico(destino, bloquear=True) if destino is not None else None
        if grupo_destino is not None:
            if (grupo_destino.pk == i.grupo_id or grupo_destino.disciplina_id != p.disciplina_id
                    or grupo_destino.nivel_id != p.nivel_destino_id):
                raise ValidationError('Destino incompatible.')
            if not all((grupo_destino.activo, grupo_destino.periodo.activo, grupo_destino.nivel.activo, grupo_destino.disciplina.activo)):
                raise ValidationError('Destino inactivo.')
        filas.append({'afectacion': a.pk, 'origen': i.pk, 'version': i.version, 'situacion': s,
            'deportista': i.deportista_id, 'disciplina': i.grupo.disciplina_id,
            'grupo': i.grupo_id, 'nivel': i.grupo.nivel_id, 'periodo': i.grupo.periodo_id,
            'disposicion': opcion, 'destino': destino, 'motivo': str(d['motivo']).strip(),
            'huella_contexto': huella_contexto(i, destino, grupo_destino=grupo_destino)})
    return sorted(filas, key=lambda d: d['afectacion'])


def relacion_coherente(p, a):
    i = a.inscripcion
    return (a.progresion_id == p.pk and i.deportista_id == p.deportista_id
        and i.grupo.disciplina_id == p.disciplina_id and i.grupo.nivel.disciplina_id == p.disciplina_id
        and p.nivel_origen.disciplina_id == p.disciplina_id and p.nivel_destino.disciplina_id == p.disciplina_id)


def obtener_destino_historico(destino, bloquear=False):
    grupos = Grupo.objects.select_related('periodo', 'nivel', 'disciplina')
    if bloquear:
        grupos = grupos.select_for_update(of=('self',))
    grupo = grupos.filter(pk=destino).first()
    if grupo is None:
        raise Conflicto(f'El destino histórico {destino} ya no existe; requiere una nueva revisión administrativa.')
    return grupo


def validar_evidencia_lectura(filas):
    try:
        validar_disposiciones(filas)
    except ErrorModelo:
        raise Conflicto('Evidencia administrativa incompleta o corrupta; requiere revisión institucional.') from None


def huella_contexto(i, destino, *, grupo_destino=None):
    from .revision_ascensos import datos_grupo, huella
    return huella({'deportista': i.deportista_id, 'disciplina': i.grupo.disciplina_id,
        'grupo': datos_grupo(i.grupo), 'estado': i.estado, 'ingreso': i.fecha_ingreso,
        'catalogo': list(i.grupo.disciplina.niveles.order_by('pk').values('id', 'codigo', 'orden', 'activo')),
        'disciplina_activa': i.grupo.disciplina.activo,
        'salida': i.fecha_salida, 'destino': datos_grupo(grupo_destino or obtener_destino_historico(destino)) if destino else None,
        'reservas': list(i.reservas.order_by('pk').values('id', 'fecha_inicio', 'fecha_vencimiento', 'liberada_en'))})


def guardar_version_administrativa(p):
    # Nunca reserializar la resolución ni sus fechas históricas por un cambio administrativo.
    try:
        p.full_clean()
        p.save(update_fields=['version', 'actualizado_por', 'actualizado_en'])
    except ErrorModelo:
        raise ValidationError('Estructura administrativa inválida; requiere revisión institucional.') from None


@transaction.atomic
def revisar_plan(actor, identificador, version, disposiciones, motivo):
    actor, p = contexto_bloqueado(actor, identificador, version)
    if not motivo or not motivo.strip():
        raise ValidationError('Motivo obligatorio.')
    anterior = p.revisiones_administrativas.order_by('-numero').first()
    revision = RevisionAdministrativa(progresion=p, numero=anterior.numero + 1 if anterior else 1,
        anterior=anterior, actor=actor, motivo=motivo.strip(), version_progresion=p.version + 1,
        disposiciones=filas_actuales(p, disposiciones))
    guardar_validado(revision)
    p.version += 1
    p.actualizado_por = actor
    guardar_version_administrativa(p)
    registrar_evento(p, actor, 'revision_administrativa', motivo.strip(), {'revision': revision.pk})
    return revision


@transaction.atomic
def registrar_resultado(actor, revision_id, version, afectacion_id, clave, motivo, estado='pendiente'):
    revision = RevisionAdministrativa.objects.select_related('progresion').get(pk=revision_id)
    actor = autorizado(actor)
    validar_evidencia_lectura(revision.disposiciones)
    for fila in sorted(revision.disposiciones, key=lambda f: f['destino'] or 0):
        if fila['destino'] is not None:
            obtener_destino_historico(fila['destino'], bloquear=True)
    previo = revision.resultados.filter(clave=clave).first()
    if previo:
        if any(not relacion_coherente(revision.progresion, a) for a in
                revision.progresion.afectaciones.select_related('inscripcion__grupo__nivel')):
            raise Conflicto('La identidad o disciplina de una inscripción cambió; requiere revisión institucional.')
        if (previo.afectacion_id, previo.motivo, previo.estado) != (afectacion_id, motivo.strip(), estado):
            raise Conflicto('La clave ya identifica otro resultado.')
        return previo
    actor, p = contexto_bloqueado(actor, revision.progresion_id, version)
    if p.revisiones_administrativas.order_by('-numero').first().pk != revision.pk:
        raise Conflicto('La revisión no es la vigente.')
    resumen = consultar_ejecucion(actor, p.pk)
    if resumen['discrepancias'] or resumen['inscripciones_nuevas']:
        raise Conflicto('El contexto cambió; registra una revisión administrativa expresa.')
    if estado not in ('pendiente', 'resuelta') or not motivo or not motivo.strip():
        raise ValidationError('B3-B1 no admite ejecución; motivo obligatorio.')
    a = p.afectaciones.filter(pk=afectacion_id).select_related('inscripcion').first()
    if a is None or revision.resultados.filter(afectacion=a).exists():
        raise Conflicto('Afectación inexistente o ya registrada en esta revisión.')
    if estado == 'resuelta' and a.inscripcion.estado != 'finalizada':
        raise ValidationError('Solo una inscripción ya finalizada admite situación final resuelta.')
    resultado = ResultadoAdministrativo(revision=revision, afectacion=a, origen=a.inscripcion,
        estado=estado, clave=clave, motivo=motivo.strip(), actor=actor,
        version_progresion=p.version + 1,
        fecha_efectiva=a.inscripcion.fecha_salida if estado == 'resuelta' else None)
    guardar_validado(resultado)
    p.version += 1
    p.actualizado_por = actor
    guardar_version_administrativa(p)
    registrar_evento(p, actor, 'resultado_administrativo', motivo.strip(), {'resultado': resultado.pk})
    return resultado


def consultar_ejecucion(actor, identificador):
    # El resumen administrativo no se incorpora a la proyección docente.
    from deportistas.permisos import usuario_actual
    actor = usuario_actual(actor)
    if (not actor.tiene_rol('administrador')) and not es_coordinador_activo(actor):
        raise PermissionDenied('Consulta administrativa restringida.')
    p = progresiones_visibles(actor).get(pk=identificador)
    revision = p.revisiones_administrativas.order_by('-numero').first()
    resultados = {r.afectacion_id: r for r in revision.resultados.all()} if revision else {}
    from .servicios_movimientos import movimientos, movimiento_vigente
    ejecutadas = {r.afectacion_id: r for r in movimientos(p)}
    resultados.update(ejecutadas)
    filas = revision.disposiciones if revision else []
    if revision:
        validar_evidencia_lectura(filas)
    nuevas = set(relevantes(p).values_list('pk', flat=True)) - {f['origen'] for f in filas} - {r.destino_id for r in ejecutadas.values()}
    discrepancias = []
    advertencias_destinos = []
    for a in p.afectaciones.select_related('inscripcion'):
        f = next((f for f in filas if f['afectacion'] == a.pk), None)
        if a.pk in ejecutadas:
            if not f or not relacion_coherente(p, a) or not movimiento_vigente(ejecutadas[a.pk], f):
                discrepancias.append(a.pk)
            continue
        grupo_destino = None
        if f and f['destino'] is not None:
            try:
                grupo_destino = obtener_destino_historico(f['destino'])
            except Conflicto:
                discrepancias.append(a.pk)
                advertencias_destinos.append({'afectacion': a.pk, 'destino': f['destino'],
                    'codigo': 'destino_inexistente', 'bloquea_resultado': True,
                    'mensaje': 'El destino histórico ya no existe; registra una nueva revisión administrativa.'})
                continue
            if grupo_destino.disciplina_id != p.disciplina_id or grupo_destino.nivel_id != p.nivel_destino_id:
                codigo = 'destino_incompatible'
            elif not all((grupo_destino.activo, grupo_destino.periodo.activo, grupo_destino.nivel.activo, grupo_destino.disciplina.activo)):
                codigo = 'destino_inactivo'
            elif not grupo_destino.horarios.filter(activo=True).exists():
                codigo = 'destino_sin_horarios'
            else:
                from .servicios import ocupacion_maxima
                from django.utils import timezone
                codigo = 'destino_sin_cupo' if ocupacion_maxima(grupo_destino,
                    inicio=max(timezone.localdate(), grupo_destino.periodo.fecha_inicio)) >= grupo_destino.cupo_maximo else None
            if codigo:
                bloquea = codigo != 'destino_sin_cupo'
                advertencias_destinos.append({'afectacion': a.pk, 'destino': f['destino'], 'codigo': codigo,
                    'bloquea_resultado': bloquea, 'mensaje': 'El destino requiere revisión: ' + codigo.replace('destino_', '').replace('_', ' ') + '.'})
                if bloquea:
                    discrepancias.append(a.pk)
        actual = 'finalizada' if a.inscripcion.estado == 'finalizada' else situacion(a.inscripcion)
        if (not f or not relacion_coherente(p, a)
                or any(f[k] != valor for k, valor in {'origen': a.inscripcion_id,
                    'deportista': a.inscripcion.deportista_id, 'disciplina': a.inscripcion.grupo.disciplina_id,
                    'grupo': a.inscripcion.grupo_id, 'nivel': a.inscripcion.grupo.nivel_id,
                    'periodo': a.inscripcion.grupo.periodo_id}.items())
                or f['version'] != a.inscripcion.version or f['situacion'] != actual
                or f['huella_contexto'] != huella_contexto(a.inscripcion, f['destino'], grupo_destino=grupo_destino)):
            if a.pk not in discrepancias:
                discrepancias.append(a.pk)
    abiertas = ExcepcionPedagogica.objects.filter(afectacion__progresion=p, estado='autorizada').exists()
    pendientes = [f['afectacion'] for f in filas if f['disposicion'] in ('revisar', 'pendiente')
        or f['afectacion'] not in resultados or resultados[f['afectacion']].estado not in ('resuelta', 'ejecutada')]
    continuidades_validas = all(any(e.situacion == 'vigente' for e in ExcepcionPedagogica.objects.filter(
        afectacion_id=f['afectacion'])) for f in filas if f['disposicion'] == 'continuidad')
    completo = bool(filas) and all(f['disposicion'] != 'revisar' for f in filas) and continuidades_validas and not nuevas and not discrepancias
    puede_cerrar = p.estado_decision == 'aprobada' and completo and not pendientes and not abiertas
    ejecutadas = sum(r.estado == 'ejecutada' for r in resultados.values())
    estado = 'ejecutado' if filas and ejecutadas == len(filas) else 'parcialmente_ejecutado' if ejecutadas else 'pendiente'
    return {'progresion': p.pk, 'version': p.version, 'revision': revision.pk if revision else None,
        'estado_ejecucion': estado, 'ejecucion_habilitada': False, 'cerrado': False,
        'plan_completo': completo, 'pendientes': pendientes, 'excepciones_abiertas': abiertas,
        'discrepancias': discrepancias, 'inscripciones_nuevas': sorted(nuevas), 'puede_cerrar': puede_cerrar,
        'advertencias_destinos': advertencias_destinos,
        'afectaciones': [{'afectacion': f['afectacion'], 'disposicion': f['disposicion'],
            'estado_ejecucion': resultados[f['afectacion']].estado if f['afectacion'] in resultados else 'pendiente'} for f in filas],
        'resultados': [{'afectacion': r.afectacion_id, 'estado': r.estado, 'origen': r.origen_id,
            'destino': r.destino_id, 'fecha_efectiva': r.fecha_efectiva} for r in resultados.values()]}
