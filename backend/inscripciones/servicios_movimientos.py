"""Ejecución individual institucional, sin endpoints y sin cierre automático."""
from datetime import timedelta
from zoneinfo import ZoneInfo
from uuid import UUID
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError, NotFound
from deportistas.servicios import Conflicto
from .models import Inscripcion, ReservaCupo
from .modelos_ejecucion import RevisionAdministrativa, ResultadoAdministrativo
from .servicios_ejecucion import (autorizado, contexto_bloqueado, obtener_destino_historico,
    validar_evidencia_lectura, relacion_coherente, huella_contexto, guardar_version_administrativa)
from .servicios_ascensos import guardar_validado, registrar_evento


def hoy_bogota():
    return timezone.localtime(timezone.now(), ZoneInfo('America/Bogota')).date()


def movimientos(p):
    return ResultadoAdministrativo.objects.filter(revision__progresion=p, estado='ejecutada').select_related('origen__grupo__periodo', 'destino__grupo__periodo', 'afectacion')


def foto(i):
    return {'id': i.pk, 'version': i.version, 'huella': huella_contexto(i, None),
        'registro': {'deportista': i.deportista_id, 'grupo': i.grupo_id, 'estado': i.estado,
            'ingreso': str(i.fecha_ingreso), 'salida': str(i.fecha_salida) if i.fecha_salida else None,
            'causa': i.causa_salida, 'anterior': i.inscripcion_anterior_id}}


def movimiento_vigente(r, fila_revision=None):
    e = r.evidencia_ejecucion
    origen, destino = foto(r.origen), foto(r.destino)
    if not isinstance(e, dict) or not all(isinstance(e.get(k), dict) for k in ('origen', 'destino')):
        return False
    registros_iguales = all(all(e[k].get(c) == actual[c] for c in ('id', 'version', 'registro'))
        for k, actual in (('origen', origen), ('destino', destino)))
    contexto = (e['origen'].get('huella') == origen['huella'] and e['destino'].get('huella') == destino['huella'])
    ratificado = bool(fila_revision and fila_revision['destino'] == r.destino.grupo_id
        and fila_revision['huella_contexto'] == huella_contexto(r.origen, fila_revision['destino']))
    return (registros_iguales and (contexto or ratificado)
        and r.destino.inscripcion_anterior_id == r.origen_id and r.destino.deportista_id == r.origen.deportista_id
        and r.origen.fecha_salida == r.fecha_efectiva == r.destino.fecha_ingreso)


