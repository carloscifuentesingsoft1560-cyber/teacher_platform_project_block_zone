from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import close_old_connections,connections
from django.test import TransactionTestCase,skipUnlessDBFeature
from rest_framework.exceptions import APIException
from deportistas.tests import DatosFase3
from deportistas.servicios import Conflicto
from cuentas.models import Usuario
from cuentas.serializers_usuarios import AdministracionUsuarioSerializer
from cuentas.servicios_usuarios import guardar_usuario
from .servicios import inscribir,resolver
from .serializers import PropuestaSerializer
from .servicios import proponer
from .models import Inscripcion,Propuesta

class CarrerasOperativas(DatosFase3,TransactionTestCase):
    def carrera(self,acciones):
        barrera=Barrier(len(acciones))
        def ejecutar(accion):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                accion()
                return "confirmada"
            except APIException:
                return "rechazada"
            finally:
                connections["default"].close()
        with ThreadPoolExecutor(max_workers=len(acciones)) as pool:
            return list(pool.map(ejecutar,acciones))

    def propuesta(self):
        origen=self.inscribir()
        s=PropuestaSerializer(data={"tipo":"traslado","deportista":self.persona.pk,"inscripcion_origen":origen.pk,"grupo_destino":self.b.pk,"fecha_efectiva":str(self.hoy),"justificacion":"Ficticia concurrente"})
        s.is_valid(raise_exception=True)
        return proponer(s,self.prof)

    @skipUnlessDBFeature("has_select_for_update")
    def test_dos_aprobaciones_solo_un_traslado(self):
        self.preparar()
        p=self.propuesta()
        acciones=[lambda:resolver(p,self.coord,{"version":1,"resolucion":"Revisión ficticia"},True)]*2
        self.assertCountEqual(self.carrera(acciones),["confirmada","rechazada"])
        self.assertEqual(Inscripcion.objects.count(),2)
        self.assertEqual(Propuesta.objects.get().estado,"aplicada")

    @skipUnlessDBFeature("has_select_for_update")
    def test_dos_grupos_incompatibles_misma_persona(self):
        self.preparar()
        acciones=[lambda:inscribir(self.persona,self.a,self.hoy,self.coord,"Alta ficticia"),
                  lambda:inscribir(self.persona,self.x,self.hoy,self.coord,"Alta ficticia")]
        self.assertCountEqual(self.carrera(acciones),["confirmada","rechazada"])
        self.assertEqual(Inscripcion.objects.count(),1)

    @skipUnlessDBFeature("has_select_for_update")
    def test_desactivar_coordinador_durante_aprobacion(self):
        self.preparar()
        p=self.propuesta()
        def desactivar():
            s=AdministracionUsuarioSerializer(self.coord,data={"is_active":False},partial=True)
            s.is_valid(raise_exception=True)
            guardar_usuario(s,self.admin)
        resultados=self.carrera([lambda:resolver(p,self.coord,{"version":1,"resolucion":"Revisión ficticia"},True),desactivar])
        self.coord.refresh_from_db()
        self.assertFalse(self.coord.is_active)
        p.refresh_from_db()
        if p.estado=="aplicada":
            self.assertEqual(resultados.count("confirmada"),2)
            self.assertEqual(Inscripcion.objects.count(),2)
        else:
            self.assertEqual(p.estado,"pendiente")
            self.assertCountEqual(resultados,["confirmada","rechazada"])
            self.assertEqual(Inscripcion.objects.count(),1)
