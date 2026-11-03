from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import close_old_connections,connections
from django.test import TransactionTestCase
from rest_framework.exceptions import APIException
from cuentas.models import Usuario,PertenenciaRol
from cuentas.servicios_roles import otorgar


class ConcurrenciaRoles(TransactionTestCase):
    def test_dos_nombramientos_solo_un_coordinador(self):
        admin=Usuario.objects.create_user(username='ficticio_admin',rol='administrador')
        personas=[Usuario.objects.create_user(username='ficticio_'+str(i),rol='profesor') for i in range(2)]
        barrera=Barrier(2)
        def nombrar(u):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                otorgar(admin,u.pk,'coordinador','Nombramiento concurrente ficticio')
                return 'ok'
            except APIException:return 'rechazado'
            finally:connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(nombrar,personas)),['ok','rechazado'])
        self.assertEqual(PertenenciaRol.objects.filter(rol='coordinador',vigente=True).count(),1)
