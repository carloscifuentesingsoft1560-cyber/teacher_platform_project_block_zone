"""B2.2: fixtures ficticias, solo mediante el ejecutor PostgreSQL aislado."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from importlib import import_module
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError as ErrorModelo
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.loader import MigrationLoader
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from cuentas.models import Usuario
from cuentas.tests.test_acreditaciones_emisoras import DatosB21
from deportistas.servicios import Conflicto
from recursos.models import FuenteDocumento, FuenteVersion, FragmentoFuente
from . import modelos_funcionales as m
from .models import TerminoActividad, Ejercicio, EjercicioVersion, PasoEjercicio
from .servicios_funcionales import proponer_perfil, proponer_correspondencia, registrar_revision


class CatalogoFuncionalTests(DatosB21, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.termino = TerminoActividad.objects.create(namespace='exigencia_funcional', codigo='fixture-b22', nombre='Exigencia ficticia no aprobada')
        fuente = FuenteDocumento.objects.create(titulo='Fuente técnica ficticia', autor=self.registrador)
        fv = FuenteVersion.objects.create(fuente=fuente, numero=1,
            referencia_externa='https://example.invalid/b22', licencia='Fixture sin datos personales')
        self.fragmento = FragmentoFuente.objects.create(fuente=fv, localizador='Sección ficticia', texto_original='Propuesta técnica sin aprobación')

    def datos_perfil(self, **cambios):
        datos = dict(actor=self.registrador, clave=uuid4(), disciplina_id=self.disciplina.pk,
            nombre='Perfil ficticio pendiente', alcance='Descripción funcional propuesta, sin aptitud individual',
            exigencias=[dict(termino_id=self.termino.pk, significado='Definición ficticia', estado_dato='desconocido', tipo='desconocido', operador='sin_dato')],
            condiciones=[dict(exigencia_indice=0, descripcion='Condición propuesta', metodo_verificacion='Verificación documental explícita')],
            adaptaciones=[dict(condicion_indice=0, alternativa='Alternativa propuesta', limites='Sin ampliación del alcance')],
            procedencias=[dict(fragmento_id=self.fragmento.pk, justificacion='Procedencia técnica ficticia')], motivo='Propuesta documental')
        datos.update(cambios)
        return datos

    def perfil(self, **cambios):
        return proponer_perfil(**self.datos_perfil(**cambios))

    def revisar(self, evento, accion='revision', **cambios):
        datos = dict(actor=self.registrador, clave=uuid4(), tipo='perfil' if isinstance(evento, m.EventoPerfilFuncional) else 'correspondencia',
            version_id=evento.version_id, numero_esperado=evento.numero, accion=accion, motivo='Revisión documental ficticia')
        datos.update(cambios)
        return registrar_revision(**datos)

    def ejercicio(self, publicar=True):
        ejercicio = Ejercicio.objects.create(codigo='fixture-ej-' + uuid4().hex[:10], nombre='Ejercicio ficticio', autor=self.titular)
        version = EjercicioVersion.objects.create(identidad=ejercicio, autor=self.titular, disciplina=self.disciplina,
            nombre='Ejercicio ficticio', objetivo='Objetivo', poblacion='Ficticia', metodologia='Demostración', descripcion='Descripción',
            riesgos='Revisión requerida', controles='Supervisión', derechos='Contenido ficticio', acceso_tecnico=True)
        PasoEjercicio.objects.create(version=version, orden=1, instrucciones='Ejercicio ficticio en suelo')
        if publicar:
            from recursos.editorial import transicion
            coordinador = Usuario.objects.filter(rol='coordinador').first()
            if coordinador is None:
                coordinador = Usuario.objects.create_user(username='coord-' + uuid4().hex[:10], rol='coordinador')
            transicion(self.titular, version, 'proponer', version.revision, uuid4())
            version.refresh_from_db()
            transicion(coordinador, version, 'aprobar', version.revision, uuid4())
            version.refresh_from_db()
        return version

    def correspondencia(self, evento=None, **cambios):
        evento = evento or self.perfil()
        if not any(k in cambios for k in ('ejercicio_id', 'tarea_id', 'actividad_id')):
            cambios['ejercicio_id'] = self.ejercicio().pk
        datos = dict(actor=self.registrador, clave=uuid4(), perfil_version_id=evento.version_id,
                     evento_perfil_id=evento.pk, motivo='Propuesta de correspondencia', justificacion='Coincidencia documental explícita')
        datos.update(cambios)
        return proponer_correspondencia(**datos)

    def rechazo_sql(self, accion, codigos=('23514',)):
        with self.assertRaises(IntegrityError) as error:
            with transaction.atomic():
                accion()
                with connection.cursor() as cursor:
                    cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
        self.assertIn(error.exception.__cause__.sqlstate, codigos)

    def test_01_perfil_completo_desconocido_sin_concesion(self):
        evento = self.perfil()
        self.assertEqual(evento.accion, 'propuesta')
        self.assertEqual(evento.version.exigencias.get().estado_dato, 'desconocido')
        self.assertEqual(evento.persona_actor_id, self.enlace_reg.persona_id)
        self.assertEqual(evento.version.procedencias.get().fragmento_id, self.fragmento.pk)
        self.assertFalse({'aprobado', 'vigente', 'autorizado'} & {f.name for f in evento.version._meta.fields})

    def test_02_version_consecutiva_y_antecesora(self):
        uno = self.perfil()
        dos = self.perfil(perfil_id=uno.version.perfil_id, numero_esperado=1)
        self.assertEqual(dos.version.anterior_id, uno.version_id)
        self.assertEqual(dos.version.numero, 2)
        self.assertEqual(uno.version.nombre, m.PerfilFuncionalVersion.objects.get(pk=uno.version_id).nombre)

    def test_03_version_esperada_obsoleta(self):
        uno = self.perfil()
        with self.assertRaises(Conflicto):
            self.perfil(perfil_id=uno.version.perfil_id, numero_esperado=0)

    def test_04_idempotencia_y_conflicto(self):
        datos = self.datos_perfil()
        uno = proponer_perfil(**datos)
        self.assertEqual(proponer_perfil(**datos).pk, uno.pk)
        with self.assertRaises(Conflicto):
            proponer_perfil(**dict(datos, nombre='Otra solicitud'))

    def test_05_revision_y_retiro_terminal(self):
        evento = self.revisar(self.perfil())
        retiro = self.revisar(evento, 'retiro')
        self.assertEqual(retiro.numero, 3)
        with self.assertRaises(ValidationError):
            self.revisar(retiro)
        with self.assertRaises(ValidationError):
            self.perfil(perfil_id=retiro.version.perfil_id, numero_esperado=1)

    def test_06_no_existe_aprobacion(self):
        evento = self.perfil()
        with self.assertRaises(ValidationError):
            self.revisar(evento, 'aprobar')
        with self.assertRaises(PermissionDenied):
            self.perfil(actor=self.titular)

    def test_07_inmutabilidad_orm_diez_modelos(self):
        for nombre in ('PerfilFuncional', 'PerfilFuncionalVersion', 'ExigenciaPerfilFuncional', 'CondicionPerfilFuncional',
                       'AdaptacionPerfilFuncional', 'ProcedenciaPerfilFuncional', 'EventoPerfilFuncional', 'CorrespondenciaFuncional',
                       'CorrespondenciaFuncionalVersion', 'EventoCorrespondenciaFuncional'):
            modelo = getattr(m, nombre)
            for operacion in (lambda: modelo(pk=1).save(), lambda: modelo(pk=1).delete(),
                              lambda: modelo.objects.all().update(id=1), lambda: modelo.objects.all().delete(),
                              lambda: modelo.objects.bulk_update([], ['id'])):
                with self.assertRaises(ErrorModelo):
                    operacion()

    def test_08_inmutabilidad_sql_diez_tablas(self):
        evento = self.perfil()
        correspondencia = self.correspondencia(evento)
        objetos = [evento, evento.version, evento.version.perfil, evento.version.exigencias.get(), evento.version.condiciones.get(),
                   evento.version.adaptaciones.get(), evento.version.procedencias.get(), correspondencia,
                   correspondencia.version, correspondencia.version.correspondencia]
        for objeto in objetos:
            for instruccion in ('UPDATE {tabla} SET id=id WHERE id=%s', 'DELETE FROM {tabla} WHERE id=%s'):
                def accion(objeto=objeto, instruccion=instruccion):
                    with connection.cursor() as cursor:
                        cursor.execute(instruccion.format(tabla=connection.ops.quote_name(objeto._meta.db_table)), [objeto.pk])
                self.rechazo_sql(accion)

    def test_09_primer_evento_diferido(self):
        perfil = self.perfil().version.perfil
        self.rechazo_sql(lambda: m.PerfilFuncionalVersion.objects.create(perfil=perfil, numero=2,
            anterior=perfil.versiones.get(), nombre='Sin evento', alcance='Debe fallar al confirmar'))

    def test_10_cabecera_incompleta_rollback(self):
        cantidad = m.PerfilFuncional.objects.count()
        self.rechazo_sql(lambda: m.PerfilFuncional.objects.create(disciplina=self.disciplina))
        self.assertEqual(m.PerfilFuncional.objects.count(), cantidad)

    def test_11_rollback_completo(self):
        cantidades = (m.PerfilFuncional.objects.count(), m.PerfilFuncionalVersion.objects.count(), m.EventoPerfilFuncional.objects.count())
        with patch('biblioteca.servicios_funcionales.registrar', side_effect=RuntimeError('Fallo de auditoría ficticio')):
            with self.assertRaises(RuntimeError):
                self.perfil()
        self.assertEqual(cantidades, (m.PerfilFuncional.objects.count(), m.PerfilFuncionalVersion.objects.count(), m.EventoPerfilFuncional.objects.count()))

    def test_12_termino_namespace_invalido(self):
        termino = TerminoActividad.objects.create(namespace='capacidad', codigo='otra', nombre='Otro vocabulario')
        datos = self.datos_perfil()
        datos['exigencias'][0]['termino_id'] = termino.pk
        self.rechazo_sql(lambda: proponer_perfil(**datos))

    def test_13_coherencia_tipo_operador_unidad(self):
        for cambios in (dict(tipo='numero'), dict(valor_texto='No debe existir'), dict(unidad_propuesta='m')):
            datos = self.datos_perfil()
            datos['exigencias'][0].update(cambios)
            self.rechazo_sql(lambda: proponer_perfil(**datos))

    def test_14_valor_numerico_propuesto(self):
        datos = self.datos_perfil()
        datos['exigencias'][0].update(estado_dato='conocido', tipo='numero', operador='lte', valor_numero=2, unidad_propuesta='unidad-ficticia')
        evento = proponer_perfil(**datos)
        self.assertEqual(evento.version.exigencias.get().valor_numero, 2)

    def test_15_significado_historico_del_termino(self):
        evento = self.perfil()
        original = evento.version.exigencias.get()
        self.rechazo_sql(lambda: TerminoActividad.objects.filter(pk=self.termino.pk).update(nombre='Nombre posterior'))
        self.termino.refresh_from_db()
        self.assertEqual(self.termino.nombre, original.nombre_historico)
        # Los términos no tienen ediciones: otro significado exige otra identidad.
        nuevo = TerminoActividad.objects.create(namespace='exigencia_funcional',
            codigo='fixture-b22-posterior', nombre='Significado posterior ficticio')
        datos = self.datos_perfil(perfil_id=evento.version.perfil_id, numero_esperado=1)
        datos['exigencias'][0].update(termino_id=nuevo.pk, significado='Definición posterior ficticia')
        posterior = proponer_perfil(**datos)
        historica = evento.version.exigencias.get()
        self.assertEqual(historica.termino_id, self.termino.pk)
        self.assertEqual(historica.codigo_historico, original.codigo_historico)
        self.assertEqual(historica.nombre_historico, 'Exigencia ficticia no aprobada')
        self.assertEqual(historica.significado, original.significado)
        self.assertEqual(posterior.version.anterior_id, evento.version_id)
        self.assertEqual(posterior.version.exigencias.get().termino_id, nuevo.pk)
        self.assertEqual(posterior.version.exigencias.get().significado, 'Definición posterior ficticia')

    def test_16_detalle_no_insertable_tras_evento(self):
        evento = self.perfil()
        self.rechazo_sql(lambda: m.ProcedenciaPerfilFuncional.objects.create(version=evento.version,
            fragmento=self.fragmento, justificacion='Inserción tardía'))

    def test_17_correspondencia_ejercicio_exacta(self):
        evento = self.perfil()
        ejercicio = self.ejercicio()
        correspondencia = self.correspondencia(evento, ejercicio_id=ejercicio.pk)
        self.assertEqual(correspondencia.version.contexto['contenido']['id'], ejercicio.pk)
        self.assertEqual(correspondencia.version.evento_perfil_id, evento.pk)

    def test_18_destino_exclusivo(self):
        evento = self.perfil()
        with self.assertRaises(ValidationError):
            self.correspondencia(evento, ejercicio_id=None)
        self.rechazo_sql(lambda: m.CorrespondenciaFuncional.objects.create())

    def test_19_referencia_inexistente(self):
        self.rechazo_sql(lambda: m.CorrespondenciaFuncional.objects.create(ejercicio_id=999999999), ('23503', '23514'))

    def test_20_disciplina_incompatible(self):
        from organizacion.models import Disciplina
        otra = Disciplina.objects.create(codigo='b22-otra', nombre='Otra disciplina ficticia')
        evento = self.perfil(disciplina_id=otra.pk)
        self.rechazo_sql(lambda: self.correspondencia(evento))

    def test_21_perfil_retirado_o_sustituido(self):
        evento = self.perfil()
        self.revisar(evento, 'retiro')
        self.rechazo_sql(lambda: self.correspondencia(evento))
        otro = self.perfil()
        self.perfil(perfil_id=otro.version.perfil_id, numero_esperado=1)
        self.rechazo_sql(lambda: self.correspondencia(otro))

    def test_22_evento_perfil_obsoleto(self):
        evento = self.perfil()
        self.revisar(evento)
        self.rechazo_sql(lambda: self.correspondencia(evento))

    def test_23_adaptacion_de_otro_perfil(self):
        evento = self.perfil()
        ajena = self.perfil().version.adaptaciones.get()
        self.rechazo_sql(lambda: self.correspondencia(evento, adaptacion_id=ajena.pk))

    def test_24_correspondencia_no_heredada_ejercicio_nuevo(self):
        self.correspondencia()
        nuevo = self.ejercicio()
        self.assertFalse(m.CorrespondenciaFuncional.objects.filter(ejercicio=nuevo).exists())

    def test_25_ejercicio_borrador_no_es_destino_estable(self):
        self.rechazo_sql(lambda: self.correspondencia(ejercicio_id=self.ejercicio(publicar=False).pk))

    def test_26_migraciones_anteriores_y_guardias(self):
        loader = MigrationLoader(connection)
        for nodo in [('cuentas', '0009_competencia_emisora_guardias_b1'),
                     ('cuentas', '0011_guardias_mandatos_acreditaciones_b2_1'),
                     ('biblioteca', '0005_guardias_catalogo_funcional_b2_2')]:
            self.assertIn(nodo, loader.applied_migrations)
        loader.graph.ensure_not_cyclic()
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_trigger WHERE tgname='zdb_b22_guardia' AND NOT tgisinternal")
            self.assertEqual(cursor.fetchone()[0], 10)
        self.rechazo_sql(lambda: self._sql('UPDATE cuentas_competenciaemisora SET alcance_propuesto=alcance_propuesto WHERE id=%s', self.b1.pk))
        self.rechazo_sql(lambda: self._sql('DELETE FROM cuentas_mandatoinstitucional WHERE id=%s', self.m.pk))

    def _sql(self, consulta, pk):
        with connection.cursor() as cursor:
            cursor.execute(consulta, [pk])

    def test_27_migracion_guardias_irreversible(self):
        operacion = import_module('biblioteca.migrations.0005_guardias_catalogo_funcional_b2_2').Migration.operations[0]
        self.assertFalse(operacion.reversible)
        with self.assertRaises(NotImplementedError):
            operacion.database_backwards('biblioteca', None, None, None)

    def test_28_evento_sql_aprobacion_prohibida(self):
        evento = self.perfil()
        self.rechazo_sql(lambda: m.EventoPerfilFuncional.objects.create(version=evento.version, anterior=evento,
            numero=2, accion='aprobado', actor=self.registrador, persona_actor=self.enlace_reg.persona,
            enlace_actor=self.enlace_reg, version_enlace_actor=1, evidencia_actor=self.enlace_reg.evidencia,
            clave=uuid4(), solicitud={}, motivo='No permitido'))

    def test_29_correspondencia_revision_retiro_y_versiones(self):
        evento = self.perfil()
        correspondencia = self.correspondencia(evento)
        nueva = self.correspondencia(evento, ejercicio_id=correspondencia.version.correspondencia.ejercicio_id,
            correspondencia_id=correspondencia.version.correspondencia_id, numero_esperado=1)
        self.assertEqual(nueva.version.anterior_id, correspondencia.version_id)
        retiro = self.revisar(nueva, 'retiro')
        with self.assertRaises(ValidationError):
            self.revisar(retiro)

    def test_30_concurrencia_real_version_esperada(self):
        evento = self.perfil()
        barrera = Barrier(2)
        datos = self.datos_perfil(perfil_id=evento.version.perfil_id, numero_esperado=1)

        def trabajo():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout='5s'")
                    cursor.execute("SET statement_timeout='15s'")
                barrera.wait(timeout=10)
                try:
                    return ('creada', proponer_perfil(**dict(datos, clave=uuid4())).version.numero)
                except Conflicto:
                    return ('conflicto', None)
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as equipo:
            futuros = [equipo.submit(trabajo) for _ in range(2)]
            resultados = [f.result(timeout=25) for f in futuros]
        self.assertCountEqual([r[0] for r in resultados], ['creada', 'conflicto'])
        self.assertEqual(m.PerfilFuncionalVersion.objects.filter(perfil_id=evento.version.perfil_id).count(), 2)

    def sesion_preparada(self, finalizar=False):
        from organizacion.models import Nivel, Periodo, Grupo, Asignacion
        from sesiones.servicios import crear_sesion, comandar
        from sesiones.ejecucion import operar
        from sesiones.models import EjecucionSesion
        fecha = timezone.localdate() - timedelta(days=1)
        nivel = Nivel.objects.create(disciplina=self.disciplina, codigo='b22-nivel', nombre='Nivel ficticio')
        periodo = Periodo.objects.create(codigo='b22-periodo', nombre='Periodo ficticio', fecha_inicio=fecha, fecha_fin=fecha)
        grupo = Grupo.objects.create(codigo='b22-grupo', nombre='Grupo ficticio', disciplina=self.disciplina, nivel=nivel, periodo=periodo, cupo_maximo=2)
        Asignacion.objects.create(grupo=grupo, usuario=self.titular, tipo='profesor', fecha_inicio=fecha)
        sesion = crear_sesion(actor=self.titular, clave=uuid4(), grupo_id=grupo.pk, profesor_id=self.titular.pk,
            fecha=fecha, hora_inicio='10:00', hora_fin='11:00')
        sesion = comandar(actor=self.titular, sesion_id=sesion.pk, version=sesion.version, clave=uuid4(), operacion='planificar',
            datos=dict(objetivo='Plan ficticio', tareas=[dict(fase=f, minutos=20, instrucciones='Tarea ficticia') for f in ('inicial','central','final')]))
        plan = sesion.planes.get()
        tareas = list(plan.tareas.all())
        actividades = [dict(tarea=t.pk, resultado='realizada', minutos=10, descripcion='Actividad ficticia') for t in tareas]
        actividades[1].update(resultado='modificada', adaptacion_metodologica='Cambio ficticio explícito')
        actividades[2].update(resultado='omitida', minutos=0, motivo_omision='Sin práctica')
        sesion = operar(actor=self.titular, sesion_id=sesion.pk, version=sesion.version, clave=uuid4(), operacion='guardar_ejecucion',
            datos=dict(plan=plan.pk, inicio=f'{fecha}T10:00:00-05:00', fin=f'{fecha}T10:45:00-05:00', actividades=actividades))
        if finalizar:
            sesion = operar(actor=self.titular, sesion_id=sesion.pk, version=sesion.version, clave=uuid4(), operacion='finalizar_ejecucion', datos={})
        return sesion, plan, EjecucionSesion.objects.get(sesion=sesion)

    def test_31_tarea_sellada_y_proteccion_historica(self):
        sesion, plan, ejecucion = self.sesion_preparada()
        tarea = plan.tareas.first()
        evento = self.correspondencia(tarea_id=tarea.pk)
        self.assertEqual(evento.version.contexto['contenido']['id'], tarea.pk)
        self.rechazo_sql(lambda: self._sql('UPDATE sesiones_tareasesion SET instrucciones=instrucciones WHERE id=%s', tarea.pk))
        self.assertFalse(m.CorrespondenciaFuncional.objects.filter(actividad__ejecucion=ejecucion).exists())

    def test_32_actividad_abierta_rechazada(self):
        sesion, plan, ejecucion = self.sesion_preparada()
        self.rechazo_sql(lambda: self.correspondencia(actividad_id=ejecucion.actividades.first().pk))

    def test_33_actividad_finalizada_y_adaptacion_explicita(self):
        sesion, plan, ejecucion = self.sesion_preparada(finalizar=True)
        perfil = self.perfil()
        realizada = ejecucion.actividades.get(resultado='realizada')
        evento = self.correspondencia(perfil, actividad_id=realizada.pk)
        self.assertEqual(evento.version.contexto['contenido']['id'], realizada.pk)
        modificada = ejecucion.actividades.get(resultado='modificada')
        self.rechazo_sql(lambda: self.correspondencia(perfil, actividad_id=modificada.pk))
        self.correspondencia(perfil, actividad_id=modificada.pk, adaptacion_id=perfil.version.adaptaciones.get().pk)
        self.rechazo_sql(lambda: self.correspondencia(perfil, actividad_id=ejecucion.actividades.get(resultado='omitida').pk))
        self.rechazo_sql(lambda: self._sql('UPDATE sesiones_actividadejecutada SET descripcion=descripcion WHERE id=%s', realizada.pk))

    def test_34_realizada_sigue_bloqueada(self):
        from sesiones.ejecucion import verificar_autorizacion_funcional
        sesion, plan, ejecucion = self.sesion_preparada(finalizar=True)
        with self.assertRaises(PermissionDenied):
            verificar_autorizacion_funcional(sesion, ejecucion)
        self.rechazo_sql(lambda: self._sql("UPDATE sesiones_sesion SET estado='realizada' WHERE id=%s", sesion.pk))

    def test_35_idempotencia_concurrente(self):
        barrera = Barrier(2)
        datos = self.datos_perfil()

        def trabajo():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout='5s'")
                    cursor.execute("SET statement_timeout='15s'")
                barrera.wait(timeout=10)
                return proponer_perfil(**datos).pk
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as equipo:
            futuros = [equipo.submit(trabajo) for _ in range(2)]
            resultados = [f.result(timeout=25) for f in futuros]
        self.assertEqual(resultados[0], resultados[1])

    def test_36_condiciones_integridad_y_rollback(self):
        datos = self.datos_perfil()
        datos['adaptaciones'][0]['condicion_indice'] = 3
        with self.assertRaises(ValidationError):
            proponer_perfil(**datos)
        self.assertEqual(m.PerfilFuncional.objects.count(), 0)

    def test_37_contexto_falso_rechazado_sql(self):
        from biblioteca.servicios_funcionales import _actor
        evento = self.perfil()
        ejercicio = self.ejercicio()

        def accion():
            _actor(self.registrador)
            cabecera = m.CorrespondenciaFuncional.objects.create(ejercicio=ejercicio)
            m.CorrespondenciaFuncionalVersion.objects.create(correspondencia=cabecera, numero=1,
                perfil_version=evento.version, evento_perfil=evento, contexto={'falso': True}, justificacion='Falso')
        self.rechazo_sql(accion)
