"""Comandos documentales B2.3 A. Sin consultas, aprobación o habilitación operativa."""
import hashlib
import json
from datetime import timezone as utc
from uuid import UUID
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from cuentas.models import AcreditacionEmisora, EnlaceIdentidad, Usuario
from auditoria.servicios import registrar
from .servicios import Conflicto
from .modelos_autorizaciones_funcionales import (ExpedienteAutorizacionFuncional as Expediente,
    PropuestaDecisionFuncionalVersion as Version, AlcanceDecisionFuncional as Alcance,
    CondicionDecisionFuncional as Condicion, AdaptacionDecisionFuncional as Adaptacion,
    ReferenciaEvidenciaFuncional as Evidencia, EventoExpedienteFuncional as Evento)


def _uuid(valor):
    try:
        resultado = UUID(str(valor))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('Referencia opaca UUID v4 requerida.')
    if resultado.version != 4:
        raise ValidationError('Referencia opaca UUID v4 requerida.')
    return resultado


def _fecha(valor):
    if not hasattr(valor, 'utcoffset') or timezone.is_naive(valor):
        raise ValidationError('Fecha explícita con zona requerida.')
    return valor.astimezone(utc.utc).isoformat()


def _actor(actor):
    # No se usa es_gestor ni se heredan permisos de recursos pedagógicos.
    list(Usuario.objects.select_for_update().order_by('pk'))
    if not Usuario.objects.get(pk=actor.pk).tiene_rol('administrador'):
        raise PermissionDenied('Se requiere custodia documental vigente y específica, no solo un rol.')
    enlace = EnlaceIdentidad.objects.select_for_update().filter(usuario=actor, vigente=True, usuario__is_active=True).first()
    if enlace is None:
        raise PermissionDenied('Identidad acreditada requerida para registro documental.')
    return dict(actor=actor, persona_actor_id=enlace.persona_id, enlace_actor=enlace,
                version_enlace_actor=enlace.version, evidencia_actor=enlace.evidencia)


