"""Regresiones de auditoría; todas las escrituras son fixtures PostgreSQL aisladas."""
from copy import deepcopy
from datetime import datetime, timedelta
from uuid import uuid4
import json
from unittest.mock import patch
from django.test import TestCase
from django.db import connection, transaction, DatabaseError
from django.db.models.query import QuerySet
from django.core.exceptions import ValidationError as ErrorModelo
from django.utils import timezone
from deportistas.servicios import Conflicto
from organizacion.models import Grupo, Disciplina, Nivel
from .models import Inscripcion
from .modelos_ascensos import AfectacionInscripcion
from .modelos_ejecucion import RevisionAdministrativa, ResultadoAdministrativo, validar_disposiciones
from .servicios_ejecucion import consultar_ejecucion, registrar_resultado
from .servicios_ascensos import autorizar_excepcion
from .test_ejecucion_b3_b1 import DatosEjecucion


class CorreccionesB3B1(DatosEjecucion, TestCase):
    def setUp(self):
        self.aprobada()
        self.secundaria = self.inscribir(grupo=self.b)
        self.af = AfectacionInscripcion.objects.create(progresion=self.p, inscripcion=self.secundaria,
            version_observada=self.secundaria.version, situacion_observada='activa')
        self.r = self.revisar()
        self.p.refresh_from_db()

    def sql_resultado(self):
        with connection.cursor() as c:
            c.execute('INSERT INTO public.inscripciones_resultadoadministrativo '
                '(revision_id,afectacion_id,origen_id,estado,clave,motivo,actor_id,version_progresion,registrada_en) '
                'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,now())', [self.r.pk,self.af.pk,self.secundaria.pk,
                    'pendiente',uuid4(),'Prueba aislada',self.admin.pk,self.p.version+1])

    def test_deportista_secundario_cambiado_sin_version(self):
        ajena = self.persona_nueva('Ajena')
        Inscripcion.objects.filter(pk=self.secundaria.pk).update(deportista=ajena)
        self.assertIn(self.af.pk, consultar_ejecucion(self.coord,self.p.pk)['discrepancias'])
        with self.assertRaises(Conflicto):
            registrar_resultado(self.admin,self.r.pk,self.p.version,self.af.pk,uuid4(),'No cruzar')
        with self.assertRaises(Conflicto):
            self.revisar()

    def test_reintento_idempotente_no_oculta_identidad_cruzada(self):
        clave = uuid4()
        registrar_resultado(self.admin,self.r.pk,self.p.version,self.af.pk,clave,'Resultado aislado')
        Inscripcion.objects.filter(pk=self.secundaria.pk).update(deportista=self.persona_nueva('Ajena'))
        with self.assertRaises(Conflicto):
            registrar_resultado(self.admin,self.r.pk,self.p.version,self.af.pk,clave,'Resultado aislado')

    def test_resultado_cruzado_orm_y_sql(self):
        Inscripcion.objects.filter(pk=self.secundaria.pk).update(deportista=self.persona_nueva('Ajena'))
        with self.assertRaises(ErrorModelo):
            ResultadoAdministrativo.objects.create(revision=self.r,afectacion=self.af,origen=self.secundaria,
                estado='pendiente',clave=uuid4(),motivo='No cruzar',actor=self.admin,version_progresion=self.p.version+1)
        with self.assertRaises(DatabaseError), transaction.atomic():
            self.sql_resultado()

    def test_disciplina_secundaria_cambiada_sin_version(self):
        d = Disciplina.objects.create(codigo='otra-auditoria',nombre='Otra')
        n = Nivel.objects.create(disciplina=d,codigo='otro',nombre='Otro')
        Grupo.objects.filter(pk=self.b.pk).update(disciplina=d,nivel=n)
        self.assertIn(self.af.pk, consultar_ejecucion(self.admin,self.p.pk)['discrepancias'])
        with self.assertRaises(DatabaseError), transaction.atomic():
            self.sql_resultado()
        with self.assertRaises(Conflicto):
            registrar_resultado(self.admin,self.r.pk,self.p.version,self.af.pk,uuid4(),'No cruzar')

    def test_grupo_secundario_cambiado_sin_version(self):
        g = self.grupo('cambio', '14:00', '15:00')
        Inscripcion.objects.filter(pk=self.secundaria.pk).update(grupo=g)
        self.assertIn(self.af.pk, consultar_ejecucion(self.coord,self.p.pk)['discrepancias'])
        with self.assertRaises(Conflicto):
            registrar_resultado(self.admin,self.r.pk,self.p.version,self.af.pk,uuid4(),'Revisar grupo')

    def test_sql_revalida_otras_afectaciones_no_solo_resultado(self):
        Inscripcion.objects.filter(pk=self.secundaria.pk).update(deportista=self.persona_nueva('Ajena'))
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as c:
            c.execute('INSERT INTO public.inscripciones_resultadoadministrativo '
                '(revision_id,afectacion_id,origen_id,estado,clave,motivo,actor_id,version_progresion,registrada_en) '
                'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,now())', [self.r.pk,self.p.afectaciones.get(inscripcion=self.origen).pk,
                    self.origen.pk,'pendiente',uuid4(),'Revalidar conjunto',self.admin.pk,self.p.version+1])

    def casos_invalidos(self):
        base = self.r.disposiciones
        yield None
        yield {}
        yield [None]
        yield []
        for campo, valor in [('huella_contexto',None),('huella_contexto',123),('huella_contexto','invalida'),
                ('origen',None),('origen','1'),('origen',True),('disposicion',[]),('motivo',None),
                ('destino',False),('situacion',{}),('deportista',0)]:
            filas = deepcopy(base); filas[0][campo] = valor; yield filas
        filas = deepcopy(base); del filas[0]['huella_contexto']; yield filas
        filas = deepcopy(base); filas[0]['extra'] = 'no permitido'; yield filas

    def test_json_ausente_nulo_y_tipos_invalidos_modelo(self):
        for filas in self.casos_invalidos():
            with self.subTest(filas=filas), self.assertRaises(ErrorModelo):
                validar_disposiciones(filas)

    def test_json_incompleto_rechazado_sql_antes_de_auditoria(self):
        for filas in self.casos_invalidos():
            with self.subTest(filas=filas), self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as c:
                c.execute('INSERT INTO public.inscripciones_revisionadministrativa '
                    '(progresion_id,numero,anterior_id,actor_id,motivo,version_progresion,disposiciones,registrada_en) '
                    'VALUES (%s,2,%s,%s,%s,%s,%s::jsonb,now())', [self.p.pk,self.r.pk,self.admin.pk,
                        'Evidencia incompleta',self.p.version+1,json.dumps(filas)])

    def test_consulta_corrupta_da_conflicto_no_keyerror(self):
        original = QuerySet.first
        for filas in self.casos_invalidos():
            r = deepcopy(self.r); r.disposiciones = filas
            with self.subTest(filas=filas), patch.object(QuerySet,'first',new=lambda qs: r if qs.model is RevisionAdministrativa else original(qs)):
                with self.assertRaises(Conflicto):
                    consultar_ejecucion(self.coord,self.p.pk)

    def test_huella_alterada_detectada(self):
        r = deepcopy(self.r); r.disposiciones[0]['huella_contexto'] = '0'*64
        original = QuerySet.first
        with patch.object(QuerySet,'first',new=lambda qs: r if qs.model is RevisionAdministrativa else original(qs)):
            self.assertTrue(consultar_ejecucion(self.coord,self.p.pk)['discrepancias'])

    def test_identidades_presentes_en_todas_las_evidencias(self):
        for f in self.r.disposiciones:
            self.assertEqual(f['deportista'],self.persona.pk)
            self.assertEqual(f['disciplina'],self.d.pk)
            self.assertIsInstance(f['grupo'],int)
            self.assertEqual(len(f['huella_contexto']),64)

    def test_revision_continuidad_con_excepcion_vigente(self):
        self.p.refresh_from_db()
        autorizar_excepcion(self.coord,self.p.pk,self.p.version,self.af.pk,
            'Autorización coordinadora expresa',self.hoy,self.hoy+timedelta(days=2))
        filas = self.filas()
        next(f for f in filas if f['afectacion']==self.af.pk)['disposicion'] = 'continuidad'
        r = self.revisar(filas=filas)
        with connection.cursor() as c:
            c.execute('SET CONSTRAINTS ALL IMMEDIATE')
        self.assertEqual(next(f['disposicion'] for f in r.disposiciones if f['afectacion']==self.af.pk),'continuidad')
        self.assertFalse(consultar_ejecucion(self.coord,self.p.pk)['puede_cerrar'])

    def test_fecha_bogota_independiente_de_sesion_sql(self):
        instantes = [('2026-10-30T04:59:59+00:00','2026-10-29'),
            ('2026-10-30T05:00:00+00:00','2026-10-30'),('2026-10-31T00:01:00+00:00','2026-10-30')]
        for zona in ('UTC','Pacific/Kiritimati','America/Bogota'):
            with connection.cursor() as c:
                c.execute('SET LOCAL TIME ZONE %s',[zona])
                for instante, esperado in instantes:
                    c.execute("SELECT (%s::timestamptz AT TIME ZONE 'America/Bogota')::date",[instante])
                    self.assertEqual(str(c.fetchone()[0]),esperado)
                    with timezone.override('America/Bogota'):
                        self.assertEqual(str(timezone.localdate(datetime.fromisoformat(instante))),esperado)

    def test_trigger_usa_bogota_con_sesion_en_otro_dia(self):
        futura = self.inscribir(grupo=self.grupo('futura-auditoria','14:00','15:00'),inicio=self.hoy+timedelta(days=1))
        AfectacionInscripcion.objects.create(progresion=self.p,inscripcion=futura,
            version_observada=futura.version,situacion_observada='futura')
        with connection.cursor() as c:
            c.execute('SELECT extract(epoch FROM decidida_en) FROM public.inscripciones_progresioninstitucional WHERE id=%s',[self.p.pk])
            fecha_anterior = c.fetchone()[0]
            c.execute("SET LOCAL TIME ZONE 'Pacific/Kiritimati'")
            c.execute("SELECT CURRENT_DATE, (statement_timestamp() AT TIME ZONE 'America/Bogota')::date")
            sesion, operativa = c.fetchone()
            self.assertEqual(operativa,self.hoy)
        r = self.revisar()
        self.assertEqual(next(f['situacion'] for f in r.disposiciones if f['origen']==futura.pk),'futura')
        with connection.cursor() as c:
            c.execute('SELECT extract(epoch FROM decidida_en) FROM public.inscripciones_progresioninstitucional WHERE id=%s',[self.p.pk])
            self.assertEqual(c.fetchone()[0],fecha_anterior)
