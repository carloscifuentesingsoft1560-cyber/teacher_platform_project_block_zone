from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from recursos.api import Estricto, CustodiaVista, VersionVista
from recursos.permisos import custodio, programas_visibles, versiones_visibles
from recursos.editorial import bloquear, editable
from .models import ProgramaFormativo, Malla, MallaVersion, FaseCurricular, SemanaCurricular, ClasePrevista, ElementoCurricular, LoteImportacion, ActividadCurricular, UbicacionCurricular
from .servicios import crear_hijo


class ProgramaSerializer(Estricto):
    nombre = serializers.CharField(source='nivel.nombre', read_only=True)
    class Meta:
        model = ProgramaFormativo
        fields = ['id', 'uuid', 'nivel', 'nombre', 'modalidad', 'formalizado']
        read_only_fields = ['id', 'uuid']


class ProgramaVista(CustodiaVista):
    serializer_class = ProgramaSerializer
    def initial(self, request, *args, **kwargs):
        # Lectura docente por ámbito; escritura de configuración por custodia.
        from rest_framework.viewsets import GenericViewSet
        GenericViewSet.initial(self, request, *args, **kwargs)
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and not custodio(request.user):
            raise PermissionDenied()
    def get_queryset(self):
        return programas_visibles(self.request.user).select_related('nivel').order_by('nivel__orden', 'pk')

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        bloquear(request.user)
        if not custodio(request.user): raise PermissionDenied()
        if set(request.data) - {'modalidad', 'formalizado'}: raise ValidationError('El nivel vinculado es estable.')
        p = ProgramaFormativo.objects.select_for_update().get(pk=self.get_object().pk)
        s = self.get_serializer(p, data=request.data, partial=True); s.is_valid(raise_exception=True); s.save()
        from auditoria.servicios import registrar
        registrar(request.user, p, 'programa_configurar', list(request.data))
        return Response(s.data)


class FaseSerializer(Estricto):
    class Meta:
        model = FaseCurricular
        fields = ['id', 'uuid', 'clave_logica', 'codigo', 'nombre', 'orden']
        read_only_fields = ['id', 'uuid', 'clave_logica']


class SemanaSerializer(Estricto):
    class Meta:
        model = SemanaCurricular
        fields = ['id', 'uuid', 'clave_logica', 'fase', 'ordinal']
        read_only_fields = ['id', 'uuid', 'clave_logica']


class ClaseSerializer(Estricto):
    class Meta:
        model = ClasePrevista
        fields = ['id', 'uuid', 'clave_logica', 'semana', 'ordinal']
        read_only_fields = ['id', 'uuid', 'clave_logica']


class ElementoSerializer(Estricto):
    procedencia = serializers.SerializerMethodField()
    class Meta:
        model = ElementoCurricular
        fields = ['id', 'uuid', 'clave_logica', 'tipo', 'texto', 'dimension', 'subdimension', 'instrumento_propuesto', 'padre', 'fase', 'semana', 'clase', 'procedencia']
        read_only_fields = ['id', 'uuid', 'clave_logica']
    def get_procedencia(self, obj):
        return list(obj.procedencias.values('fragmento__fuente__uuid', 'fragmento__hoja', 'fragmento__celda', 'fragmento__rango', 'transformacion', 'observacion'))


class MallaVersionSerializer(Estricto):
    nombre = serializers.CharField(source='identidad.nombre', read_only=True)
    programa = serializers.IntegerField(source='identidad.programa_id', read_only=True)
    class Meta:
        model = MallaVersion
        fields = ['id', 'uuid', 'identidad', 'nombre', 'programa', 'numero', 'revision', 'naturaleza', 'estado', 'vigente', 'autor', 'revisor', 'revisada_en', 'derivada_de', 'derechos', 'observaciones_revision', 'semanas_esperadas', 'clases_esperadas']
        read_only_fields = ['id', 'uuid', 'identidad', 'numero', 'revision', 'naturaleza', 'estado', 'vigente', 'autor', 'revisor', 'revisada_en', 'derivada_de', 'observaciones_revision']


class UbicacionSerializer(Estricto):
    class Meta:
        model = UbicacionCurricular
        fields = ['id','elemento','fase','semana','clase']
        read_only_fields = ['id']


class MallaCrear(Estricto):
    derechos = serializers.CharField(write_only=True)
    class Meta:
        model = Malla
        fields = ['codigo', 'nombre', 'programa', 'derechos']


