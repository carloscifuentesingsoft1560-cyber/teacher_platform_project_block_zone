"""Contratos administrativos B3-C. No conceden autoridad pedagógica."""
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from .serializers_ascensos import EntradaEstricta, DisposicionAscensoSerializer


class InstalacionPendiente(APIException):
    status_code = 503
    default_detail = 'La ejecución requiere instalar y verificar la migración 0004. No se realizó ningún movimiento.'


def instalacion_verificada():
    """Sin caché: no basta un cliente que declare habilitada la ejecución."""
    if connection.vendor != 'postgresql' or not MigrationRecorder.Migration.objects.filter(
            app='inscripciones', name='0005_facultades_multirrol').exists():
        return False
    with connection.cursor() as c:
        c.execute("""SELECT EXISTS (SELECT 1 FROM information_schema.columns
          WHERE table_schema='public' AND table_name='inscripciones_resultadoadministrativo'
          AND column_name='evidencia_ejecucion'),
          EXISTS (SELECT 1 FROM pg_catalog.pg_trigger t
          JOIN pg_catalog.pg_class r ON r.oid=t.tgrelid
          JOIN pg_catalog.pg_namespace n ON n.oid=r.relnamespace
          JOIN pg_catalog.pg_proc f ON f.oid=t.tgfoid
          JOIN pg_catalog.pg_namespace nf ON nf.oid=f.pronamespace
          WHERE n.nspname='public' AND r.relname='inscripciones_resultadoadministrativo'
          AND t.tgname='zdb_movimiento_ascenso_verificado' AND t.tgenabled='O'
          AND t.tgdeferrable AND t.tginitdeferred AND nf.nspname='public'
          AND f.proname='zdb_movimiento_ascenso_verificado'),
          (SELECT count(*) FROM pg_catalog.pg_constraint x
          JOIN pg_catalog.pg_class r ON r.oid=x.conrelid
          JOIN pg_catalog.pg_namespace n ON n.oid=r.relnamespace
          WHERE n.nspname='public' AND r.relname='inscripciones_resultadoadministrativo'
          AND x.conname='resultado_admin_estado_coherente' AND x.convalidated),
          (SELECT count(*) FROM pg_catalog.pg_indexes WHERE schemaname='public'
          AND tablename='inscripciones_resultadoadministrativo'
          AND indexname IN ('movimiento_afectacion_unico','movimiento_origen_unico'))""")
        columna, trigger, restriccion, indices = c.fetchone()
    if not (columna and trigger and restriccion == 1 and indices == 2):
        return False
    # La marca de migración no acredita por sí sola la nueva autoridad SQL.
    from importlib import import_module
    import re
    migracion = import_module('inscripciones.migrations.0005_facultades_multirrol')
    roles = import_module('cuentas.migrations.0006_roles_compatibilidad')
    esperados = {
        'zdb_administracion_b3_guardia': migracion.guardia.split('AS $$',1)[1].rsplit('$$;',1)[0],
        'zdb_tiene_rol': re.search(r'CREATE FUNCTION public.zdb_tiene_rol.*?AS \$\$(.*?)\$\$;',roles.SQL,re.S).group(1),
    }
    with connection.cursor() as c:
        c.execute("""SELECT p.proname,p.prosrc,p.prosecdef,p.proconfig FROM pg_catalog.pg_proc p
          JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
          WHERE n.nspname='public' AND p.proname IN ('zdb_administracion_b3_guardia','zdb_tiene_rol')""")
        encontrados=c.fetchall()
        if len(encontrados)!=2 or any(nombre not in esperados or cuerpo!=esperados[nombre] or definer
                or config!=['search_path=pg_catalog'] for nombre,cuerpo,definer,config in encontrados):
            return False
        c.execute("""SELECT count(*) FROM pg_catalog.pg_trigger t
          JOIN pg_catalog.pg_class r ON r.oid=t.tgrelid
          JOIN pg_catalog.pg_namespace n ON n.oid=r.relnamespace
          WHERE n.nspname='public' AND r.relname='cuentas_usuario'
            AND t.tgname='zdb_rol_principal_compatible' AND t.tgenabled='O'""")
        return c.fetchone()[0]==1


