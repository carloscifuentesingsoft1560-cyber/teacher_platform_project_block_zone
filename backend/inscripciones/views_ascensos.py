"""Propuestas docentes y revisión pedagógica B2.2-A; sin ejecución administrativa."""
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from deportistas.permisos import AccesoFase3, usuario_actual, deportistas_visibles
from organizacion.models import Nivel
from organizacion.permisos import es_coordinador_activo
from .consultas_ascensos import referencias_docentes, nivel_inmediatamente_superior
from .servicios_ascensos import progresiones_visibles, proponer_progresion, decidir_progresion, disponer_inscripcion
from .serializers_ascensos import (CrearAscensoSerializer, ContextoAscensoSerializer,
    NivelesAscensoSerializer, FiltrosAscensoSerializer, AscensoLecturaSerializer, EntradaEstricta,
    AscensoCoordinacionSerializer, DecisionAscensoSerializer, DisposicionAscensoSerializer)
from .api_ejecucion import AdministracionAscensoMixin


class AccesoAscensos(BasePermission):
    def has_permission(self, request, view):
        actor = usuario_actual(request.user)
        if view.action == 'ejecutar' or (view.action == 'revisiones' and request.method == 'POST'):
            return actor.tiene_rol('administrador')
        if view.action in ('ejecucion', 'revisiones', 'resultados'):
            return (actor.tiene_rol('administrador')) or es_coordinador_activo(actor)
        if view.action in ('aprobar', 'rechazar', 'advertencias', 'afectaciones', 'disponer'):
            return es_coordinador_activo(actor)
        if view.action in ('create', 'contexto', 'niveles'):
            return (actor.tiene_rol('profesor'))
        return (any(actor.tiene_rol(papel) for papel in ('profesor', 'administrador'))) or es_coordinador_activo(actor)


def validar_consulta(clase, parametros):
    entrada = clase(data=parametros)
    entrada.is_valid(raise_exception=True)
    return entrada.validated_data


def metadatos_nivel(nivel):
    return {'id': nivel.pk, 'codigo': nivel.codigo, 'nombre': nivel.nombre,
        'disciplina': nivel.disciplina_id, 'orden': nivel.orden}


