"""Viabilidad compartida por consulta, propuesta y decisión; no escribe datos."""
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from deportistas.permisos import usuario_actual, deportistas_visibles, inscripciones_visibles
from deportistas.servicios import Conflicto
from .models import Propuesta
from .servicios import docente_en_grupo, validar_nueva, ocupacion_maxima, mensaje_integridad_historial

AVISO_NIVEL_ANTIGUO = ('El mecanismo anterior de cambio de nivel está deshabilitado. '
    'La propuesta histórica se conserva para revisión administrativa; utiliza el procedimiento de ascenso institucional. '
    'No se convierte ni ejecuta automáticamente.')


def bloquear_nivel_antiguo(tipo):
    if tipo == 'nivel':
        raise Conflicto(AVISO_NIVEL_ANTIGUO)


def contexto_docente(actor, persona, tipo, fecha, origen=None, propuesta=None):
    actor = usuario_actual(actor)
    if (not actor.tiene_rol('profesor')):
        raise PermissionDenied('Solo un profesor con ámbito vigente puede presentar propuestas.')
    bloquear_nivel_antiguo(tipo)
    persona = deportistas_visibles(actor).filter(pk=persona.pk).first()
    if persona is None:
        raise PermissionDenied('Deportista fuera de su ámbito vigente.')
    if fecha != timezone.localdate():
        raise ValidationError('Las propuestas corresponden a la fecha operativa actual.')
    if tipo not in ('inscripcion', 'traslado', 'nivel'):
        raise ValidationError('Tipo de propuesta no admitido.')
    if tipo == 'inscripcion':
        if origen is not None:
            raise ValidationError('Una inscripción adicional no modifica un origen.')
        return persona, None
    if origen is None:
        raise ValidationError({'inscripcion_origen': 'Selecciona una inscripción de origen.'})
    origen = inscripciones_visibles(actor).filter(pk=origen.pk, deportista=persona, estado='activa').select_related('grupo__periodo','grupo__nivel','grupo__disciplina').first()
    if origen is None or not docente_en_grupo(actor, origen.grupo, fecha):
        raise PermissionDenied('Origen fuera de su asignación vigente.')
    if origen.fecha_ingreso >= fecha:
        raise ValidationError(mensaje_integridad_historial(tipo == 'nivel'))
    if not all((origen.grupo.activo, origen.grupo.nivel.activo, origen.grupo.disciplina.activo, origen.grupo.periodo.activo)):
        raise ValidationError('La estructura de origen no está activa.')
    pendientes = Propuesta.objects.filter(inscripcion_origen=origen, estado='pendiente')
    if propuesta:
        pendientes = pendientes.exclude(pk=propuesta.pk)
    if pendientes.exists():
        raise Conflicto('El origen ya tiene una propuesta pendiente. Revisa o cancela la anterior.')
    return persona, origen


def validar_destino(persona, tipo, fecha, origen, destino, propuesta=None):
    if origen:
        if destino.pk == origen.grupo_id:
            raise ValidationError('El destino debe ser un grupo distinto del origen.')
        if destino.disciplina_id != origen.grupo.disciplina_id:
            raise ValidationError('El destino debe pertenecer a la misma disciplina.')
        diferente = destino.nivel_id != origen.grupo.nivel_id
        if diferente != (tipo == 'nivel'):
            raise ValidationError('Traslado requiere el mismo nivel; cambio de nivel requiere un nivel distinto.')
    pendientes = Propuesta.objects.filter(deportista=persona, grupo_destino=destino, estado='pendiente')
    if propuesta:
        pendientes = pendientes.exclude(pk=propuesta.pk)
    if pendientes.exists():
        raise Conflicto('Ya existe una propuesta pendiente para ese destino.')
    # Proyectar el cierre del origen sin modificarlo: no debe causar un cruce ficticio.
    validar_nueva(persona, destino, fecha, excluir=origen.pk if origen else None, permitir_nivel=tipo == 'nivel')


def metadatos_destino(grupo, fecha):
    horarios = list(grupo.horarios.filter(activo=True).order_by('dia','hora_inicio'))
    dias = {h.dia for h in horarios}
    jornada = ('Entre semana' if dias and dias <= {0,1,2,3,4} else
               'Sábado' if dias == {5} else 'Domingo' if dias == {6} else 'Mixta')
    ocupacion = ocupacion_maxima(grupo, inicio=fecha)
    return {
        'id': grupo.pk, 'codigo': grupo.codigo, 'nombre': grupo.nombre,
        'nivel': grupo.nivel_id, 'nivel_nombre': grupo.nivel.nombre,
        'jornada': jornada, 'periodo': grupo.periodo_id, 'periodo_nombre': grupo.periodo.nombre,
        'fecha_inicio_periodo': grupo.periodo.fecha_inicio, 'fecha_fin_periodo': grupo.periodo.fecha_fin,
        'horarios': [{'dia':h.dia, 'hora_inicio':h.hora_inicio, 'hora_fin':h.hora_fin} for h in horarios],
        'disponibilidad': {'desde':fecha, 'hasta':grupo.periodo.fecha_fin,
                          'cupo_maximo':grupo.cupo_maximo, 'disponibles':max(0,grupo.cupo_maximo-ocupacion)},
    }
