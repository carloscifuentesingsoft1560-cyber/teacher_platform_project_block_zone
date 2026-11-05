"""B2.3 A: fixtures ficticias y PostgreSQL temporal; sin concesión operativa."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from importlib import import_module
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4
from django.core.exceptions import ValidationError as ErrorModelo
from django.db import close_old_connections, connection, transaction
from django.db.migrations.loader import MigrationLoader
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from cuentas.models import Persona, EnlaceIdentidad
from cuentas.tests.test_acreditaciones_emisoras import DatosB21
from biblioteca import test_funcional as b22
from biblioteca import modelos_funcionales as catalogo
from biblioteca.models import TerminoActividad
from biblioteca.servicios_funcionales import registrar_revision
from recursos.models import FuenteDocumento, FuenteVersion, FragmentoFuente
from auditoria.models import CambioAdministrativo
from .models import Deportista
from .servicios import Conflicto
from . import modelos_autorizaciones_funcionales as m
from .servicios_autorizaciones_funcionales import proponer, revisar


class ExpedientesFuncionalesTests(DatosB21, TransactionTestCase):
    # Reutilizar solo helpers ficticios, sin heredar ni ejecutar las suites anteriores.
    datos_perfil = b22.CatalogoFuncionalTests.datos_perfil
    perfil = b22.CatalogoFuncionalTests.perfil
    ejercicio = b22.CatalogoFuncionalTests.ejercicio
    correspondencia = b22.CatalogoFuncionalTests.correspondencia
    rechazo_sql = b22.CatalogoFuncionalTests.rechazo_sql
    _sql = b22.CatalogoFuncionalTests._sql
    sesion_preparada = b22.CatalogoFuncionalTests.sesion_preparada

    def setUp(self):
        super().setUp()
        self.termino = TerminoActividad.objects.create(namespace='exigencia_funcional', codigo='fixture-b23', nombre='Propuesta ficticia')
        fuente = FuenteDocumento.objects.create(titulo='Fuente técnica ficticia', autor=self.registrador)
        version = FuenteVersion.objects.create(fuente=fuente, numero=1, referencia_externa='https://example.invalid/b23', licencia='Fixture')
        self.fragmento = FragmentoFuente.objects.create(fuente=version, localizador='Sección ficticia')
        self.p = self.perfil()
        self.destinatario = Deportista.objects.create(nombres='Ficticio', apellidos='B23', fecha_nacimiento=date(2010, 1, 1),
            creado_por=self.registrador, actualizado_por=self.registrador)
        persona = Persona.objects.create(creada_por=self.registrador)
        self.enlace_dest = EnlaceIdentidad.objects.create(persona=persona, deportista=self.destinatario,
            evidencia=uuid4(), acreditado_por=self.registrador)

    def datos(self, **cambios):
        # DatosB21 utiliza self.datos() al construir sus fundamentos.
        if not hasattr(self, 'enlace_dest'):
            return DatosB21.datos(self)
        condicion = self.p.version.condiciones.get()
        adaptacion = self.p.version.adaptaciones.get()
        datos = dict(actor=self.registrador, clave=uuid4(), enlace_destinatario_id=self.enlace_dest.pk,
            disciplina_id=self.disciplina.pk, acreditacion_id=self.a.pk, evento_acreditacion_id=self.evento_a.pk,
            desde_propuesta=timezone.now(), hasta_propuesta=timezone.now()+timedelta(days=1),
            alcances=[dict(perfil_version_id=self.p.version_id, evento_perfil_id=self.p.pk,
                condiciones=[dict(condicion_id=condicion.pk, modalidad='condicionar')],
                adaptaciones=[dict(condicion_id=condicion.pk, adaptacion_id=adaptacion.pk)])],
            evidencias=[dict(referencia=str(uuid4()), registro_custodia=str(uuid4()), huella_documento='a'*64)])
        datos.update(cambios)
        return datos

    def propuesta(self, **cambios):
        return proponer(**self.datos(**cambios))

    def revision(self, evento, **cambios):
        datos = dict(actor=self.registrador, clave=uuid4(), expediente_id=evento.expediente_id,
            numero_esperado=evento.numero, accion='revision')
        datos.update(cambios)
        return revisar(**datos)

    def test_01_propuesta_documental_identidad_y_evidencia(self):
        evento = self.propuesta()
        self.assertEqual(evento.accion, 'propuesta')
        self.assertEqual(evento.expediente.persona_id, self.enlace_dest.persona_id)
        self.assertEqual(evento.version.acreditacion_id, self.a.pk)
        self.assertEqual(evento.version.evidencias.count(), 1)
        self.assertEqual(len(evento.huella), 64)
        self.assertFalse({'aprobado', 'vigente', 'autorizado'} & {f.name for f in evento.version._meta.fields})

    def test_02_rol_administrativo_no_basta(self):
        with self.assertRaises(PermissionDenied):
            self.propuesta(actor=self.otro)
        with self.assertRaises(PermissionDenied):
            self.propuesta(actor=self.titular)

    def test_03_separacion_de_personas(self):
        otra = Deportista.objects.create(nombres='Ficticio', apellidos='Otra cuenta', fecha_nacimiento=date(2010,1,1),
            creado_por=self.registrador, actualizado_por=self.registrador)
        enlace = EnlaceIdentidad.objects.create(persona=self.enlace_reg.persona, deportista=otra, evidencia=uuid4(), acreditado_por=self.registrador)
        self.rechazo_sql(lambda: self.propuesta(enlace_destinatario_id=enlace.pk))

    def test_04_destinatario_emisor_no_permitido(self):
        enlace = self.enlace_dest
        from cuentas.servicios_identidad import revocar_enlace
        revocar_enlace(self.registrador, enlace.pk, enlace.version)
        nuevo = EnlaceIdentidad.objects.create(persona=self.enlace_cand.persona, deportista=self.destinatario,
            evidencia=uuid4(), acreditado_por=self.registrador)
        self.rechazo_sql(lambda: self.propuesta(enlace_destinatario_id=nuevo.pk))

    def test_05_versiones_consecutivas(self):
        uno = self.propuesta()
        dos = self.propuesta(expediente_id=uno.expediente_id, numero_esperado=1)
        self.assertEqual(dos.version.anterior_id, uno.version_id)
        self.assertEqual(dos.anterior_id, uno.pk)
        with self.assertRaises(Conflicto):
            self.propuesta(expediente_id=uno.expediente_id, numero_esperado=1)

    def test_06_retiro_terminal(self):
        uno = self.propuesta()
        retiro = self.revision(uno, accion='retiro')
        with self.assertRaises(ValidationError):
            self.revision(retiro)
        with self.assertRaises(ValidationError):
            self.propuesta(expediente_id=uno.expediente_id, numero_esperado=1)

    def test_07_prohibicion_aprobar(self):
        uno = self.propuesta()
        with self.assertRaises(ValidationError):
            self.revision(uno, accion='aprobar')
        self.rechazo_sql(lambda: self._sql("UPDATE deportistas_eventoexpedientefuncional SET accion='aprobado' WHERE id=%s", uno.pk))

    def test_08_inmutabilidad_orm(self):
        for nombre in ('ExpedienteAutorizacionFuncional','PropuestaDecisionFuncionalVersion','AlcanceDecisionFuncional',
                       'CondicionDecisionFuncional','AdaptacionDecisionFuncional','ReferenciaEvidenciaFuncional','EventoExpedienteFuncional'):
            modelo = getattr(m, nombre)
            self.assertEqual(modelo._meta.default_permissions, ())
            for operacion in (lambda: modelo(pk=1).save(), lambda: modelo(pk=1).delete(),
                              lambda: modelo.objects.update(id=1), lambda: modelo.objects.all().delete(),
                              lambda: modelo.objects.bulk_update([], ['id'])):
                with self.assertRaises(ErrorModelo):
                    operacion()

    def test_09_inmutabilidad_sql(self):
        e = self.propuesta()
        alcance = e.version.alcances.get()
        for objeto in (e,e.expediente,e.version,alcance,alcance.condiciones.get(),alcance.adaptaciones.get(),e.version.evidencias.get()):
            for consulta in ('UPDATE {tabla} SET id=id WHERE id=%s','DELETE FROM {tabla} WHERE id=%s'):
                self.rechazo_sql(lambda: self._sql(consulta.format(tabla=objeto._meta.db_table), objeto.pk))

    def test_10_cabecera_sin_primera_version(self):
        self.rechazo_sql(lambda: m.ExpedienteAutorizacionFuncional.objects.create(deportista=self.destinatario,
            persona=self.enlace_dest.persona,enlace_identidad=self.enlace_dest,version_enlace=1,
            evidencia_identidad=self.enlace_dest.evidencia,disciplina=self.disciplina))

    def test_11_auditoria_obligatoria_y_rollback(self):
        cantidad = m.ExpedienteAutorizacionFuncional.objects.count()
        with patch('deportistas.servicios_autorizaciones_funcionales.registrar', return_value=None):
            self.rechazo_sql(lambda: self.propuesta())
        self.assertEqual(m.ExpedienteAutorizacionFuncional.objects.count(), cantidad)

    def test_12_auditoria_sin_datos_sensibles(self):
        evento = self.propuesta()
        audit = CambioAdministrativo.objects.get(entidad=evento._meta.label_lower, identificador=evento.pk)
        self.assertEqual(audit.campos, ['accion','numero'])
        self.assertEqual(audit.accion,'propuesta')

    def test_13_idempotencia_huella(self):
        datos = self.datos()
        uno = proponer(**datos)
        self.assertEqual(proponer(**datos).pk,uno.pk)
        with self.assertRaises(Conflicto):
            proponer(**dict(datos,hasta_propuesta=datos['hasta_propuesta']+timedelta(hours=1)))

    def test_14_b21_evento_obsoleto(self):
        from cuentas.servicios_competencias_emisoras import registrar_evento
        registrar_evento(actor=self.registrador,tipo='acreditacion',expediente_id=self.a.pk,numero_esperado=1,
            clave=uuid4(),accion='revision',**DatosB21.datos(self))
        self.rechazo_sql(lambda: self.propuesta())

    def test_15_b1_fundamento_retirado(self):
        from cuentas.models import EventoCompetenciaEmisora
        EventoCompetenciaEmisora.objects.create(competencia=self.b1,numero=2,anterior=self.evento_b1,accion='retiro',
            actor=self.registrador,clave=uuid4(),motivo='Fixture',referencia_evidencia=uuid4(),
            vigente_desde_propuesta=self.desde,vigente_hasta_propuesta=self.hasta)
        self.rechazo_sql(lambda: self.propuesta())

    def test_16_perfil_retirado(self):
        registrar_revision(actor=self.registrador,clave=uuid4(),tipo='perfil',version_id=self.p.version_id,
            numero_esperado=1,accion='retiro',motivo='Fixture')
        self.rechazo_sql(lambda: self.propuesta())

    def test_17_correspondencia_exacta(self):
        correspondencia = self.correspondencia(self.p)
        datos = self.datos()
        datos['alcances'][0].update(correspondencia_version_id=correspondencia.version_id,evento_correspondencia_id=correspondencia.pk)
        evento = proponer(**datos)
        self.assertEqual(evento.version.alcances.get().correspondencia_version_id,correspondencia.version_id)

    def test_18_correspondencia_incompatible(self):
        correspondencia = self.correspondencia(self.perfil())
        datos = self.datos()
        datos['alcances'][0].update(correspondencia_version_id=correspondencia.version_id,evento_correspondencia_id=correspondencia.pk)
        self.rechazo_sql(lambda: proponer(**datos))

    def test_19_condicion_ajena(self):
        ajena = self.perfil().version.condiciones.get()
        datos = self.datos()
        datos['alcances'][0]['condiciones'][0]['condicion_id'] = ajena.pk
        self.rechazo_sql(lambda: proponer(**datos))

    def test_20_adaptacion_ajena(self):
        datos = self.datos()
        datos['alcances'][0]['adaptaciones'][0]['adaptacion_id'] = self.perfil().version.adaptaciones.get().pk
        self.rechazo_sql(lambda: proponer(**datos))

    def test_21_adaptacion_no_supera_exclusion(self):
        datos = self.datos()
        datos['alcances'][0]['condiciones'][0]['modalidad']='excluir'
        self.rechazo_sql(lambda: proponer(**datos))

    def test_22_fechas_invalidas_y_emision_futura(self):
        for cambios in (dict(hasta_propuesta=timezone.now()-timedelta(days=1)),
                        dict(emitida_en_declarada=timezone.now()+timedelta(hours=1),desde_propuesta=timezone.now()+timedelta(hours=2))):
            self.rechazo_sql(lambda: self.propuesta(**cambios))

    def test_23_evidencia_opaca_no_urls(self):
        datos = self.datos()
        datos['evidencias'][0]['referencia']='https://example.invalid/documento'
        with self.assertRaises(ValidationError):
            proponer(**datos)
        self.assertEqual(m.ExpedienteAutorizacionFuncional.objects.count(),0)

    def test_24_sin_alcance_o_evidencia(self):
        self.rechazo_sql(lambda: self.propuesta(alcances=[]))
        self.rechazo_sql(lambda: self.propuesta(evidencias=[]))

    def test_25_identidad_revocada_impide_revision_no_retiro(self):
        from cuentas.servicios_identidad import revocar_enlace
        evento = self.propuesta()
        revocar_enlace(self.registrador,self.enlace_dest.pk,self.enlace_dest.version)
        self.rechazo_sql(lambda: self.revision(evento))
        self.assertEqual(self.revision(evento,accion='retiro').accion,'retiro')

    def test_26_concurrencia_version_esperada(self):
        evento = self.propuesta()
        datos = self.datos(expediente_id=evento.expediente_id,numero_esperado=1)
        barrera = Barrier(2)

        def trabajo():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout='5s'")
                    cursor.execute("SET statement_timeout='15s'")
                barrera.wait(timeout=10)
                try:
                    proponer(**dict(datos,clave=uuid4()))
                    return 'creada'
                except Conflicto:
                    return 'conflicto'
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as equipo:
            futuros=[equipo.submit(trabajo) for _ in range(2)]
            resultados=[f.result(timeout=25) for f in futuros]
        self.assertCountEqual(resultados,['creada','conflicto'])

    def test_27_concurrencia_idempotente(self):
        datos=self.datos()
        barrera=Barrier(2)

        def trabajo():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout='5s'")
                    cursor.execute("SET statement_timeout='15s'")
                barrera.wait(timeout=10)
                return proponer(**datos).pk
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as equipo:
            futuros=[equipo.submit(trabajo) for _ in range(2)]
            resultados=[f.result(timeout=25) for f in futuros]
        self.assertEqual(resultados[0],resultados[1])

    def test_28_bloqueo_realizada(self):
        b22.CatalogoFuncionalTests.test_34_realizada_sigue_bloqueada(self)

    def test_29_guardias_anteriores_instaladas(self):
        loader=MigrationLoader(connection)
        loader.graph.ensure_not_cyclic()
        for nodo in [('cuentas','0009_competencia_emisora_guardias_b1'),('cuentas','0011_guardias_mandatos_acreditaciones_b2_1'),
                     ('biblioteca','0005_guardias_catalogo_funcional_b2_2'),('deportistas','0005_guardias_expedientes_funcionales_b2_3')]:
            self.assertIn(nodo,loader.applied_migrations)
        self.rechazo_sql(lambda: self._sql('UPDATE cuentas_competenciaemisora SET id=id WHERE id=%s',self.b1.pk))
        self.rechazo_sql(lambda: self._sql('UPDATE cuentas_acreditacionemisora SET id=id WHERE id=%s',self.a.pk))
        self.rechazo_sql(lambda: self._sql('UPDATE biblioteca_perfilfuncionalversion SET id=id WHERE id=%s',self.p.version_id))

    def test_30_irreversibilidad(self):
        operacion=import_module('deportistas.migrations.0005_guardias_expedientes_funcionales_b2_3').Migration.operations[0]
        self.assertFalse(operacion.reversible)
        with self.assertRaises(NotImplementedError):
            operacion.database_backwards('deportistas',None,None,None)

    def test_31_detalle_sellado(self):
        evento=self.propuesta()
        self.rechazo_sql(lambda: m.ReferenciaEvidenciaFuncional.objects.create(version=evento.version,
            referencia=uuid4(),registro_custodia=uuid4(),huella_documento='b'*64))

    def test_32_no_se_guarda_solicitud_ni_motivo_libre(self):
        for modelo in (m.EventoExpedienteFuncional,m.PropuestaDecisionFuncionalVersion,m.ReferenciaEvidenciaFuncional):
            self.assertFalse({'solicitud','motivo','diagnostico','url','ruta'} & {f.name for f in modelo._meta.fields})
