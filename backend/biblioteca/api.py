from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from recursos.api import Estricto, CustodiaVista, VersionVista, descargar
from recursos.permisos import custodio, programas_visibles, versiones_visibles
from recursos.editorial import bloquear, editable
from .models import Ejercicio, EjercicioVersion, TerminoActividad, PasoEjercicio, AdaptacionEjercicio, ExigenciaEjercicio, ProcedenciaEjercicio, MaterialDocente, MaterialDocenteVersion, MaterialEjercicio, CandidatoBiblioteca


class TerminoSerializer(Estricto):
    class Meta:
        model = TerminoActividad
        fields = ['id', 'namespace', 'codigo', 'nombre']
        read_only_fields = ['id']
    def validate(self, d):
        if d.get('namespace') == 'estilo' and d.get('codigo') not in ('fisico', 'electrico', 'coordinativo', 'tecnico-equilibrio'):
            raise serializers.ValidationError('Usa los cuatro estilos institucionales; capacidades en otro namespace.')
        return d


class TerminoVista(CustodiaVista):
    serializer_class = TerminoSerializer
    queryset = TerminoActividad.objects.order_by('namespace', 'codigo')
    def initial(self, request, *args, **kwargs):
        from rest_framework.viewsets import GenericViewSet
        GenericViewSet.initial(self, request, *args, **kwargs)
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and not custodio(request.user): raise PermissionDenied()


class VersionBibliotecaSerializer(Estricto):
    def validate(self, datos):
        actor = self.context['request'].user
        if 'programas' in datos and not custodio(actor):
            permitidos = set(programas_visibles(actor).values_list('pk', flat=True))
            if any(x.pk not in permitidos for x in datos['programas']):
                raise serializers.ValidationError('Programas fuera de tu ámbito.')
        if datos.get('acceso_tecnico') and not (custodio(actor) or actor.tiene_rol('routesetter')):
            raise serializers.ValidationError('Acceso técnico requiere facultades de routesetter.')
        archivo = datos.get('archivo')
        if archivo and archivo.autor_id != actor.pk and not custodio(actor): raise serializers.ValidationError('Archivo no disponible.')
        return datos


class EjercicioSerializer(VersionBibliotecaSerializer):
    pasos = serializers.SerializerMethodField()
    adaptaciones = serializers.SerializerMethodField()
    exigencias = serializers.SerializerMethodField()
    procedencias = serializers.SerializerMethodField()
    materiales = serializers.SerializerMethodField()
    class Meta:
        model = EjercicioVersion
        fields = ['id', 'uuid', 'identidad', 'numero', 'revision', 'naturaleza', 'estado', 'vigente', 'autor', 'derivada_de', 'revisor', 'revisada_en', 'derechos', 'observaciones_revision',
            'disciplina', 'programas', 'etiquetas', 'nombre', 'objetivo', 'poblacion', 'metodologia', 'descripcion', 'organizacion', 'prerrequisitos', 'riesgos', 'controles', 'edad_min', 'edad_max', 'duracion_min', 'duracion_max', 'acceso_tecnico', 'exigencias_conocidas', 'pasos', 'adaptaciones', 'exigencias', 'procedencias', 'materiales']
        read_only_fields = ['id', 'uuid', 'identidad', 'numero', 'revision', 'naturaleza', 'estado', 'vigente', 'autor', 'derivada_de', 'revisor', 'revisada_en', 'observaciones_revision']
    def validate(self, d):
        d = super().validate(d)
        for minimo, maximo in [('edad_min','edad_max'),('duracion_min','duracion_max')]:
            a, b = d.get(minimo, getattr(self.instance, minimo, None)), d.get(maximo, getattr(self.instance, maximo, None))
            if a is not None and b is not None and a > b: raise serializers.ValidationError({maximo: 'El máximo debe ser al menos el mínimo.'})
        disciplina = d.get('disciplina', getattr(self.instance, 'disciplina', None))
        if disciplina and any(p.nivel.disciplina_id != disciplina.pk for p in d.get('programas', [])): raise serializers.ValidationError('Disciplina/programa incompatibles.')
        return d
    def get_pasos(self, o): return list(o.pasos.values('id', 'orden', 'instrucciones'))
    def get_adaptaciones(self, o): return list(o.adaptaciones.values('id', 'condicion', 'alternativa', 'limites'))
    def get_exigencias(self, o): return list(o.exigencias.values('id', 'termino_id', 'descripcion', 'estado_dato'))
    def get_procedencias(self, o): return list(o.procedencias.values('fragmento__fuente__uuid', 'fragmento__localizador', 'adaptacion'))
    def get_materiales(self, o):
        actor = self.context['request'].user
        visibles = versiones_visibles(actor, MaterialDocenteVersion.objects.all(), 'biblioteca')
        return list(o.materiales.filter(material__in=visibles).values('material__uuid', 'finalidad'))