class PaginaAdministrativa(EntradaEstricta):
    page = serializers.IntegerField(min_value=1, required=False)


class FilaRevision(DisposicionAscensoSerializer):
    version = None


class CrearRevision(EntradaEstricta):
    version = serializers.IntegerField(min_value=1)
    motivo = serializers.CharField(max_length=500, allow_blank=False)
    disposiciones = FilaRevision(many=True, allow_empty=False)


class EjecutarReubicacion(EntradaEstricta):
    revision = serializers.IntegerField(min_value=1)
    version = serializers.IntegerField(min_value=1)
    afectacion = serializers.IntegerField(min_value=1)
    clave = serializers.UUIDField()
    motivo = serializers.CharField(max_length=240, allow_blank=False)


def mensaje_validacion(detalle):
    if isinstance(detalle, dict):
        return '; '.join(mensaje_validacion(v) for v in detalle.values())
    if isinstance(detalle, (list, tuple)):
        return '; '.join(mensaje_validacion(v) for v in detalle)
    return str(detalle)


def grupo_minimo(g):
    from .servicios import ocupacion_maxima
    from .servicios_movimientos import hoy_bogota
    from .models import ReservaCupo
    hoy = hoy_bogota()
    ocupacion = ocupacion_maxima(g, inicio=max(hoy, g.periodo.fecha_inicio))
    return {'id': g.pk, 'codigo': g.codigo, 'nombre': g.nombre, 'activo': g.activo,
        'nivel': g.nivel.nombre, 'periodo': g.periodo.nombre,
        'horarios': list(g.horarios.filter(activo=True).values('dia', 'hora_inicio', 'hora_fin')),
        'capacidad': g.cupo_maximo, 'ocupacion_maxima': ocupacion,
        'reservas_vigentes': ReservaCupo.objects.filter(inscripcion__grupo=g, liberada_en__isnull=True,
            fecha_inicio__lte=hoy, fecha_vencimiento__gte=hoy).count(),
        'disponibles': max(0, g.cupo_maximo - ocupacion)}


