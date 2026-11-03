from uuid import uuid4
from django.test import TestCase
from django.db import transaction, IntegrityError
from rest_framework.exceptions import PermissionDenied
from .test_ejecucion_b3_b1 import DatosEjecucion
from .modelos_ejecucion import RevisionAdministrativa
from .servicios_ejecucion import revisar_plan
from cuentas.servicios_roles import otorgar, revocar


class FacultadesAscensosEtapa2(DatosEjecucion,TestCase):
    def setUp(self):
        self.aprobada()

    def test_coordinador_no_formaliza_servicio_ni_api(self):
        with self.assertRaises(PermissionDenied):
            revisar_plan(self.coord,self.p.pk,self.p.version,self.filas(),'Revisión no autorizada')
        self.c.force_authenticate(self.coord)
        self.assertEqual(self.post(f'ascensos/{self.p.pk}/revisiones/',{}).status_code,403)
        self.assertEqual(self.post(f'ascensos/{self.p.pk}/ejecutar/',{}).status_code,403)
        self.assertEqual(RevisionAdministrativa.objects.count(),0)

    def test_coordinador_no_formaliza_sql_directo(self):
        valido=self.revisar()
        with self.assertRaises(IntegrityError),transaction.atomic():
            RevisionAdministrativa.objects.create(progresion=self.p,numero=2,anterior=valido,
                disposiciones=valido.disposiciones,actor=self.coord,motivo='Intento sin autoridad',
                version_progresion=self.p.version+1)
        self.assertEqual(RevisionAdministrativa.objects.count(),1)

    def test_doble_rol_formaliza_y_revocacion_actua_sin_recargar_actor(self):
        r=otorgar(self.admin,self.coord.pk,'administrador','Funciones institucionales combinadas')
        revisar_plan(self.coord,self.p.pk,self.p.version,self.filas(),'Administración explícita')
        self.p.refresh_from_db()
        revocar(self.admin,r.pk,r.version,'Fin de función administrativa')
        with self.assertRaises(PermissionDenied):
            revisar_plan(self.coord,self.p.pk,self.p.version,self.filas(),'Actor en caché')
        self.assertTrue(self.coord.tiene_rol('coordinador'))
