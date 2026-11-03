"""Destinos JSON desaparecidos: fixtures exclusivamente en PostgreSQL aislado."""
from copy import deepcopy
from uuid import uuid4
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from deportistas.servicios import Conflicto
from organizacion.models import Grupo, Disciplina, Nivel
from .modelos_ascensos import AfectacionInscripcion
from .modelos_ejecucion import RevisionAdministrativa, ResultadoAdministrativo
from .servicios_ejecucion import consultar_ejecucion, registrar_resultado, huella_contexto
from .test_ejecucion_b3_b1 import DatosEjecucion


class DestinosAdministrativos(DatosEjecucion, TestCase):
    def setUp(self):
        self.aprobada()
        segunda = self.inscribir(grupo=self.b)
        AfectacionInscripcion.objects.create(progresion=self.p, inscripcion=segunda,
            version_observada=segunda.version, situacion_observada='activa')
        self.destino = self.grupo('destino-auditoria', '14:00', '15:00', self.n2)
        self.id_destino = self.destino.pk
        self.filas_destino = self.filas('reubicar')
        for f in self.filas_destino:
            f['destino'] = self.id_destino
        self.r = self.revisar(filas=self.filas_destino)
        self.p.refresh_from_db()

    def eliminar_destino(self):
        self.destino.horarios.all().delete()
        self.destino.delete()

    def resumen(self):
        return consultar_ejecucion(self.coord, self.p.pk)

    def registrar(self, clave=None):
        self.p.refresh_from_db()
        return registrar_resultado(self.admin, self.r.pk, self.p.version,
            self.p.afectaciones.first().pk, clave or uuid4(), 'Resultado de prueba')

    def test_destino_compatible_sin_discrepancias(self):
        r = self.resumen()
        self.assertFalse(r['discrepancias'])
        self.assertFalse(r['advertencias_destinos'])
        self.assertTrue(r['plan_completo'])

    def test_destino_eliminado_discrepancia_por_cada_afectacion(self):
        self.eliminar_destino()
        r = self.resumen()
        self.assertEqual(set(r['discrepancias']), set(self.p.afectaciones.values_list('id', flat=True)))
        self.assertEqual(len(r['advertencias_destinos']), 2)
        for aviso in r['advertencias_destinos']:
            self.assertEqual((aviso['codigo'], aviso['destino']), ('destino_inexistente', self.id_destino))
            self.assertTrue(aviso['bloquea_resultado'])
        self.assertFalse(r['plan_completo'])
        self.assertFalse(r['puede_cerrar'])

    def test_consultas_repetidas_preservan_evidencia_y_aprobacion(self):
        evidencia = deepcopy(self.r.disposiciones)
        decision = (self.p.decidida_por_id, self.p.decidida_en, self.p.resolucion)
        self.eliminar_destino()
        antes = self.inventario_deportivo()
        eventos = list(self.p.eventos.values())
        version = self.p.version
        self.assertEqual(self.resumen(), self.resumen())
        self.assertEqual(self.inventario_deportivo(), antes)
        self.r.refresh_from_db(); self.p.refresh_from_db()
        self.assertEqual(self.r.disposiciones, evidencia)
        self.assertEqual(self.r.disposiciones[0]['destino'], self.id_destino)
        self.assertEqual((self.p.decidida_por_id, self.p.decidida_en, self.p.resolucion), decision)
        self.assertEqual(self.p.version, version)
        self.assertEqual(list(self.p.eventos.values()), eventos)

    def test_huella_y_registro_destino_eliminado_sin_excepcion_inesperada(self):
        self.eliminar_destino()
        with self.assertRaises(Conflicto):
            huella_contexto(self.origen, self.id_destino)
        with self.assertRaises(Conflicto):
            self.registrar()
        self.assertFalse(ResultadoAdministrativo.objects.exists())

    def test_crear_revision_con_destino_ya_inexistente(self):
        self.eliminar_destino()
        with self.assertRaises(Conflicto):
            self.revisar(filas=self.filas_destino)
        self.assertEqual(RevisionAdministrativa.objects.count(), 1)

    def test_nueva_revision_sustituye_destino_sin_reescribir_historia(self):
        original = deepcopy(self.r.disposiciones)
        self.eliminar_destino()
        nuevo = self.grupo('destino-nuevo', '15:00', '16:00', self.n2)
        filas = deepcopy(self.filas_destino)
        for f in filas:
            f['destino'] = nuevo.pk
        r = self.revisar(filas=filas)
        self.assertEqual(r.anterior_id, self.r.pk)
        self.assertFalse(self.resumen()['discrepancias'])
        self.assertEqual(RevisionAdministrativa.objects.get(pk=self.r.pk).disposiciones, original)
        self.r = r
        self.registrar()

    def test_reintento_idempotente_despues_de_eliminar_destino(self):
        clave = uuid4()
        resultado = self.registrar(clave)
        self.assertEqual(self.registrar(clave).pk, resultado.pk)
        self.eliminar_destino()
        with self.assertRaises(Conflicto):
            self.registrar(clave)
        self.assertEqual(ResultadoAdministrativo.objects.count(), 1)

    def test_reintento_anterior_no_se_convierte_en_nueva_revision(self):
        clave = uuid4(); self.registrar(clave)
        self.eliminar_destino()
        r = self.revisar(filas=self.filas('reubicar'))  # El destino existente l sustituye al eliminado.
        with self.assertRaises(Conflicto):
            self.registrar(clave)
        self.r = r
        self.assertFalse(self.resumen()['discrepancias'])
        self.registrar(uuid4())
        self.assertEqual(ResultadoAdministrativo.objects.count(), 2)

    def test_destino_inactivo_distinto_de_inexistente(self):
        Grupo.objects.filter(pk=self.id_destino).update(activo=False)
        self.assertTrue(Grupo.objects.filter(pk=self.id_destino).exists())
        self.assertEqual(self.resumen()['advertencias_destinos'][0]['codigo'], 'destino_inactivo')
        with self.assertRaises(Conflicto):
            self.registrar()
        with self.assertRaises(ValidationError):
            self.revisar(filas=self.filas_destino)

    def test_destino_sin_horarios(self):
        self.destino.horarios.all().delete()
        self.assertEqual(self.resumen()['advertencias_destinos'][0]['codigo'], 'destino_sin_horarios')
        with self.assertRaises(Conflicto):
            self.registrar()

    def test_destino_otra_disciplina(self):
        d = Disciplina.objects.create(codigo='otra-destino', nombre='Otra')
        n = Nivel.objects.create(disciplina=d, codigo='otro', nombre='Otro')
        Grupo.objects.filter(pk=self.id_destino).update(disciplina=d, nivel=n)
        self.assertEqual(self.resumen()['advertencias_destinos'][0]['codigo'], 'destino_incompatible')
        with self.assertRaises(Conflicto):
            self.registrar()

    def test_destino_nivel_modificado(self):
        Grupo.objects.filter(pk=self.id_destino).update(nivel=self.n)
        self.assertEqual(self.resumen()['advertencias_destinos'][0]['codigo'], 'destino_incompatible')
        with self.assertRaises(Conflicto):
            self.registrar()

    def test_sin_cupo_no_es_destino_inexistente_ni_reserva_plaza(self):
        self.inscribir(persona=self.persona_nueva('Otra uno'), grupo=self.destino)
        self.inscribir(persona=self.persona_nueva('Otra dos'), grupo=self.destino)
        antes = self.inventario_deportivo()
        r = self.resumen()
        self.assertEqual(r['advertencias_destinos'][0]['codigo'], 'destino_sin_cupo')
        self.assertFalse(r['advertencias_destinos'][0]['bloquea_resultado'])
        self.assertFalse(r['discrepancias'])
        self.registrar()  # Evidencia pendiente, nunca traslado ni adjudicación de plaza.
        self.assertEqual(self.inventario_deportivo(), antes)
        self.assertFalse(r['ejecucion_habilitada'])