class MallaVista(VersionVista):
    modelo = MallaVersion
    tipo = 'malla'
    serializer_class = MallaVersionSerializer

    @transaction.atomic
    def create(self, request):
        bloquear(request.user)
        s = MallaCrear(data=request.data); s.is_valid(raise_exception=True)
        d = dict(s.validated_data); derechos = d.pop('derechos')
        if not programas_visibles(request.user).filter(pk=d['programa'].pk).exists():
            raise PermissionDenied('Programa fuera de tu ámbito.')
        m = Malla.objects.create(autor=request.user, **d)
        v = MallaVersion.objects.create(identidad=m, autor=request.user, derechos=derechos)
        return Response(self.get_serializer(v).data, status=201)

    def filtrar(self, qs):
        qs = super().filtrar(qs)
        if self.request.query_params.get('programa'):
            try: programa = int(self.request.query_params['programa'])
            except ValueError: raise ValidationError('Filtro de programa inválido.')
            qs = qs.filter(identidad__programa_id=programa)
        return qs

    @action(detail=True, methods=['get'])
    def estructura(self, request, uuid=None):
        v = self.get_object()
        return Response({'fases': FaseSerializer(v.fases.all(), many=True).data, 'semanas': SemanaSerializer(v.semanas.all(), many=True).data,
            'clases': ClaseSerializer(ClasePrevista.objects.filter(semana__version=v), many=True).data,
            'elementos': ElementoSerializer(v.elementos.order_by('pk'), many=True).data,
            'ubicaciones': UbicacionSerializer(UbicacionCurricular.objects.filter(elemento__version=v), many=True).data,
            'actividades': list(ActividadCurricular.objects.filter(elemento__version=v).values('id', 'elemento_id', 'ejercicio_version__uuid', 'finalidad'))})

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def agregar(self, request, uuid=None):
        bloquear(request.user)
        v = self.get_object()
        type(v.identidad).objects.select_for_update().get(pk=v.identidad_id)
        v = MallaVersion.objects.select_for_update().get(pk=v.pk)
        editable(request.user, v)
        from deportistas.servicios import Conflicto
        if set(request.data) != {'tipo', 'datos', 'revision'}:
            raise ValidationError('Se requieren tipo, datos y revision.')
        if request.data['revision'] != v.revision: raise Conflicto()
        mapa = {'fase': (FaseCurricular, FaseSerializer), 'semana': (SemanaCurricular, SemanaSerializer), 'clase': (ClasePrevista, ClaseSerializer), 'elemento': (ElementoCurricular, ElementoSerializer), 'ubicacion': (UbicacionCurricular, UbicacionSerializer)}
        if not isinstance(request.data['tipo'], str) or request.data['tipo'] not in mapa: raise ValidationError('Tipo no admitido.')
        modelo, serializador = mapa[request.data['tipo']]
        s = serializador(data=request.data['datos']); s.is_valid(raise_exception=True)
        obj = crear_hijo(request.user, v, modelo, s.validated_data)
        return Response(serializador(obj).data, status=201)

    @action(detail=True, methods=['post'], url_path='editar-elemento')
    @transaction.atomic
    def editar_elemento(self, request, uuid=None):
        bloquear(request.user)
        v = self.get_object()
        type(v.identidad).objects.select_for_update().get(pk=v.identidad_id)
        v = MallaVersion.objects.select_for_update().get(pk=v.pk); editable(request.user, v)
        from deportistas.servicios import Conflicto
        if set(request.data) != {'elemento', 'revision', 'texto'}: raise ValidationError('Campos no permitidos.')
        if request.data['revision'] != v.revision: raise Conflicto()
        e = get_object_or_404(v.elementos, uuid=request.data['elemento'])
        if not isinstance(request.data['texto'], str) or not request.data['texto'].strip(): raise ValidationError('Texto requerido.')
        e.texto = request.data['texto']; e.save(update_fields=['texto'])
        v.revision += 1; v.save(update_fields=['revision'])
        from auditoria.servicios import registrar
        registrar(request.user, e, 'curriculo_editar', ['texto'])
        return Response(ElementoSerializer(e).data)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def actividad(self, request, uuid=None):
        bloquear(request.user); v = self.get_object()
        type(v.identidad).objects.select_for_update().get(pk=v.identidad_id)
        v = MallaVersion.objects.select_for_update().get(pk=v.pk); editable(request.user, v)
        from deportistas.servicios import Conflicto
        if set(request.data) != {'elemento', 'ejercicio_version', 'finalidad', 'revision'}: raise ValidationError('Campos no permitidos.')
        if request.data['revision'] != v.revision: raise Conflicto()
        from biblioteca.models import EjercicioVersion
        from .servicios import resolver_referencia
        e = get_object_or_404(v.elementos, uuid=request.data['elemento'])
        ejercicio = get_object_or_404(versiones_visibles(request.user, EjercicioVersion.objects.all(), 'biblioteca'), uuid=request.data['ejercicio_version'])
        resolver_referencia(request.user, ejercicio)
        if not isinstance(request.data['finalidad'], str) or not 1 <= len(request.data['finalidad']) <= 200: raise ValidationError('Finalidad requerida.')
        a, _ = ActividadCurricular.objects.get_or_create(elemento=e, ejercicio_version=ejercicio, defaults={'finalidad': request.data['finalidad']})
        v.revision += 1; v.save(update_fields=['revision'])
        from auditoria.servicios import registrar
        registrar(request.user, a, 'curriculo_actividad', ['elemento','ejercicio_version'])
        return Response({'id': a.pk}, status=201)


class LoteSerializer(Estricto):
    class Meta:
        model = LoteImportacion
        fields = ['uuid', 'fuente', 'perfil', 'clave', 'estado', 'vista_previa', 'resultado']
        read_only_fields = fields


class ImportacionVista(CustodiaVista):
    queryset = LoteImportacion.objects.order_by('-pk')
    serializer_class = LoteSerializer
    lookup_field = 'uuid'
    def create(self, request):
        from .importacion import extraer_lote
        if set(request.data) != {'fuente', 'clave'}: raise ValidationError('Indica fuente y clave UUID.')
        lote = extraer_lote(request.user, request.data['fuente'], request.data['clave'])
        return Response(self.get_serializer(lote).data, status=201)

    @action(detail=True, methods=['post'])
    def confirmar(self, request, uuid=None):
        from .importacion import confirmar_lote
        if set(request.data) != {'programas'}: raise ValidationError('Indica el mapa explícito de programas por hoja.')
        lote = confirmar_lote(request.user, self.get_object(), request.data['programas'])
        return Response(self.get_serializer(lote).data)