class MaterialSerializer(VersionBibliotecaSerializer):
    class Meta:
        model = MaterialDocenteVersion
        fields = ['id', 'uuid', 'identidad', 'numero', 'revision', 'naturaleza', 'estado', 'vigente', 'autor', 'derivada_de', 'revisor', 'revisada_en', 'derechos', 'observaciones_revision', 'titulo', 'resumen', 'archivo', 'referencia_externa', 'programas', 'acceso_tecnico']
        read_only_fields = ['id', 'uuid', 'identidad', 'numero', 'revision', 'naturaleza', 'estado', 'vigente', 'autor', 'derivada_de', 'revisor', 'revisada_en', 'observaciones_revision']
    def validate(self, d):
        d = super().validate(d)
        a = d.get('archivo', getattr(self.instance, 'archivo', None)); ref = d.get('referencia_externa', getattr(self.instance, 'referencia_externa', ''))
        if a and a.finalidad != 'material_docente': raise serializers.ValidationError('Una fuente de custodia no se publica como material docente.')
        if bool(a) == bool(ref): raise serializers.ValidationError('Indica archivo o referencia, no ambos.')
        if ref and not ref.startswith('https://'): raise serializers.ValidationError('Solo enlaces HTTPS sin descarga automática.')
        return d


class CrearEjercicio(serializers.Serializer):
    codigo = serializers.SlugField(max_length=80)
    contenido = serializers.JSONField()
    def to_internal_value(self, data):
        if set(data) != {'codigo', 'contenido'}: raise serializers.ValidationError('Indica codigo y contenido.')
        return super().to_internal_value(data)


class BibliotecaVista(VersionVista):
    @transaction.atomic
    def create(self, request):
        bloquear(request.user)
        entrada = CrearEjercicio(data=request.data); entrada.is_valid(raise_exception=True)
        s = self.get_serializer(data=entrada.validated_data['contenido']); s.is_valid(raise_exception=True)
        nombre = s.validated_data.get('nombre') or s.validated_data.get('titulo')
        identidad = self.identidad_modelo.objects.create(codigo=entrada.validated_data['codigo'], nombre=nombre, autor=request.user)
        s.save(identidad=identidad, autor=request.user)
        from auditoria.servicios import registrar
        registrar(request.user, s.instance, 'biblioteca_crear', [])
        return Response(s.data, status=201)

    def filtrar(self, qs):
        qs = super().filtrar(qs)
        params = self.request.query_params
        texto = params.get('buscar')
        if texto:
            qs = qs.filter(Q(nombre__icontains=texto) | Q(objetivo__icontains=texto)) if self.modelo == EjercicioVersion else qs.filter(Q(titulo__icontains=texto) | Q(resumen__icontains=texto))
        for param, campo in [('programa', 'programas__id'), ('disciplina', 'disciplina_id')]:
            if params.get(param) and (self.modelo == EjercicioVersion or param == 'programa'):
                try: valor = int(params[param])
                except ValueError: raise ValidationError('Filtro numérico inválido.')
                qs = qs.filter(**{campo: valor})
        if self.modelo == EjercicioVersion:
            for param, namespace in [('capacidad','capacidad'),('material','implemento'),('instalacion','instalacion'),('estilo','estilo'),('movimiento','movimiento')]:
                if params.get(param): qs = qs.filter(etiquetas__namespace=namespace, etiquetas__codigo=params[param])
            if params.get('poblacion'): qs = qs.filter(poblacion__icontains=params['poblacion'])
            if params.get('duracion_max'):
                try: minutos = int(params['duracion_max'])
                except ValueError: raise ValidationError('Duración inválida.')
                qs = qs.filter(duracion_max__lte=minutos)
        return qs.distinct()