def lectura_administrativa(actor, p):
    from .servicios_ascensos import situacion
    from .servicios_ejecucion import consultar_ejecucion
    from .modelos_ejecucion import ResultadoAdministrativo
    from .servicios_movimientos import hoy_bogota
    from .servicios import validar_nueva
    from .revision_ascensos import actor_minimo
    from organizacion.models import Grupo
    from rest_framework.exceptions import APIException as ErrorApi
    instalado = instalacion_verificada()
    revision = p.revisiones_administrativas.order_by('-numero').first()
    # La proyección B3-B1 no selecciona el campo agregado por 0004.
    resumen = consultar_ejecucion(actor, p.pk) if instalado else {
        'progresion': p.pk, 'version': p.version, 'revision': revision.pk if revision else None,
        'plan_completo': False, 'discrepancias': [], 'advertencias_destinos': [],
        'inscripciones_nuevas': [], 'estado_ejecucion': 'no_habilitada', 'puede_cerrar': False}
    resumen['ejecucion_habilitada'] = bool(instalado)
    resumen['aviso_instalacion'] = '' if instalado else str(InstalacionPendiente.default_detail)
    resumen['estado_decision'] = p.estado_decision
    resumen['deportista'] = p.deportista.nombres + ' ' + p.deportista.apellidos
    resumen['disciplina'] = p.disciplina.nombre
    resumen['disciplina_id'] = p.disciplina_id
    resumen['nivel_destino_id'] = p.nivel_destino_id
    resumen['nivel_origen'] = p.nivel_origen.nombre
    resumen['nivel_destino'] = p.nivel_destino.nombre
    resumen['revision_numero'] = revision.numero if revision else None
    if revision:
        from .servicios_ejecucion import validar_evidencia_lectura
        validar_evidencia_lectura(revision.disposiciones)
    filas = {f['afectacion']: f for f in revision.disposiciones} if revision else {}
    resultados = set(ResultadoAdministrativo.objects.filter(revision__progresion=p,
        estado='ejecutada').values_list('afectacion_id', flat=True))
    locales = set(revision.resultados.values_list('afectacion_id', flat=True)) if revision else set()
    afectaciones = list(p.afectaciones.select_related('inscripcion__grupo__periodo',
        'inscripcion__grupo__nivel', 'inscripcion__grupo__disciplina'))
    hoy = hoy_bogota()
    detalles = []
    for a in afectaciones:
        f = filas.get(a.pk, {})
        destino_id = f.get('destino', a.destino_id)
        destino = Grupo.objects.select_related('periodo', 'nivel', 'disciplina').filter(pk=destino_id).first() if destino_id else None
        i = a.inscripcion
        razones = []
        if not actor.tiene_rol("administrador"): razones.append("Formalización exclusiva de administración.")
        if not instalado: razones.append('Instalación 0004 pendiente de verificación.')
        if p.estado_decision != 'aprobada': razones.append('Se requiere aprobación pedagógica.')
        if not resumen['plan_completo'] or resumen['discrepancias'] or resumen['inscripciones_nuevas']:
            razones.append('El plan completo requiere revisión administrativa vigente.')
        if a.pk in resultados: razones.append('La afectación ya fue ejecutada.')
        elif a.pk in locales: razones.append('Existe evidencia en esta revisión; registra una nueva revisión expresa.')
        if f.get('disposicion') != 'reubicar' or destino is None:
            razones.append('No existe un destino de reubicación válido.')
        if i.estado != 'activa' or i.fecha_ingreso >= hoy or i.reservas.filter(liberada_en__isnull=True).exists():
            razones.append('Solo se ejecutan inscripciones activas, sin reserva abierta y con ingreso anterior a hoy; suspendidas y futuras están bloqueadas.')
        if not (i.grupo.activo and i.grupo.periodo.activo and i.grupo.nivel.activo and i.grupo.disciplina.activo
                and i.grupo.periodo.fecha_inicio <= hoy <= i.grupo.periodo.fecha_fin):
            razones.append('El grupo o periodo de origen no está vigente.')
        for otra in afectaciones:
            if otra.pk == a.pk or otra.pk in resultados or otra.inscripcion.estado == 'finalizada': continue
            if (otra.inscripcion.estado != 'activa' or otra.inscripcion.fecha_ingreso > hoy or not otra.excepciones.filter(
                    estado='autorizada', fecha_inicio__lte=hoy, fecha_limite__gte=hoy).exists()):
                razones.append('Otra inscripción pendiente requiere una situación operativa autorizada y excepción vigente.'); break
        if destino:
            if destino.nivel_id != p.nivel_destino_id or destino.disciplina_id != p.disciplina_id:
                razones.append('Destino incompatible con la progresión aprobada.')
            try:
                validar_nueva(i.deportista, destino, hoy, excluir=i.pk, permitir_nivel=True)
            except ErrorApi as e:
                razones.append(mensaje_validacion(e.detail))
        detalles.append({'afectacion': a.pk, 'inscripcion': i.pk, 'estado': i.estado,
            'situacion': 'finalizada' if i.estado == 'finalizada' else situacion(i),
            'fecha_ingreso': i.fecha_ingreso, 'fecha_salida': i.fecha_salida,
            'origen': grupo_minimo(i.grupo), 'destino_id': destino_id,
            'destino': grupo_minimo(destino) if destino else None,
            'disposicion': f.get('disposicion', a.disposicion), 'motivo': f.get('motivo', a.motivo),
            'ejecutada': a.pk in resultados, 'puede_ejecutar': not razones, 'bloqueos': razones})
    resumen['afectaciones'] = detalles
    resumen['excepciones'] = [{'afectacion': e.afectacion_id, 'situacion': e.situacion,
        'inicio': e.fecha_inicio, 'limite': e.fecha_limite, 'motivo': e.motivo,
        'responsable': actor_minimo(e.creado_por)} for a in afectaciones for e in a.excepciones.select_related('creado_por')]
    return resumen


