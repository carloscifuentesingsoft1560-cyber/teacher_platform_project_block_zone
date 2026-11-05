"""Comandos internos de expedientes pendientes; no conceden permisos ni aprobaciones."""
from datetime import timezone as utc
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from auditoria.servicios import registrar
from deportistas.servicios import Conflicto
from .models import (Usuario, EnlaceIdentidad, MandatoInstitucional, EventoMandatoInstitucional,
                     AcreditacionEmisora, EventoAcreditacionEmisora)
from .servicios_roles import bloquear_admin


def _uuid(valor):
    try:
        valor = UUID(str(valor))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('Se requiere referencia opaca UUID v4.')
    if valor.version != 4:
        raise ValidationError('Se requiere referencia opaca UUID v4.')
    return valor


def _id(valor):
    if type(valor) is not int or valor < 1:
        raise ValidationError('Identificador o versión no válido.')
    return valor


def _enlace(enlace_id):
    enlace = EnlaceIdentidad.objects.select_for_update().filter(pk=enlace_id, vigente=True, usuario__is_active=True).first()
    if enlace is None or enlace.usuario_id is None:
        raise PermissionDenied('Se requiere identidad de cuenta acreditada y vigente.')
    return enlace


def _actor(actor):
    # Mantener el orden global de usuarios antes de identidades y expedientes.
    bloquear_admin(actor)
    actual = Usuario.objects.get(pk=actor.pk)
    enlace = EnlaceIdentidad.objects.filter(usuario=actual, vigente=True).first()
    if enlace is None:
        raise PermissionDenied('Se requiere identidad acreditada del registrador.')
    return actual, _enlace(enlace.pk)


def _registro(actor, enlace):
    return dict(registrada_por=actor, persona_registradora_id=enlace.persona_id,
                enlace_registrador=enlace, version_enlace_registrador=enlace.version,
                evidencia_registrador=enlace.evidencia)


def _datos(motivo, referencia_evidencia, desde, hasta):
    if not isinstance(motivo, str) or not motivo.strip() or len(motivo) > 500:
        raise ValidationError('Motivo requerido, máximo 500 caracteres.')
    for fecha in (desde, hasta):
        if fecha is not None and (not hasattr(fecha, 'utcoffset') or timezone.is_naive(fecha)):
            raise ValidationError('Indica fecha y hora con zona explícita.')
    if desde is None or (hasta is not None and hasta <= desde):
        raise ValidationError('Intervalo propuesto inválido.')
    return dict(motivo=motivo.strip(), referencia_evidencia=str(_uuid(referencia_evidencia)),
                vigente_desde_propuesta=desde.astimezone(utc.utc).isoformat(),
                vigente_hasta_propuesta=hasta.astimezone(utc.utc).isoformat() if hasta else None)


def _reintento(actor, enlace, clave, solicitud):
    for modelo in (EventoMandatoInstitucional, EventoAcreditacionEmisora):
        evento = modelo.objects.filter(actor=actor, clave=clave).first()
        if evento:
            if evento.persona_actor_id != enlace.persona_id:
                raise PermissionDenied('La identidad actual no coincide con el autor histórico.')
            if evento.solicitud != solicitud:
                raise Conflicto('Clave reutilizada con otra solicitud.')
            return evento
    return None


def _evento(modelo, padre, actor, enlace, clave, accion, solicitud, datos, anterior=None):
    from django.utils.dateparse import parse_datetime
    datos = dict(datos)
    datos['vigente_desde_propuesta'] = parse_datetime(datos['vigente_desde_propuesta'])
    if datos['vigente_hasta_propuesta']:
        datos['vigente_hasta_propuesta'] = parse_datetime(datos['vigente_hasta_propuesta'])
    evento = modelo.objects.create(**padre, numero=anterior.numero+1 if anterior else 1,
        anterior=anterior, accion=accion, actor=actor, persona_actor_id=enlace.persona_id,
        enlace_actor=enlace, version_enlace_actor=enlace.version, evidencia_actor=enlace.evidencia,
        clave=clave, solicitud=solicitud, **datos)
    registrar(actor, evento, accion, ['numero', 'accion', 'referencia_evidencia'])
    return evento


