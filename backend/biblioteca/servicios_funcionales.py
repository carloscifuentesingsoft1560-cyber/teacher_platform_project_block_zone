"""Registro documental interno. Ningún comando aprueba perfiles ni habilita práctica."""
import json
from uuid import UUID
from django.db import connection, transaction
from rest_framework.exceptions import PermissionDenied, ValidationError
from auditoria.servicios import registrar
from cuentas.models import EnlaceIdentidad
from cuentas.servicios_roles import bloquear_admin
from deportistas.servicios import Conflicto
from .modelos_funcionales import (PerfilFuncional, PerfilFuncionalVersion,
    ExigenciaPerfilFuncional, CondicionPerfilFuncional, AdaptacionPerfilFuncional,
    ProcedenciaPerfilFuncional, EventoPerfilFuncional, CorrespondenciaFuncional,
    CorrespondenciaFuncionalVersion, EventoCorrespondenciaFuncional)


def _identificador(valor):
    try:
        valor = UUID(str(valor))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('Clave UUID v4 requerida.')
    if valor.version != 4:
        raise ValidationError('Clave UUID v4 requerida.')
    return valor


def _actor(actor):
    # Mismo orden de bloqueo que B1/B2.1 y cambios de roles/identidad.
    bloquear_admin(actor)
    enlace = EnlaceIdentidad.objects.select_for_update().filter(usuario=actor, vigente=True, usuario__is_active=True).first()
    if enlace is None:
        raise PermissionDenied('Se requiere identidad acreditada del registrador documental.')
    return dict(actor=actor, persona_actor_id=enlace.persona_id, enlace_actor=enlace,
                version_enlace_actor=enlace.version, evidencia_actor=enlace.evidencia)


def _solicitud(**datos):
    # No convertir silenciosamente valores arbitrarios a texto.
    return json.loads(json.dumps(datos, sort_keys=True, allow_nan=False))


def _reintento(identidad, clave, solicitud):
    for modelo in (EventoPerfilFuncional, EventoCorrespondenciaFuncional):
        previo = modelo.objects.filter(actor=identidad['actor'], clave=clave).first()
        if previo:
            if previo.persona_actor_id != identidad['persona_actor_id'] or previo.solicitud != solicitud:
                raise Conflicto('Clave reutilizada con otra identidad o solicitud.')
            return previo


def _evento(modelo, version, identidad, clave, solicitud, motivo, accion='propuesta', anterior=None):
    if not isinstance(motivo, str) or not motivo.strip() or len(motivo) > 500:
        raise ValidationError('Motivo documental requerido, máximo 500 caracteres.')
    evento = modelo.objects.create(version=version, numero=anterior.numero + 1 if anterior else 1,
        anterior=anterior, accion=accion, clave=clave, solicitud=solicitud, motivo=motivo.strip(), **identidad)
    registrar(identidad['actor'], evento, accion, ['numero', 'accion'])
    return evento


def _anterior(cabecera, modelo, campo, numero_esperado):
    if type(numero_esperado) is not int or numero_esperado < 0:
        raise ValidationError('Número esperado inválido.')
    anterior = modelo.objects.filter(**{campo: cabecera}).order_by('-numero').first()
    if (anterior.numero if anterior else 0) != numero_esperado:
        raise Conflicto('Versión obsoleta.')
    if anterior and anterior.eventos.order_by('-numero').first().accion == 'retiro':
        raise ValidationError('La cadena retirada no se reabre.')
    return anterior


@transaction.atomic
def proponer_perfil(*, actor, clave, disciplina_id, nombre, alcance, exigencias,
                    condiciones, adaptaciones, procedencias, motivo,
                    perfil_id=None, numero_esperado=0):
    identidad = _actor(actor)
    clave = _identificador(clave)
    solicitud = _solicitud(tipo='perfil', perfil=perfil_id, esperado=numero_esperado,
        disciplina=disciplina_id, nombre=nombre, alcance=alcance, exigencias=exigencias,
        condiciones=condiciones, adaptaciones=adaptaciones, procedencias=procedencias, motivo=motivo)
    previo = _reintento(identidad, clave, solicitud)
    if previo:
        return previo
    if perfil_id is None:
        if numero_esperado != 0:
            raise Conflicto('Un perfil nuevo exige versión esperada cero.')
        perfil = PerfilFuncional.objects.create(disciplina_id=disciplina_id)
    else:
        perfil = PerfilFuncional.objects.select_for_update().get(pk=perfil_id)
        if perfil.disciplina_id != disciplina_id:
            raise ValidationError('La disciplina histórica no puede cambiar.')
    anterior = _anterior(perfil, PerfilFuncionalVersion, 'perfil', numero_esperado)
    version = PerfilFuncionalVersion.objects.create(perfil=perfil, anterior=anterior,
        numero=numero_esperado+1, nombre=nombre, alcance=alcance)
    from .models import TerminoActividad
    filas = []
    for datos in exigencias:
        datos = dict(datos)
        termino = TerminoActividad.objects.select_for_update().get(pk=datos.pop('termino_id'))
        fila = ExigenciaPerfilFuncional.objects.create(version=version, termino=termino,
            codigo_historico=termino.codigo, nombre_historico=termino.nombre, **datos)
        filas.append(fila)
    condiciones_guardadas = []
    for datos in condiciones:
        datos = dict(datos)
        indice = datos.pop('exigencia_indice')
        if type(indice) is not int or not 0 <= indice < len(filas):
            raise ValidationError('Exigencia de condición ajena al perfil.')
        condiciones_guardadas.append(CondicionPerfilFuncional.objects.create(version=version, exigencia=filas[indice], **datos))
    for datos in adaptaciones:
        datos = dict(datos)
        indice = datos.pop('condicion_indice')
        if type(indice) is not int or not 0 <= indice < len(condiciones_guardadas):
            raise ValidationError('Condición de adaptación ajena al perfil.')
        AdaptacionPerfilFuncional.objects.create(version=version, condicion=condiciones_guardadas[indice], **datos)
    for datos in procedencias:
        ProcedenciaPerfilFuncional.objects.create(version=version, **datos)
    return _evento(EventoPerfilFuncional, version, identidad, clave, solicitud, motivo)


