"""Seguimiento interno e indicadores descriptivos; no certifican práctica ni aprendizaje."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from organizacion.models import Grupo
from organizacion.permisos import es_coordinador_activo
from .models import SeguimientoPedagogico
from .permisos import sesiones_visibles
from .serializers import Comando
from .servicios import _usuarios, _reintento, _evento, Conflicto


class NuevoSeguimiento(Comando):
    comentario = serializers.CharField(max_length=4000)
    recomendaciones = serializers.CharField(max_length=4000, allow_blank=True, default='')


class LecturaSeguimiento(serializers.ModelSerializer):
    class Meta:
        model = SeguimientoPedagogico
        fields = ['id', 'sesion', 'actor', 'registrado_en', 'comentario', 'recomendaciones', 'anterior', 'evento']


@transaction.atomic
def registrar(*, actor, sesion_id, version, clave, comentario, recomendaciones=''):
    referencia = get_object_or_404(sesiones_visibles(actor), pk=sesion_id)
    actor, _ = _usuarios(actor, referencia.profesor_id)
    if not es_coordinador_activo(actor):
        raise PermissionDenied('Se requiere coordinación vigente.')
    Grupo.objects.select_for_update().get(pk=referencia.grupo_id)
    sesion = get_object_or_404(sesiones_visibles(actor).select_for_update(), pk=sesion_id)
    entrada = NuevoSeguimiento(data=dict(version=version, clave=clave, comentario=comentario, recomendaciones=recomendaciones))
    entrada.is_valid(raise_exception=True)
    datos = entrada.validated_data
    solicitud = dict(sesion=sesion.pk, version=version, comentario=datos['comentario'], recomendaciones=datos['recomendaciones'])
    repetida = _reintento(actor, clave, 'seguimiento', solicitud)
    if repetida:
        return sesion
    if version != sesion.version:
        raise Conflicto()
    anterior = sesion.seguimientos.order_by('-pk').first()
    sesion.version += 1
    sesion.actualizado_por = actor
    sesion.save(update_fields=['version', 'actualizado_por', 'actualizado_en'])
    _evento(sesion, actor, clave, 'seguimiento', solicitud, dict(anterior=anterior.pk if anterior else None))
    SeguimientoPedagogico.objects.create(sesion=sesion, actor=actor, comentario=datos['comentario'], recomendaciones=datos['recomendaciones'], anterior=anterior, evento=sesion.eventos.get(actor=actor, clave=clave))
    return sesion


class Filtros(serializers.Serializer):
    profesor = serializers.IntegerField(min_value=1, required=False)
    grupo = serializers.IntegerField(min_value=1, required=False)
    nivel = serializers.IntegerField(min_value=1, required=False)
    periodo = serializers.IntegerField(min_value=1, required=False)
    desde = serializers.DateField(required=False)
    hasta = serializers.DateField(required=False)
    situacion = serializers.ChoiceField(choices=['programadas', 'ejecutadas', 'canceladas', 'pendientes', 'realizadas'], required=False)

    def validate(self, datos):
        if datos.get('desde') and datos.get('hasta') and datos['desde'] > datos['hasta']:
            raise ValidationError('Intervalo invertido.')
        return datos


def filtrar(consulta, parametros):
    entrada = Filtros(data=parametros)
    entrada.is_valid(raise_exception=True)
    datos = entrada.validated_data
    for campo, ruta in [('profesor', 'profesor_id'), ('grupo', 'grupo_id'), ('nivel', 'grupo__nivel_id'), ('periodo', 'grupo__periodo_id'), ('desde', 'fecha__gte'), ('hasta', 'fecha__lte')]:
        if campo in datos:
            consulta = consulta.filter(**{ruta: datos[campo]})
    situacion = datos.get('situacion')
    if situacion == 'ejecutadas':
        consulta = consulta.filter(ejecucion__finalizada_en__isnull=False)
    elif situacion == 'pendientes':
        consulta = consulta.filter(estado='planificada', fecha__lte=timezone.localdate(), ejecucion__finalizada_en__isnull=True)
    elif situacion in ('programadas', 'canceladas', 'realizadas'):
        consulta = consulta.filter(estado={'programadas': 'planificada', 'canceladas': 'cancelada', 'realizadas': 'realizada'}[situacion])
        if situacion == 'programadas':
            consulta = consulta.filter(ejecucion__finalizada_en__isnull=True)
    return consulta


def indicadores(consulta):
    resultado = dict(sesiones=0, informes_cerrados=0, realizadas_institucionales=0, canceladas=0, asistencia_cerrada_sesiones=0, asistencia={e: 0 for e in ['asistio', 'no_asistio', 'tarde', 'excusa', 'retiro']}, duracion_real_minutos=0, minutos_efectivos=0, minutos_planificados=0, actividades={e: 0 for e in ['realizada', 'modificada', 'omitida']}, tareas_curriculares=0, tareas_curriculares_abordadas=0)
    consulta = consulta.select_related('ejecucion', 'ejecucion__plan').prefetch_related('asistencias', 'ejecucion__actividades', 'ejecucion__plan__tareas')
    for sesion in consulta.iterator(chunk_size=200):
        resultado['sesiones'] += 1
        resultado['realizadas_institucionales'] += sesion.estado == 'realizada'
        resultado['canceladas'] += sesion.estado == 'cancelada'
        if sesion.asistencia_confirmada:
            resultado['asistencia_cerrada_sesiones'] += 1
            for asistencia in sesion.asistencias.all():
                resultado['asistencia'][asistencia.estado] += 1
        ejecucion = getattr(sesion, 'ejecucion', None)
        if not ejecucion or not ejecucion.finalizada_en:
            continue
        resultado['informes_cerrados'] += 1
        resultado['duracion_real_minutos'] += (ejecucion.fin-ejecucion.inicio).total_seconds()/60
        resultado['minutos_planificados'] += sum(t.minutos for t in ejecucion.plan.tareas.all())
        curricular = ejecucion.plan.malla_version_id is not None
        for actividad in ejecucion.actividades.all():
            resultado['actividades'][actividad.resultado] += 1
            resultado['minutos_efectivos'] += actividad.minutos
            if curricular:
                resultado['tareas_curriculares'] += 1
                resultado['tareas_curriculares_abordadas'] += actividad.resultado != 'omitida'
    total = sum(resultado['asistencia'].values())
    resultado['porcentaje_presencia'] = 100*(resultado['asistencia']['asistio']+resultado['asistencia']['tarde'])/total if total else None
    resultado['porcentaje_cumplimiento_curricular_declarado'] = 100*resultado['tareas_curriculares_abordadas']/resultado['tareas_curriculares'] if resultado['tareas_curriculares'] else None
    resultado['tiempo_no_distribuido_minutos'] = resultado['duracion_real_minutos']-resultado['minutos_efectivos']
    return resultado