@transaction.atomic
def proponer_mandato(*, actor, clave, enlace_identidad_id, disciplina_id, alcance_propuesto,
                     motivo, referencia_evidencia, vigente_desde_propuesta, vigente_hasta_propuesta=None):
    actor, enlace = _actor(actor)
    clave = _uuid(clave)
    datos = _datos(motivo, referencia_evidencia, vigente_desde_propuesta, vigente_hasta_propuesta)
    if not isinstance(alcance_propuesto, str) or not alcance_propuesto.strip() or len(alcance_propuesto) > 240:
        raise ValidationError('Alcance propuesto requerido, máximo 240 caracteres.')
    solicitud = dict(tipo='mandato', operacion='propuesta', enlace=_id(enlace_identidad_id),
        disciplina=_id(disciplina_id), alcance=alcance_propuesto.strip(), datos=datos)
    previo = _reintento(actor, enlace, clave, solicitud)
    if previo:
        return previo
    titular = _enlace(enlace_identidad_id)
    mandato = MandatoInstitucional.objects.create(**_registro(actor, enlace),
        persona_id=titular.persona_id, usuario_id=titular.usuario_id, enlace_identidad=titular,
        version_enlace=titular.version, evidencia_identidad=titular.evidencia,
        disciplina_id=disciplina_id, alcance_propuesto=alcance_propuesto.strip())
    return _evento(EventoMandatoInstitucional, dict(mandato=mandato), actor, enlace,
                   clave, 'propuesta', solicitud, datos)


@transaction.atomic
def proponer_acreditacion(*, actor, clave, competencia_id, evento_competencia_id,
                         mandato_id, evento_mandato_id, motivo, referencia_evidencia,
                         vigente_desde_propuesta, vigente_hasta_propuesta=None):
    actor, enlace = _actor(actor)
    clave = _uuid(clave)
    datos = _datos(motivo, referencia_evidencia, vigente_desde_propuesta, vigente_hasta_propuesta)
    referencias = dict(competencia_id=_id(competencia_id), evento_competencia_id=_id(evento_competencia_id),
                      mandato_id=_id(mandato_id), evento_mandato_id=_id(evento_mandato_id))
    solicitud = dict(tipo='acreditacion', operacion='propuesta', referencias=referencias, datos=datos)
    previo = _reintento(actor, enlace, clave, solicitud)
    if previo:
        return previo
    acreditacion = AcreditacionEmisora.objects.create(**_registro(actor, enlace), **referencias)
    return _evento(EventoAcreditacionEmisora, dict(acreditacion=acreditacion), actor,
                   enlace, clave, 'propuesta', solicitud, datos)


@transaction.atomic
def registrar_evento(*, actor, tipo, expediente_id, numero_esperado, clave, accion,
                     motivo, referencia_evidencia, vigente_desde_propuesta, vigente_hasta_propuesta=None):
    actor, enlace = _actor(actor)
    if tipo not in ('mandato', 'acreditacion') or accion not in ('revision', 'retiro'):
        raise ValidationError('Solo revisión o retiro de expedientes pendientes.')
    clave = _uuid(clave)
    datos = _datos(motivo, referencia_evidencia, vigente_desde_propuesta, vigente_hasta_propuesta)
    solicitud = dict(tipo=tipo, operacion=accion, expediente=_id(expediente_id),
                     numero_esperado=_id(numero_esperado), datos=datos)
    previo = _reintento(actor, enlace, clave, solicitud)
    if previo:
        return previo
    cabecera, modelo = ((MandatoInstitucional, EventoMandatoInstitucional) if tipo == 'mandato'
                        else (AcreditacionEmisora, EventoAcreditacionEmisora))
    expediente = cabecera.objects.filter(pk=expediente_id).first()
    if expediente is None:
        raise ValidationError('Expediente no disponible.')
    anterior = expediente.eventos.order_by('-numero').first()
    if anterior is None or anterior.numero != numero_esperado:
        raise Conflicto('Versión de expediente obsoleta.')
    if anterior.accion == 'retiro':
        raise ValidationError('Expediente retirado; no se reabre.')
    return _evento(modelo, {tipo: expediente}, actor, enlace, clave, accion, solicitud, datos, anterior)