@transaction.atomic
def proponer_correspondencia(*, actor, clave, perfil_version_id, evento_perfil_id,
                            motivo, justificacion, ejercicio_id=None, tarea_id=None,
                            actividad_id=None, adaptacion_id=None,
                            correspondencia_id=None, numero_esperado=0):
    identidad = _actor(actor)
    clave = _identificador(clave)
    solicitud = _solicitud(tipo='correspondencia', correspondencia=correspondencia_id,
        esperado=numero_esperado, perfil=perfil_version_id, evento=evento_perfil_id,
        ejercicio=ejercicio_id, tarea=tarea_id, actividad=actividad_id,
        adaptacion=adaptacion_id, motivo=motivo, justificacion=justificacion)
    previo = _reintento(identidad, clave, solicitud)
    if previo:
        return previo
    destino = dict(ejercicio_id=ejercicio_id, tarea_id=tarea_id, actividad_id=actividad_id)
    if sum(x is not None for x in destino.values()) != 1:
        raise ValidationError('Se requiere exactamente un destino.')
    if correspondencia_id is None:
        if numero_esperado != 0:
            raise Conflicto('Una correspondencia nueva exige versión esperada cero.')
        cabecera = CorrespondenciaFuncional.objects.create(**destino)
    else:
        cabecera = CorrespondenciaFuncional.objects.select_for_update().get(pk=correspondencia_id)
        if any(getattr(cabecera, k) != v for k, v in destino.items()):
            raise ValidationError('El destino histórico no puede cambiar.')
    anterior = _anterior(cabecera, CorrespondenciaFuncionalVersion, 'correspondencia', numero_esperado)
    with connection.cursor() as cursor:
        cursor.execute('SELECT public.zdb_b22_contexto(%s)', [cabecera.pk])
        contexto = cursor.fetchone()[0]
    if isinstance(contexto, str):
        contexto = json.loads(contexto)
    version = CorrespondenciaFuncionalVersion.objects.create(correspondencia=cabecera,
        anterior=anterior, numero=numero_esperado+1, perfil_version_id=perfil_version_id,
        evento_perfil_id=evento_perfil_id, adaptacion_id=adaptacion_id,
        contexto=contexto, justificacion=justificacion)
    return _evento(EventoCorrespondenciaFuncional, version, identidad, clave, solicitud, motivo)


@transaction.atomic
def registrar_revision(*, actor, clave, tipo, version_id, numero_esperado, accion, motivo):
    if tipo not in ('perfil', 'correspondencia') or accion not in ('revision', 'retiro'):
        raise ValidationError('Solo revisión documental o retiro; no existe aprobación funcional.')
    identidad = _actor(actor)
    clave = _identificador(clave)
    solicitud = _solicitud(tipo=tipo, version=version_id, esperado=numero_esperado, accion=accion, motivo=motivo)
    previo = _reintento(identidad, clave, solicitud)
    if previo:
        return previo
    version_modelo, evento_modelo = ((PerfilFuncionalVersion, EventoPerfilFuncional) if tipo == 'perfil'
        else (CorrespondenciaFuncionalVersion, EventoCorrespondenciaFuncional))
    version = version_modelo.objects.select_for_update().get(pk=version_id)
    anterior = version.eventos.order_by('-numero').first()
    if anterior is None or anterior.numero != numero_esperado:
        raise Conflicto('Revisión obsoleta.')
    if anterior.accion == 'retiro':
        raise ValidationError('Retiro terminal.')
    return _evento(evento_modelo, version, identidad, clave, solicitud, motivo, accion, anterior)
