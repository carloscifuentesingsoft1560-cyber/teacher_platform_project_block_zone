"""Movimientos institucionales exclusivamente en PostgreSQL temporal aislado."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch
from django.test import TestCase, TransactionTestCase
from django.db import transaction, connection, DatabaseError, close_old_connections, connections
from rest_framework.exceptions import APIException, PermissionDenied
from deportistas.servicios import Conflicto
from .test_ejecucion_b3_b1 import DatosEjecucion
from .models import Inscripcion, ReservaCupo, EventoInscripcion
from .modelos_ejecucion import ResultadoAdministrativo
from .modelos_ascensos import AfectacionInscripcion
from .servicios_ejecucion import consultar_ejecucion, registrar_resultado
from .servicios_movimientos import ejecutar_reubicacion
from .servicios_ascensos import autorizar_excepcion, decidir_progresion
from organizacion.models import Grupo


class DatosMovimiento(DatosEjecucion):
    def iniciar_movimiento(self):
        self.aprobada()
        self.r = self.revisar(filas=self.filas('reubicar'))
        self.p.refresh_from_db()
        self.aid = self.p.afectaciones.get().pk
        self.c.force_authenticate(self.admin)

    def ejecutar(self, actor=None, clave=None, **datos):
        self.p.refresh_from_db()
        return ejecutar_reubicacion(actor or self.admin, self.r.pk, self.p.version, self.aid,
            clave or uuid4(), 'Movimiento institucional ficticio', **datos)


class MovimientosB3B2(DatosMovimiento, TestCase):
    def setUp(self):
        self.iniciar_movimiento()

    def test_movimiento_valido_historial_y_estado(self):
        r = self.ejecutar()
        self.assertEqual(r.estado, 'ejecutada')
        self.origen.refresh_from_db()
        self.assertEqual((self.origen.estado, self.origen.fecha_salida), ('finalizada', self.hoy))
        self.assertEqual(r.destino.inscripcion_anterior_id, self.origen.pk)
        self.assertEqual(r.destino.grupo_id, self.l.pk)
        resumen = consultar_ejecucion(self.coord, self.p.pk)
        self.assertEqual(resumen['estado_ejecucion'], 'ejecutado')
        self.assertFalse(resumen['cerrado'])
        self.assertTrue(resumen['puede_cerrar'])
        self.assertEqual(EventoInscripcion.objects.filter(tipo='traslado_origen').count(), 1)

    def test_administrador_ejecuta_pero_no_aprueba(self):
        with self.assertRaises(PermissionDenied):
            decidir_progresion(self.admin,self.p.pk,self.p.version,True,'No corresponde')
        self.assertEqual(self.ejecutar(self.admin).actor_id,self.admin.pk)

    def test_profesor_no_ejecuta(self):
        with self.assertRaises(PermissionDenied):
            self.ejecutar(self.prof)

    def test_idempotencia_y_otra_clave_no_duplica(self):
        clave = uuid4(); r = self.ejecutar(clave=clave)
        self.assertEqual(self.ejecutar(clave=clave).pk,r.pk)
        with self.assertRaises(Conflicto): self.ejecutar()
        self.assertEqual(Inscripcion.objects.count(),2)

    def test_cupo_completo_revierte_cierre(self):
        self.inscribir(persona=self.persona_nueva('Otra A'),grupo=self.l)
        self.inscribir(persona=self.persona_nueva('Otra B'),grupo=self.l)
        antes=self.inventario_deportivo()
        with self.assertRaises(Conflicto): self.ejecutar()
        self.assertEqual(self.inventario_deportivo(),antes)

    def test_destino_inactivo_o_eliminado(self):
        Grupo.objects.filter(pk=self.l.pk).update(activo=False)
        with self.assertRaises(Conflicto): self.ejecutar()

    def test_contexto_cambiado_sin_version(self):
        Grupo.objects.filter(pk=self.a.pk).update(cupo_maximo=3)
        with self.assertRaises(Conflicto): self.ejecutar()

    def test_fallo_despues_del_cierre_revierte_todo(self):
        antes=self.inventario_deportivo()
        with patch('inscripciones.servicios.crear_bajo_bloqueo', side_effect=RuntimeError('Fallo aislado')):
            with self.assertRaises(RuntimeError): self.ejecutar()
        self.assertEqual(self.inventario_deportivo(),antes)
        self.assertFalse(ResultadoAdministrativo.objects.exists())

    def test_estado_progresion_pendiente_o_rechazado(self):
        # No reescribir una decisión: crear fixtures independientes por rol docente.
        from .servicios_ascensos import proponer_progresion
        persona=self.persona_nueva('Otra')
        i=self.inscribir(persona=persona,grupo=self.b)
        p=proponer_progresion(self.prof,i.pk,self.n2,'Pendiente')
        with self.assertRaises(Conflicto):
            from .servicios_ejecucion import revisar_plan
            revisar_plan(self.admin,p.pk,p.version,[],'Sin aprobación')

    def test_futuro_o_mismo_dia_rechazado(self):
        with self.assertRaises(APIException): self.ejecutar(fecha=self.hoy+timedelta(days=1))
        Inscripcion.objects.filter(pk=self.origen.pk).update(fecha_ingreso=self.hoy)
        with self.assertRaises(Conflicto): self.ejecutar()

    def test_reserva_no_se_libera_ni_reanuda(self):
        self.post(f'inscripciones/{self.origen.pk}/suspender/',{'version':1,'motivo':'Pausa','fecha_vencimiento':str(self.hoy+timedelta(days=3))})
        antes=self.inventario_deportivo()
        with self.assertRaises(Conflicto): self.ejecutar()
        self.assertEqual(self.inventario_deportivo(),antes)

    def test_update_sql_no_simula_ejecucion(self):
        r=self.ejecutar()
        with self.assertRaises(DatabaseError),transaction.atomic(),connection.cursor() as c:
            c.execute("UPDATE public.inscripciones_resultadoadministrativo SET fecha_efectiva=fecha_efectiva+1 WHERE id=%s",[r.pk])

    def agregar_segunda(self, excepcion=True):
        i=self.inscribir(grupo=self.b)
        a=AfectacionInscripcion.objects.create(progresion=self.p,inscripcion=i,version_observada=i.version,situacion_observada='activa')
        if excepcion:
            self.p.refresh_from_db()
            autorizar_excepcion(self.coord,self.p.pk,self.p.version,a.pk,'Permanencia temporal',self.hoy,self.hoy+timedelta(days=2))
        filas=self.filas('reubicar')
        for f in filas:
            if f['afectacion']==a.pk:
                f['disposicion']='pendiente';f.pop('destino')
        self.r=self.revisar(filas=filas)
        return i,a

    def test_una_de_dos_con_pendiente_y_excepcion(self):
        i,a=self.agregar_segunda()
        antes=Inscripcion.objects.filter(pk=i.pk).values().get()
        self.ejecutar(self.admin)
        self.assertEqual(Inscripcion.objects.filter(pk=i.pk).values().get(),antes)
        resumen=consultar_ejecucion(self.coord,self.p.pk)
        self.assertEqual(resumen['estado_ejecucion'],'parcialmente_ejecutado')
        self.assertIn(a.pk,resumen['pendientes'])
        self.assertFalse(resumen['cerrado']);self.assertFalse(resumen['puede_cerrar'])

    def test_pendiente_sin_excepcion_no_permite_mezcla(self):
        self.agregar_segunda(excepcion=False)
        antes=self.inventario_deportivo()
        with self.assertRaises(Conflicto):self.ejecutar()
        self.assertEqual(self.inventario_deportivo(),antes)

    def test_segundo_movimiento_con_revision_nueva_no_pierde_primero(self):
        i,a=self.agregar_segunda();primero=self.ejecutar()
        nuevo=self.grupo('segundo-destino','14:00','15:00',self.n2)
        filas=self.filas('reubicar')
        next(f for f in filas if f['afectacion']==a.pk)['destino']=nuevo.pk
        self.r=self.revisar(filas=filas);self.aid=a.pk
        segundo=self.ejecutar()
        self.assertNotEqual(primero.pk,segundo.pk)
        resumen=consultar_ejecucion(self.coord,self.p.pk)
        self.assertEqual(resumen['estado_ejecucion'],'ejecutado')
        self.assertFalse(resumen['puede_cerrar'])  # Excepción aún abierta: no revocación automática.
        self.assertEqual(ResultadoAdministrativo.objects.filter(estado='ejecutada').count(),2)

    def test_excepcion_vencida_bloquea_estado_intermedio(self):
        i,a=self.agregar_segunda()
        with patch('inscripciones.servicios_movimientos.hoy_bogota',return_value=self.hoy+timedelta(days=3)):
            with self.assertRaises(Conflicto):self.ejecutar()

    def test_suspension_revisada_no_se_transfiere(self):
        self.post(f'inscripciones/{self.origen.pk}/suspender/',{'version':1,'motivo':'Pausa','fecha_vencimiento':str(self.hoy+timedelta(days=3))})
        self.r=self.revisar(filas=self.filas('reubicar'))
        antes=self.inventario_deportivo()
        with self.assertRaises(Conflicto):self.ejecutar()
        self.assertEqual(self.inventario_deportivo(),antes)

    def test_alta_futura_revisada_no_se_anticipa(self):
        Inscripcion.objects.filter(pk=self.origen.pk).update(fecha_ingreso=self.hoy+timedelta(days=1))
        self.r=self.revisar(filas=self.filas('reubicar'))
        with self.assertRaises(Conflicto):self.ejecutar()

    def test_cruce_horario_aparecido_tras_revision(self):
        # Otra disciplina es relevante para horarios, aunque no integre las afectaciones.
        from organizacion.models import Disciplina,Nivel
        otra=Disciplina.objects.create(codigo='otra-movimiento',nombre='Otra')
        nivel=Nivel.objects.create(disciplina=otra,codigo='otro',nombre='Otro')
        g=self.grupo('cruce-externo','12:30','13:30')
        Grupo.objects.filter(pk=g.pk).update(disciplina=otra,nivel=nivel);g.refresh_from_db()
        self.inscribir(grupo=g)
        antes=self.inventario_deportivo()
        with self.assertRaises(APIException):self.ejecutar()
        self.assertEqual(self.inventario_deportivo(),antes)

    def test_destino_eliminado_bloquea_ejecucion(self):
        g=self.grupo('borrable','14:00','15:00',self.n2)
        filas=self.filas('reubicar');filas[0]['destino']=g.pk
        self.r=self.revisar(filas=filas)
        g.horarios.all().delete();g.delete()
        with self.assertRaises(Conflicto):self.ejecutar()

    def test_grupos_con_historial_no_se_borran(self):
        from django.db.models.deletion import ProtectedError
        r=self.ejecutar()
        with self.assertRaises(ProtectedError):r.destino.grupo.delete()
        self.assertTrue(Grupo.objects.filter(pk=r.destino.grupo_id).exists())

    def test_cupos_cambian_por_inscripcion_no_por_plan(self):
        from .servicios import ocupacion_maxima
        self.assertEqual(ocupacion_maxima(self.a,inicio=self.hoy),1)
        self.assertEqual(ocupacion_maxima(self.l,inicio=self.hoy),0)
        self.ejecutar()
        self.assertEqual(ocupacion_maxima(self.a,inicio=self.hoy),0)
        self.assertEqual(ocupacion_maxima(self.l,inicio=self.hoy),1)

    def test_resultado_pendiente_exige_revision_explicita(self):
        self.p.refresh_from_db()
        registrar_resultado(self.admin,self.r.pk,self.p.version,self.aid,uuid4(),'Evidencia pendiente')
        with self.assertRaises(Conflicto):self.ejecutar()
        self.r=self.revisar(filas=self.filas('reubicar'))
        self.assertEqual(self.ejecutar().estado,'ejecutada')

    def test_version_obsoleta_rechazada(self):
        with self.assertRaises(Conflicto):
            ejecutar_reubicacion(self.admin,self.r.pk,self.p.version-1,self.aid,uuid4(),'Obsoleta')

    def test_clave_invalida_y_revision_inexistente(self):
        with self.assertRaises(APIException):self.ejecutar(clave='no-es-uuid')
        with self.assertRaises(APIException):
            ejecutar_reubicacion(self.admin,999999,self.p.version,self.aid,uuid4(),'No disponible')

    def test_no_redefinir_movimiento_ejecutado(self):
        self.ejecutar()
        with self.assertRaises(Conflicto):self.revisar(filas=self.filas('pendiente'))

    def test_horario_cambiado_despues_de_validar_revierte(self):
        self.agregar_segunda()
        from .servicios import crear_bajo_bloqueo
        def cambiar_y_crear(*args,**kwargs):
            self.l.horarios.update(hora_inicio='11:30',hora_fin='12:30')
            return crear_bajo_bloqueo(*args,**kwargs)
        antes=self.inventario_deportivo()
        with patch('inscripciones.servicios.crear_bajo_bloqueo',side_effect=cambiar_y_crear):
            with self.assertRaises(APIException):self.ejecutar()
        self.assertEqual(self.inventario_deportivo(),antes)

    def test_fallo_auditoria_revierte_destino_y_resultado(self):
        antes=self.inventario_deportivo()
        with patch('inscripciones.servicios_movimientos.registrar_evento',side_effect=RuntimeError('Auditoría aislada')):
            with self.assertRaises(RuntimeError):self.ejecutar()
        self.assertEqual(self.inventario_deportivo(),antes)
        self.assertFalse(ResultadoAdministrativo.objects.exists())

    def test_revisar_metadatos_despues_de_ejecutar_conserva_resultado(self):
        r=self.ejecutar()
        evidencia=r.evidencia_ejecucion.copy()
        Grupo.objects.filter(pk=self.l.pk).update(cupo_maximo=3)
        self.assertTrue(consultar_ejecucion(self.coord,self.p.pk)['discrepancias'])
        self.r=self.revisar(filas=self.filas('reubicar'))
        self.assertFalse(consultar_ejecucion(self.coord,self.p.pk)['discrepancias'])
        r.refresh_from_db();self.assertEqual(r.evidencia_ejecucion,evidencia)


class MigracionMovimientosB3B2(DatosMovimiento,TransactionTestCase):
    def test_aplicar_revertir_reaplicar_sobre_evidencia_pendiente(self):
        from django.db.migrations.executor import MigrationExecutor
        self.iniciar_movimiento()
        self.p.refresh_from_db()
        registrar_resultado(self.admin,self.r.pk,self.p.version,self.aid,uuid4(),'Evidencia previa')
        with connection.cursor() as c:
            c.execute('SELECT current_database()');self.assertTrue(c.fetchone()[0].startswith('test_zdb_fase3_'))
        antes=self.inventario_deportivo()
        try:
            MigrationExecutor(connection).migrate([('inscripciones','0003_revisionadministrativa_resultadoadministrativo_and_more')])
            with connection.cursor() as c:
                c.execute('SELECT id,estado,motivo FROM public.inscripciones_resultadoadministrativo ORDER BY id')
                filas=c.fetchall()
        finally:
            MigrationExecutor(connection).migrate([('inscripciones','0005_facultades_multirrol')])
        self.assertEqual(self.inventario_deportivo(),antes)
        self.assertEqual(list(ResultadoAdministrativo.objects.order_by('id').values_list('id','estado','motivo')),filas)

    def test_reversion_con_ejecuciones_rechazada_sin_perder_datos(self):
        from django.db.migrations.executor import MigrationExecutor
        self.iniciar_movimiento();r=self.ejecutar()
        antes=self.inventario_deportivo()
        with self.assertRaises(DatabaseError):
            MigrationExecutor(connection).migrate([('inscripciones','0003_revisionadministrativa_resultadoadministrativo_and_more')])
        self.assertEqual(self.inventario_deportivo(),antes)
        self.assertEqual(ResultadoAdministrativo.objects.get(pk=r.pk).evidencia_ejecucion,r.evidencia_ejecucion)


class ConcurrenciaMovimientosB3B2(DatosMovimiento,TransactionTestCase):
    def test_movimiento_y_alta_compiten_ultimo_cupo(self):
        self.iniciar_movimiento()
        Grupo.objects.filter(pk=self.l.pk).update(cupo_maximo=1)
        self.r=self.revisar(filas=self.filas('reubicar'));self.p.refresh_from_db()
        persona=self.persona_nueva('Competidora');barrera=Barrier(2)
        def competir(tipo):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                if tipo=='movimiento':
                    ejecutar_reubicacion(self.admin,self.r.pk,self.p.version,self.aid,uuid4(),'Último cupo')
                else:
                    from .servicios import inscribir
                    inscribir(persona,self.l,self.hoy,self.coord,'Alta concurrente')
                return 'ok'
            except APIException:return 'conflicto'
            finally:connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(competir,['movimiento','alta'])),['ok','conflicto'])
        self.assertEqual(Inscripcion.objects.filter(grupo=self.l).count(),1)
        self.origen.refresh_from_db()
        self.assertEqual(self.origen.estado,'finalizada' if ResultadoAdministrativo.objects.filter(estado='ejecutada').exists() else 'activa')

    def test_doble_ejecucion_un_solo_movimiento(self):
        self.iniciar_movimiento(); version=self.p.version; barrera=Barrier(2)
        def competir(_):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                ejecutar_reubicacion(self.admin,self.r.pk,version,self.aid,uuid4(),'Concurrente')
                return 'ok'
            except APIException: return 'conflicto'
            finally: connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(competir,range(2))),['ok','conflicto'])
        self.assertEqual(Inscripcion.objects.count(),2)
