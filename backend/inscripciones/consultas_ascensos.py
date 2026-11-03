"""Contexto docente y secuencia pedagógica; no modifica registros."""
from rest_framework.exceptions import PermissionDenied, ValidationError
from deportistas.permisos import usuario_actual, inscripciones_visibles
from deportistas.servicios import Conflicto
from organizacion.models import Nivel

SECUENCIA_PEDAGOGICA = ('ludico', 'nivel-1', 'nivel-2', 'especializacion', 'alto-rendimiento')


def referencias_docentes(actor):
    actor = usuario_actual(actor)
    if (not actor.tiene_rol('profesor')):
        raise PermissionDenied('Solo el profesor puede consultar el contexto de una propuesta.')
    return inscripciones_visibles(actor).filter(estado='activa', deportista__estado='activo',
        grupo__disciplina__activo=True, grupo__nivel__activo=True).order_by('pk')


def nivel_inmediatamente_superior(origen):
    niveles = list(Nivel.objects.filter(disciplina_id=origen.disciplina_id).order_by('orden', 'codigo'))
    configuracion = [(n.codigo, n.orden) for n in niveles]
    if configuracion != list(zip(SECUENCIA_PEDAGOGICA, range(1, 6))):
        raise Conflicto('La secuencia institucional de niveles requiere revisión de configuración.')
    actual = next((n for n in niveles if n.pk == origen.pk), None)
    if actual is None or not actual.activo or not actual.disciplina.activo:
        raise ValidationError('El nivel de origen y su disciplina deben estar activos.')
    posicion = SECUENCIA_PEDAGOGICA.index(actual.codigo)
    siguiente = niveles[posicion + 1] if posicion < len(niveles) - 1 else None
    # Un nivel desactivado no autoriza saltar al posterior.
    return siguiente if siguiente and siguiente.activo else None


def validar_nivel_propuesto(origen, destino):
    if destino.disciplina_id != origen.disciplina_id:
        raise ValidationError('El nivel propuesto debe pertenecer a la misma disciplina.')
    siguiente = nivel_inmediatamente_superior(origen)
    if siguiente is None:
        raise ValidationError('No hay un nivel inmediatamente superior activo disponible. No se permiten saltos.')
    if siguiente.pk != destino.pk:
        raise ValidationError('Solo se permite proponer el nivel pedagógico inmediatamente superior.')