class AscensoVista(AdministracionAscensoMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
        mixins.CreateModelMixin, viewsets.GenericViewSet):
    permission_classes = [AccesoFase3, AccesoAscensos]
    serializer_class = AscensoLecturaSerializer
    http_method_names = ['get', 'post', 'head', 'options']

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve') and es_coordinador_activo(usuario_actual(self.request.user)):
            return AscensoCoordinacionSerializer
        return AscensoLecturaSerializer

    def retrieve(self, request, *args, **kwargs):
        p = self.get_object()
        if es_coordinador_activo(usuario_actual(request.user)):
            from .revision_ascensos import detalle_revision
            return Response(detalle_revision(p))
        return Response(self.get_serializer(p).data)

    @action(detail=True, methods=['get'])
    def advertencias(self, request, pk=None):
        validar_consulta(EntradaVacia, request.query_params)
        from .revision_ascensos import advertencias_revision
        return Response(advertencias_revision(self.get_object()))

    @action(detail=True, methods=['get'])
    def afectaciones(self, request, pk=None):
        validar_consulta(EntradaVacia, request.query_params)
        from .revision_ascensos import detalle_revision
        datos = detalle_revision(self.get_object())
        return Response({campo: datos[campo] for campo in
            ('id', 'version', 'estado_decision', 'estado_plan', 'inscripciones', 'revision')})

    @action(detail=True, methods=['post'])
    def disponer(self, request, pk=None):
        validar_consulta(EntradaVacia, request.query_params)
        d = validar_consulta(DisposicionAscensoSerializer, request.data)
        p = disponer_inscripcion(request.user, self.get_object().pk, d['version'],
            d['afectacion'], d['disposicion'], d['motivo'], d['destino'])
        from .revision_ascensos import detalle_revision
        return Response(detalle_revision(p))

    def accion_decision(self, request):
        validar_consulta(EntradaVacia, request.query_params)
        d = validar_consulta(DecisionAscensoSerializer, request.data)
        if d['decision'] != self.action:
            raise ValidationError('La decisión explícita no coincide con la acción solicitada.')
        objeto = self.get_object()
        p = decidir_progresion(request.user, objeto.pk, d['version'], self.action == 'aprobar', d['resolucion'])
        from .revision_ascensos import detalle_revision
        return Response(detalle_revision(p))

    @action(detail=True, methods=['post'])
    def aprobar(self, request, pk=None):
        return self.accion_decision(request)

    @action(detail=True, methods=['post'])
    def rechazar(self, request, pk=None):
        return self.accion_decision(request)

    def get_queryset(self):
        filtros = validar_consulta(FiltrosAscensoSerializer, self.request.query_params)
        datos = progresiones_visibles(self.request.user).select_related('deportista', 'disciplina',
            'nivel_origen', 'nivel_destino', 'periodo')
        for campo in ('disciplina', 'deportista', 'estado_decision'):
            if campo in filtros:
                datos = datos.filter(**{campo: filtros[campo]})
        return datos

    def create(self, request, *args, **kwargs):
        validar_consulta(EntradaVacia, request.query_params)
        d = validar_consulta(CrearAscensoSerializer, request.data)
        referencia = get_object_or_404(referencias_docentes(request.user), pk=d['inscripcion_referencia'],
            deportista_id=d['deportista'], grupo__disciplina_id=d['disciplina'])
        nivel = get_object_or_404(Nivel, pk=d['nivel_destino'])
        p = proponer_progresion(request.user, referencia.pk, nivel, d['justificacion'])
        return Response(self.get_serializer(p).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def contexto(self, request):
        d = validar_consulta(ContextoAscensoSerializer, request.query_params)
        get_object_or_404(deportistas_visibles(request.user), pk=d['deportista'])
        referencias = referencias_docentes(request.user).filter(deportista_id=d['deportista'])
        if 'disciplina' in d:
            referencias = referencias.filter(grupo__disciplina_id=d['disciplina'])
        if d['vista'] == 'disciplinas':
            if d.get('search'):
                referencias = referencias.filter(Q(grupo__disciplina__nombre__icontains=d['search']) |
                    Q(grupo__disciplina__codigo__icontains=d['search']))
            datos = referencias.order_by('grupo__disciplina_id').values('grupo__disciplina_id',
                'grupo__disciplina__nombre', 'grupo__disciplina__codigo').distinct()
            pagina = self.paginate_queryset(datos)
            return self.get_paginated_response([{'id': x['grupo__disciplina_id'],
                'nombre': x['grupo__disciplina__nombre'], 'codigo': x['grupo__disciplina__codigo']} for x in pagina])
        if d.get('search'):
            referencias = referencias.filter(Q(grupo__nombre__icontains=d['search']) |
                Q(grupo__codigo__icontains=d['search']) | Q(grupo__nivel__nombre__icontains=d['search']) |
                Q(grupo__periodo__nombre__icontains=d['search']))
        pagina = self.paginate_queryset(referencias)
        resultado = []
        for i in pagina:
            siguiente = nivel_inmediatamente_superior(i.grupo.nivel)
            resultado.append({'id': i.pk, 'deportista': i.deportista_id, 'disciplina': i.grupo.disciplina_id,
                'disciplina_nombre': i.grupo.disciplina.nombre, 'grupo_codigo': i.grupo.codigo,
                'grupo_nombre': i.grupo.nombre, 'periodo': i.grupo.periodo_id,
                'periodo_nombre': i.grupo.periodo.nombre, 'nivel_origen': metadatos_nivel(i.grupo.nivel),
                'nivel_siguiente': metadatos_nivel(siguiente) if siguiente else None,
                'puede_proponer': siguiente is not None,
                'motivo_nivel': '' if siguiente else 'No hay nivel inmediatamente superior activo disponible; no se omiten niveles.',
                'aviso': 'La coordinación revisará todas las inscripciones pertinentes. Solo se muestran referencias propias; proponer no cambia grupos, cupos ni reservas.'})
        return self.get_paginated_response(resultado)

    @action(detail=False, methods=['get'])
    def niveles(self, request):
        d = validar_consulta(NivelesAscensoSerializer, request.query_params)
        i = get_object_or_404(referencias_docentes(request.user), pk=d['inscripcion_referencia'],
            deportista_id=d['deportista'], grupo__disciplina_id=d['disciplina'])
        siguiente = nivel_inmediatamente_superior(i.grupo.nivel)
        datos = [metadatos_nivel(siguiente)] if siguiente else []
        if d.get('search'):
            texto = d['search'].casefold()
            datos = [n for n in datos if texto in n['codigo'].casefold() or texto in n['nombre'].casefold()]
        return self.get_paginated_response(self.paginate_queryset(datos))


class EntradaVacia(EntradaEstricta):
    pass