class EjercicioVista(BibliotecaVista):
    modelo = EjercicioVersion
    identidad_modelo = Ejercicio
    serializer_class = EjercicioSerializer

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def agregar(self, request, uuid=None):
        bloquear(request.user); v = self.get_object()
        Ejercicio.objects.select_for_update().get(pk=v.identidad_id)
        v = EjercicioVersion.objects.select_for_update().get(pk=v.pk); editable(request.user, v)
        from deportistas.servicios import Conflicto
        if set(request.data) != {'tipo', 'datos', 'revision'}: raise ValidationError('Indica tipo, datos y revision.')
        if request.data['revision'] != v.revision: raise Conflicto()
        tipos = {'paso': (PasoEjercicio,['orden','instrucciones']), 'adaptacion': (AdaptacionEjercicio,['condicion','alternativa','limites']), 'exigencia': (ExigenciaEjercicio,['termino','descripcion','estado_dato']), 'procedencia': (ProcedenciaEjercicio,['fragmento','adaptacion']), 'material': (MaterialEjercicio,['material','finalidad'])}
        if not isinstance(request.data['tipo'], str) or request.data['tipo'] not in tipos: raise ValidationError('Tipo no admitido.')
        modelo, campos = tipos[request.data['tipo']]
        class Hijo(Estricto):
            class Meta:
                model = modelo
                fields = campos
        s = Hijo(data=request.data['datos']); s.is_valid(raise_exception=True)
        if modelo == ExigenciaEjercicio and s.validated_data['termino'].namespace != 'exigencia_funcional': raise ValidationError('Se requiere término funcional.')
        if modelo == ProcedenciaEjercicio and not custodio(request.user): raise PermissionDenied('La procedencia documental la acredita custodia.')
        if modelo == MaterialEjercicio:
            m = s.validated_data['material']
            if not versiones_visibles(request.user, MaterialDocenteVersion.objects.filter(pk=m.pk), 'biblioteca').exists(): raise PermissionDenied('Material fuera de ámbito.')
        s.save(version=v); v.revision += 1; v.save(update_fields=['revision'])
        from auditoria.servicios import registrar
        registrar(request.user, v, 'biblioteca_completar', campos)
        return Response(s.data, status=201)


class MaterialVista(BibliotecaVista):
    modelo = MaterialDocenteVersion
    identidad_modelo = MaterialDocente
    serializer_class = MaterialSerializer

    @action(detail=True, methods=['get'])
    def descarga(self, request, uuid=None):
        m = self.get_object()
        if not m.archivo_id: raise ValidationError('La referencia es externa; no se descarga desde el servidor.')
        return descargar(m.archivo, request.user)


class CandidatoSerializer(Estricto):
    class Meta:
        model = CandidatoBiblioteca
        fields = ['id', 'fragmento', 'titulo', 'naturaleza', 'observaciones']
        read_only_fields = ['id']


class CandidatoVista(CustodiaVista):
    queryset = CandidatoBiblioteca.objects.order_by('pk')
    serializer_class = CandidatoSerializer