def _huella(datos):
    return hashlib.sha256(json.dumps(datos, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def _reintento(identidad, clave, huella):
    evento = Evento.objects.filter(actor=identidad['actor'], clave=clave).first()
    if evento and (evento.huella != huella or evento.persona_actor_id != identidad['persona_actor_id']):
        raise Conflicto('Clave reutilizada con otra solicitud o identidad.')
    return evento


def _custodia(identidad, acreditacion):
    # Únicamente el registrador histórico del antecedente puede proponer/revisar.
    # No concede acceso general a expedientes ni evidencia por rol administrativo.
    if acreditacion.registrada_por_id != identidad['actor'].pk or acreditacion.persona_registradora_id != identidad['persona_actor_id']:
        raise PermissionDenied('No existe relación de registro documental con el antecedente.')


def _evento(expediente, version, identidad, clave, huella, accion, anterior):
    evento = Evento.objects.create(expediente=expediente, version=version, accion=accion,
        numero=anterior.numero+1 if anterior else 1, anterior=anterior, clave=clave, huella=huella, **identidad)
    registrar(identidad['actor'], evento, accion, ['accion', 'numero'])
    return evento


@transaction.atomic
def proponer(*, actor, clave, enlace_destinatario_id, disciplina_id, acreditacion_id,
             evento_acreditacion_id, desde_propuesta, hasta_propuesta, alcances, evidencias,
             emitida_en_declarada=None, expediente_id=None, numero_esperado=0):
    identidad = _actor(actor)
    clave = _uuid(clave)
    fechas = dict(desde=_fecha(desde_propuesta), hasta=_fecha(hasta_propuesta),
                  emision=_fecha(emitida_en_declarada) if emitida_en_declarada is not None else None)
    huella = _huella(dict(tipo='propuesta', expediente=expediente_id, esperado=numero_esperado,
        destinatario=enlace_destinatario_id, disciplina=disciplina_id, acreditacion=acreditacion_id,
        evento=evento_acreditacion_id, fechas=fechas, alcances=alcances, evidencias=evidencias))
    previo = _reintento(identidad, clave, huella)
    if previo:
        return previo
    acreditacion = AcreditacionEmisora.objects.select_for_update().get(pk=acreditacion_id)
    _custodia(identidad, acreditacion)
    enlace = EnlaceIdentidad.objects.select_for_update().get(pk=enlace_destinatario_id, vigente=True, deportista__isnull=False)
    if type(numero_esperado) is not int or numero_esperado < 0:
        raise ValidationError('Versión esperada inválida.')
    if expediente_id is None:
        if numero_esperado != 0:
            raise Conflicto('Expediente nuevo exige versión esperada cero.')
        expediente = Expediente.objects.create(deportista_id=enlace.deportista_id, persona_id=enlace.persona_id,
            enlace_identidad=enlace, version_enlace=enlace.version, evidencia_identidad=enlace.evidencia, disciplina_id=disciplina_id)
    else:
        expediente = Expediente.objects.select_for_update().get(pk=expediente_id)
        if expediente.enlace_identidad_id != enlace.pk or expediente.disciplina_id != disciplina_id:
            raise ValidationError('No se cambia destinatario ni disciplina histórica.')
    anterior_version = expediente.versiones.order_by('-numero').first()
    anterior = expediente.eventos.order_by('-numero').first()
    if (anterior_version.numero if anterior_version else 0) != numero_esperado:
        raise Conflicto('Versión obsoleta.')
    if anterior and anterior.accion == 'retiro':
        raise ValidationError('Retiro terminal.')
    version = Version.objects.create(expediente=expediente, numero=numero_esperado+1, anterior=anterior_version,
        acreditacion=acreditacion, evento_acreditacion_id=evento_acreditacion_id,
        desde_propuesta=desde_propuesta, hasta_propuesta=hasta_propuesta, emitida_en_declarada=emitida_en_declarada)
    for datos in alcances:
        datos = dict(datos)
        condiciones = datos.pop('condiciones')
        adaptaciones = datos.pop('adaptaciones')
        alcance = Alcance.objects.create(version=version, **datos)
        filas = {}
        for condicion in condiciones:
            fila = Condicion.objects.create(alcance=alcance, **condicion)
            filas[fila.condicion_id] = fila
        for adaptacion in adaptaciones:
            adaptacion = dict(adaptacion)
            condicion = filas.get(adaptacion.pop('condicion_id'))
            if condicion is None:
                raise ValidationError('Adaptación sin condición individual explícita.')
            Adaptacion.objects.create(alcance=alcance, condicion_individual=condicion, **adaptacion)
    for evidencia in evidencias:
        evidencia = dict(evidencia)
        evidencia['referencia'] = _uuid(evidencia['referencia'])
        evidencia['registro_custodia'] = _uuid(evidencia['registro_custodia'])
        Evidencia.objects.create(version=version, **evidencia)
    return _evento(expediente, version, identidad, clave, huella, 'propuesta', anterior)


@transaction.atomic
def revisar(*, actor, clave, expediente_id, numero_esperado, accion):
    if accion not in ('revision', 'retiro'):
        raise ValidationError('Solo revisión documental o retiro; no existe aprobación operativa.')
    identidad = _actor(actor)
    clave = _uuid(clave)
    huella = _huella(dict(tipo=accion, expediente=expediente_id, esperado=numero_esperado))
    previo = _reintento(identidad, clave, huella)
    if previo:
        return previo
    expediente = Expediente.objects.select_for_update().get(pk=expediente_id)
    anterior = expediente.eventos.order_by('-numero').first()
    if anterior is None or anterior.numero != numero_esperado:
        raise Conflicto('Revisión obsoleta.')
    _custodia(identidad, anterior.version.acreditacion)
    if anterior.accion == 'retiro':
        raise ValidationError('Retiro terminal.')
    return _evento(expediente, anterior.version, identidad, clave, huella, accion, anterior)
