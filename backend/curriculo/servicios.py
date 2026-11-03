from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from recursos.editorial import bloquear, editable
from recursos.permisos import versiones_visibles
from .models import FaseCurricular, SemanaCurricular, ClasePrevista, ElementoCurricular, ProcedenciaCurricular, ActividadCurricular, UbicacionCurricular


def copiar_arbol(original, copia):
    fases, semanas, clases, elementos = {}, {}, {}, {}
    for x in original.fases.all():
        old = x.pk; x.pk = None
        import uuid
        x.uuid = uuid.uuid4(); x.version = copia; x.save(); fases[old] = x
    for x in original.semanas.all():
        old = x.pk; x.pk = None; x.uuid = uuid.uuid4(); x.version = copia; x.fase = fases[x.fase_id]; x.save(); semanas[old] = x
    for x in ClasePrevista.objects.filter(semana__version=original):
        old = x.pk; x.pk = None; x.uuid = uuid.uuid4(); x.semana = semanas[x.semana_id]; x.save(); clases[old] = x
    pendientes = []
    for x in original.elementos.all():
        old, padre = x.pk, x.padre_id
        x.pk = None; x.uuid = uuid.uuid4(); x.version = copia; x.padre_id = None
        if x.fase_id: x.fase = fases[x.fase_id]
        if x.semana_id: x.semana = semanas[x.semana_id]
        if x.clase_id: x.clase = clases[x.clase_id]
        x.save(); elementos[old] = x; pendientes.append((x, padre))
    for x, padre in pendientes:
        if padre:
            x.padre = elementos[padre]; x.save(update_fields=['padre'])
    for x in ProcedenciaCurricular.objects.filter(elemento__version=original):
        x.pk = None; x.elemento = elementos[x.elemento_id]; x.save()
    for x in ActividadCurricular.objects.filter(elemento__version=original):
        x.pk = None; x.elemento = elementos[x.elemento_id]; x.save()
    for x in UbicacionCurricular.objects.filter(elemento__version=original):
        x.pk = None; x.elemento = elementos[x.elemento_id]
        if x.fase_id: x.fase = fases[x.fase_id]
        if x.semana_id: x.semana = semanas[x.semana_id]
        if x.clase_id: x.clase = clases[x.clase_id]
        x.save()


def validar_hijo(version, datos):
    fase, semana, clase, padre = (datos.get(k) for k in ('fase', 'semana', 'clase', 'padre'))
    if sum(x is not None for x in (fase, semana, clase)) > 1:
        raise ValidationError('Selecciona un único alcance.')
    if fase and fase.version_id != version.pk or semana and semana.version_id != version.pk or clase and clase.semana.version_id != version.pk or padre and padre.version_id != version.pk:
        raise ValidationError('Las referencias deben pertenecer a la misma versión.')


@transaction.atomic
def crear_hijo(actor, version, modelo, datos):
    bloquear(actor)
    type(version.identidad).objects.select_for_update().get(pk=version.identidad_id)
    version = type(version).objects.select_for_update().get(pk=version.pk)
    editable(actor, version)
    if modelo == SemanaCurricular:
        if datos['fase'].version_id != version.pk:
            raise ValidationError('Fase de otra versión.')
    elif modelo == ClasePrevista:
        if datos['semana'].version_id != version.pk:
            raise ValidationError('Semana de otra versión.')
    elif modelo == ElementoCurricular:
        validar_hijo(version, datos)
    elif modelo == UbicacionCurricular:
        if datos['elemento'].version_id != version.pk: raise ValidationError('Elemento de otra edición.')
        validar_hijo(version, datos)
    obj = modelo.objects.create(**datos, **({} if modelo in (ClasePrevista, UbicacionCurricular) else {'version': version}))
    version.revision += 1; version.save(update_fields=['revision'])
    from auditoria.servicios import registrar
    registrar(actor, obj, 'curriculo_estructura', list(datos))
    return obj


def resolver_referencia(actor, version, historica=False):
    """La retirada impide selección nueva; historia solo para custodia/autor."""
    from recursos.permisos import custodio
    if historica and (custodio(actor) or version.autor_id == actor.pk):
        return version
    tipo = 'malla' if version._meta.model_name == 'mallaversion' else 'biblioteca'
    if not versiones_visibles(actor, type(version).objects.filter(pk=version.pk), tipo).exists() or version.estado != 'aprobado' or not version.vigente:
        raise ValidationError('La referencia no es elegible para uso nuevo.')
    return version