@transaction.atomic
def ejecutar_reubicacion(actor, revision_id, version, afectacion_id, clave, motivo, fecha=None):
    actor = autorizado(actor)
    if any(type(v) is not int or v < 1 for v in (revision_id, version, afectacion_id)):
        raise ValidationError('Identificadores y versión deben ser enteros positivos.')
    try:
        clave = UUID(str(clave))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('Clave idempotente UUID inválida.') from None
    if not isinstance(motivo, str) or not 1 <= len(motivo.strip()) <= 240:
        raise ValidationError('Motivo obligatorio de hasta 240 caracteres.')
    motivo = motivo.strip()
    revision = RevisionAdministrativa.objects.select_related('progresion').filter(pk=revision_id).first()
    if revision is None:
        raise NotFound('Revisión administrativa no disponible.')
    p = revision.progresion
    if p.estado_decision != 'aprobada':
        raise Conflicto('Solo una progresión pedagógicamente aprobada puede ejecutarse.')
    previo = ResultadoAdministrativo.objects.filter(revision=revision, clave=clave).first()
    if previo:
        if (previo.estado != 'ejecutada' or previo.afectacion_id != afectacion_id or previo.motivo != motivo
                or (fecha is not None and fecha != previo.fecha_efectiva)):
            raise Conflicto('La clave identifica otra operación.')
        if any(not relacion_coherente(p, a) for a in p.afectaciones.select_related('inscripcion__grupo__nivel')):
            raise Conflicto('La identidad institucional cambió; requiere conciliación.')
        f = next((f for f in revision.disposiciones if f['afectacion'] == afectacion_id), None)
        if not movimiento_vigente(previo, f):
            raise Conflicto('El resultado confirmado presenta cambios de contexto; requiere conciliación.')
        return previo
    actor, p = contexto_bloqueado(actor, p.pk, version)
    if p.revisiones_administrativas.order_by('-numero').first().pk != revision.pk:
        raise Conflicto('Revisión administrativa obsoleta.')
    validar_evidencia_lectura(revision.disposiciones)
    # Ampliar el bloqueo a actividades de otras disciplinas para revalidar cruces.
    list(Inscripcion.objects.select_for_update().filter(deportista=p.deportista).order_by('pk'))
    list(ReservaCupo.objects.select_for_update().filter(inscripcion__deportista=p.deportista).order_by('pk'))
    for f in sorted(revision.disposiciones, key=lambda x: x['destino'] or 0):
        if f['destino']:
            obtener_destino_historico(f['destino'], bloquear=True)
    from .servicios_ejecucion import consultar_ejecucion
    resumen = consultar_ejecucion(actor, p.pk)
    if not resumen['plan_completo'] or resumen['discrepancias'] or resumen['inscripciones_nuevas']:
        raise Conflicto('El plan completo requiere revisión vigente antes de ejecutar.')
    fila = next((f for f in revision.disposiciones if f['afectacion'] == afectacion_id), None)
    if not fila or fila['disposicion'] != 'reubicar':
        raise ValidationError('La afectación requiere un destino expresamente dispuesto para reubicar.')
    if ResultadoAdministrativo.objects.filter(revision=revision, afectacion_id=afectacion_id).exists():
        raise Conflicto('Ya existe evidencia en esta fila; registra una revisión expresa antes de ejecutar.')
    realizados = {r.afectacion_id: r for r in movimientos(p)}
    if afectacion_id in realizados:
        raise Conflicto('La afectación ya fue ejecutada.')
    hoy = hoy_bogota()
    if fecha is not None and fecha != hoy:
        raise ValidationError('Solo se permite ejecución en la fecha operativa de Bogotá.')
    origen = Inscripcion.objects.select_related('grupo__periodo', 'grupo__nivel', 'grupo__disciplina', 'deportista').get(pk=fila['origen'])
    if origen.estado != 'activa' or origen.fecha_ingreso >= hoy or origen.reservas.filter(liberada_en__isnull=True).exists():
        raise Conflicto('Se requiere una inscripción activa, sin reserva abierta y con ingreso anterior a hoy; no se reactivan suspensiones ni se anticipan altas futuras.')
    for a in p.afectaciones.exclude(pk=afectacion_id).select_related('inscripcion__grupo__periodo'):
        if a.pk in realizados or a.inscripcion.estado == 'finalizada':
            continue
        i = a.inscripcion
        if i.estado != 'activa' or i.fecha_ingreso > hoy:
            raise Conflicto('Las inscripciones suspendidas o futuras restantes requieren una disposición operativa aún no definida.')
        if not a.excepciones.filter(estado='autorizada', fecha_inicio__lte=hoy, fecha_limite__gte=hoy).exists():
            raise Conflicto('Toda permanencia en el nivel anterior requiere excepción coordinadora vigente, incluso si está pendiente de destino.')
    destino = obtener_destino_historico(fila['destino'], bloquear=True)
    if not (origen.grupo.activo and origen.grupo.periodo.activo and origen.grupo.nivel.activo and origen.grupo.disciplina.activo
            and origen.grupo.periodo.fecha_inicio <= hoy <= origen.grupo.periodo.fecha_fin):
        raise Conflicto('La estructura y periodo de origen no están vigentes.')
    if destino.disciplina_id != p.disciplina_id or destino.nivel_id != p.nivel_destino_id:
        raise Conflicto('Destino ajeno al ascenso aprobado.')
    if origen.grupo.nivel_id != p.nivel_origen_id:
        raise Conflicto('Nivel de origen incompatible.')
    from .consultas_ascensos import validar_nivel_propuesto
    validar_nivel_propuesto(p.nivel_origen, p.nivel_destino)
    from .servicios import crear_bajo_bloqueo, evento
    origen.estado, origen.fecha_salida, origen.causa_salida = 'finalizada', hoy, 'cambio_nivel'
    origen.version += 1
    origen.actualizado_por = actor
    origen.save(update_fields=['estado', 'fecha_salida', 'causa_salida', 'version', 'actualizado_por', 'actualizado_en'])
    # Reutiliza cupos/intervalos/cruces, no la ruta antigua de cambio individual de nivel.
    nueva = crear_bajo_bloqueo(origen.deportista, destino, hoy, actor, motivo, origen, permitir_nivel=True)
    evento(origen, actor, 'traslado_origen', motivo, 'activa', hoy)
    resultado = ResultadoAdministrativo(revision=revision, afectacion_id=afectacion_id, origen=origen,
        destino=nueva, estado='ejecutada', fecha_efectiva=hoy, clave=clave, motivo=motivo, actor=actor,
        version_progresion=p.version + 1, evidencia_ejecucion={'origen': foto(origen), 'destino': foto(nueva)})
    guardar_validado(resultado)
    p.version += 1
    p.actualizado_por = actor
    guardar_version_administrativa(p)
    registrar_evento(p, actor, 'ejecutar_reubicacion', motivo, {'resultado': resultado.pk})
    return resultado
