"""Selección nueva vigente; la consulta histórica usa las FK exactas del plan."""
from rest_framework.exceptions import ValidationError
from recursos.permisos import versiones_visibles
from curriculo.models import ProgramaFormativo, MallaVersion, FaseCurricular, SemanaCurricular, ClasePrevista, ElementoCurricular
from biblioteca.models import EjercicioVersion


def programas_grupo(grupo):
    return ProgramaFormativo.objects.filter(nivel_id=grupo.nivel_id, nivel__disciplina_id=grupo.disciplina_id, formalizado=True)


def mallas_elegibles(actor, grupo):
    return versiones_visibles(actor, MallaVersion.objects.all(), 'malla').filter(estado='aprobado', vigente=True, identidad__programa__in=programas_grupo(grupo))


def ejercicios_elegibles(actor, grupo):
    return versiones_visibles(actor, EjercicioVersion.objects.all(), 'ejercicio').filter(estado='aprobado', vigente=True, disciplina_id=grupo.disciplina_id, programas__in=programas_grupo(grupo)).distinct()


def referencia(modelo, pk):
    if pk is None:
        return None
    objeto = modelo.objects.filter(pk=pk).first()
    if objeto is None:
        raise ValidationError('Referencia curricular no disponible.')
    return objeto


def resolver_plan(actor, grupo, datos):
    """Devuelve FK normalizadas y competencias sin modificar publicaciones."""
    programa = referencia(ProgramaFormativo, datos.get('programa_id'))
    malla = None
    if datos.get('malla_version_id'):
        malla = MallaVersion.objects.select_for_update().filter(pk=datos['malla_version_id']).first()
        if malla is None or not mallas_elegibles(actor, grupo).filter(pk=malla.pk).exists():
            raise ValidationError('Versión curricular no disponible, vigente o compatible.')
        if programa and programa.pk != malla.identidad.programa_id:
            raise ValidationError('Programa y malla incompatibles.')
        programa = malla.identidad.programa
    if programa and not programas_grupo(grupo).filter(pk=programa.pk).exists():
        raise ValidationError('Programa no formalizado o incompatible con el grupo.')
    if programa is None and any(t.get('ejercicio_version_id') for t in datos['tareas']):
        programa = programas_grupo(grupo).first()
    fase = referencia(FaseCurricular, datos.get('fase_curricular_id'))
    semana = referencia(SemanaCurricular, datos.get('semana_id'))
    clase = referencia(ClasePrevista, datos.get('clase_id'))
    if clase:
        if semana and semana.pk != clase.semana_id:
            raise ValidationError('Clase y semana incompatibles.')
        semana = clase.semana
    if semana:
        if fase and fase.pk != semana.fase_id:
            raise ValidationError('Semana y fase incompatibles.')
        fase = semana.fase
    if (fase or semana or clase or datos.get('competencias_ids')) and not malla:
        raise ValidationError('Selecciona una versión curricular vigente.')
    if fase and fase.version_id != malla.pk or semana and semana.version_id != malla.pk:
        raise ValidationError('La estructura debe pertenecer a la misma versión curricular.')
    ids = datos.get('competencias_ids', [])
    if len(ids) != len(set(ids)):
        raise ValidationError('Competencias duplicadas.')
    competencias = list(ElementoCurricular.objects.filter(pk__in=ids, version=malla, tipo='competencia').order_by('pk'))
    if len(competencias) != len(ids):
        raise ValidationError('Competencias ajenas a la versión o de tipo incorrecto.')
    return dict(programa=programa, malla_version=malla, fase_curricular=fase, semana=semana, clase=clase), competencias


def validar_ejercicios(actor, grupo, tareas):
    ids = sorted({t.get('ejercicio_version_id') for t in tareas if t.get('ejercicio_version_id')})
    # Bloquear por PK y revalidar ámbito después: DISTINCT no admite FOR UPDATE.
    versiones = list(EjercicioVersion.objects.select_for_update().filter(pk__in=ids).order_by('pk'))
    if len(versiones) != len(ids) or set(ejercicios_elegibles(actor, grupo).filter(pk__in=ids).values_list('pk', flat=True)) != set(ids):
        raise ValidationError('Ejercicio no aprobado, no vigente o incompatible con el programa del grupo.')
    por_id = {v.pk: v for v in versiones}
    for tarea in tareas:
        version = por_id.get(tarea.get('ejercicio_version_id'))
        if version and (version.duracion_min is not None and tarea['minutos'] < version.duracion_min or version.duracion_max is not None and tarea['minutos'] > version.duracion_max):
            raise ValidationError('Duración de tarea fuera del intervalo del ejercicio seleccionado.')
