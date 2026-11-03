"""Desglose de lectura de cupos; no cambia permisos ni estados por consultar."""
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from deportistas.tests import DatosFase3
from deportistas.models import Deportista
from organizacion.models import Asignacion
from .models import ReservaCupo, EventoInscripcion, Inscripcion


class ConsultaCupos(DatosFase3,TestCase):
    def setUp(self):
        self.preparar()
        self.a.cupo_maximo=5;self.a.save()

    def consultar(self, **parametros):
        return self.c.get('/api/inscripciones/cupos/',{'grupo':self.a.pk,**parametros})

    def reservar(self):
        i=self.inscribir()
        r=self.post(f'inscripciones/{i.pk}/suspender/',{'version':1,'motivo':'Reserva ficticia','fecha_vencimiento':str(self.hoy)})
        self.assertEqual(r.status_code,200)
        return i

    def test_desglosa_activas_reservas_y_plazas_con_futuras(self):
        self.reservar()
        self.inscribir(persona=self.persona_nueva('Activa'))
        self.inscribir(persona=self.persona_nueva('Programada'),inicio=self.hoy+timedelta(days=1))
        self.inscribir(persona=self.persona_nueva('Programada dos'),inicio=self.hoy+timedelta(days=1))
        r=self.consultar();self.assertEqual(r.status_code,200)
        for campo,valor in {'grupo':self.a.pk,'cupo_maximo':5,'inscripciones_activas':1,'reservas_vigentes':1,
                            'ocupacion_actual':2,'disponibles_actuales':3,'ocupacion_maxima':3,'disponibles':2}.items():
            self.assertEqual(r.data[campo],valor,campo)
        self.assertEqual(str(r.data['fecha_corte']),str(self.hoy))

    def test_reserva_vencida_no_ocupa_sin_escribir(self):
        self.reservar()
        antes=(list(Inscripcion.objects.values()),list(ReservaCupo.objects.values()),EventoInscripcion.objects.count())
        with patch('django.utils.timezone.localdate',return_value=self.hoy+timedelta(days=1)):
            r=self.consultar()
        self.assertEqual(r.status_code,200)
        self.assertEqual((r.data['ocupacion_actual'],r.data['reservas_vigentes'],r.data['ocupacion_maxima']),(0,0,0))
        self.assertEqual((list(Inscripcion.objects.values()),list(ReservaCupo.objects.values()),EventoInscripcion.objects.count()),antes)

    def test_reserva_liberada_no_cuenta_y_fechas_intervalo_se_conservan(self):
        i=self.reservar()
        self.assertEqual(self.post(f'inscripciones/{i.pk}/reanudar/',{'version':2,'motivo':'Reincorporación ficticia'}).status_code,200)
        r=self.consultar(desde=str(self.hoy+timedelta(days=1)),hasta=str(self.hoy+timedelta(days=2)))
        self.assertEqual(r.status_code,200)
        self.assertEqual((r.data['inscripciones_activas'],r.data['reservas_vigentes']),(1,0))
        self.assertEqual(str(r.data['desde']),str(self.hoy+timedelta(days=1)))

    def test_roles_conservan_alcance_de_grupos(self):
        for actor in (self.admin,self.coord,self.prof):
            self.c.force_authenticate(actor)
            self.assertEqual(self.consultar().status_code,200)
        self.c.force_authenticate(self.otro)
        self.assertEqual(self.consultar().status_code,404)
        self.c.force_authenticate(None)
        self.assertEqual(self.consultar().status_code,403)

    def test_intervalo_invalido_no_inventa_disponibilidad(self):
        self.assertEqual(self.consultar(desde=str(self.periodo.fecha_fin+timedelta(days=1))).status_code,400)
        self.assertEqual(self.consultar(grupo='texto').status_code,400)

    def test_catalogos_y_filtros_siguen_usando_ids_y_permisos(self):
        self.inscribir()
        ajeno=self.persona_nueva('Ajena')
        self.c.force_authenticate(self.prof)
        parametros={'grupo':self.a.pk,'periodo':self.periodo.pk,'disciplina':self.d.pk,'nivel':self.n.pk}
        r=self.c.get('/api/deportistas/',parametros)
        self.assertEqual(r.status_code,200)
        self.assertEqual([x['id'] for x in r.data['results']],[self.persona.pk])
        self.assertNotIn('fecha_nacimiento',r.data['results'][0])
        self.assertEqual(self.c.get('/api/deportistas/',{**parametros,'grupo':self.b.pk}).data['count'],0)
        self.assertEqual(self.c.get('/api/organizacion/grupos/').status_code,200)
        Asignacion.objects.filter(usuario=self.prof,grupo=self.a).delete()
        self.assertEqual(self.consultar().status_code,404)