class AdministracionAscensoMixin:
    def consulta_administrativa(self, clase):
        s = clase(data=self.request.query_params); s.is_valid(raise_exception=True)

    @action(detail=True, methods=['get'])
    def ejecucion(self, request, pk=None):
        from .views_ascensos import EntradaVacia
        self.consulta_administrativa(EntradaVacia)
        return Response(lectura_administrativa(request.user, self.get_object()))

    @action(detail=True, methods=['get', 'post'])
    def revisiones(self, request, pk=None):
        from .views_ascensos import EntradaVacia
        self.consulta_administrativa(PaginaAdministrativa if request.method == 'GET' else EntradaVacia)
        p = self.get_object()
        if request.method == 'POST':
            if not instalacion_verificada(): raise InstalacionPendiente()
            s = CrearRevision(data=request.data); s.is_valid(raise_exception=True)
            from .servicios_ejecucion import revisar_plan
            r = revisar_plan(request.user, p.pk, **s.validated_data)
            return Response({'id': r.pk, 'numero': r.numero, 'version': r.version_progresion}, status=201)
        datos = p.revisiones_administrativas.order_by('-numero').values('id', 'numero', 'anterior_id',
            'actor_id', 'registrada_en', 'motivo', 'version_progresion', 'disposiciones')
        pagina = self.paginate_queryset(datos)
        # Huellas e identificadores personales internos no son necesarios para revisar el plan.
        for r in pagina:
            from .servicios_ejecucion import validar_evidencia_lectura
            validar_evidencia_lectura(r['disposiciones'])
            r['disposiciones'] = [{k: f[k] for k in ('afectacion', 'origen', 'disposicion', 'destino', 'motivo')}
                for f in r['disposiciones']]
        return self.get_paginated_response(pagina)

    @action(detail=True, methods=['get'])
    def resultados(self, request, pk=None):
        from .modelos_ejecucion import ResultadoAdministrativo
        self.consulta_administrativa(PaginaAdministrativa)
        datos = ResultadoAdministrativo.objects.filter(revision__progresion=self.get_object()).order_by('-pk').values(
            'id', 'revision_id', 'afectacion_id', 'origen_id', 'destino_id', 'estado', 'fecha_efectiva',
            'actor_id', 'motivo', 'registrada_en')
        return self.get_paginated_response(self.paginate_queryset(datos))

    @action(detail=True, methods=['post'])
    def ejecutar(self, request, pk=None):
        from .views_ascensos import EntradaVacia
        self.consulta_administrativa(EntradaVacia)
        p = self.get_object()
        if not instalacion_verificada(): raise InstalacionPendiente()
        s = EjecutarReubicacion(data=request.data); s.is_valid(raise_exception=True)
        d = s.validated_data
        # La revisión debe pertenecer a la URL, también durante reintentos.
        from django.shortcuts import get_object_or_404
        get_object_or_404(p.revisiones_administrativas, pk=d['revision'])
        from .servicios_movimientos import ejecutar_reubicacion
        r = ejecutar_reubicacion(request.user, d['revision'], d['version'], d['afectacion'], d['clave'], d['motivo'])
        return Response({'resultado': r.pk, 'revision': r.revision_id, 'afectacion': r.afectacion_id,
            'origen': r.origen_id, 'destino': r.destino_id, 'estado': r.estado, 'fecha_efectiva': r.fecha_efectiva})
