"""Contratos REST de los formularios privados; fixtures solo en base de pruebas."""
from django.test import TestCase
from django.utils import timezone
from auditoria.models import CambioAdministrativo
from .tests import DatosFase3
from .models import Acudiente, VinculoAcudiente, Autorizacion, TipoAutorizacion


class ContratosFormulariosPrivados(DatosFase3, TestCase):
    def setUp(self):
        self.preparar()
        self.c.force_authenticate(self.admin)
        self.contacto = {
            'nombres': 'Acudiente', 'apellidos': 'Prueba Fase Tres',
            'telefono': '3000000000', 'correo': 'acudiente.prueba@example.com',
        }

    def test_reproduce_payload_anterior_con_campos_ajenos(self):
        r = self.post('acudientes/', {**self.contacto, 'fecha_inicio': str(self.hoy), 'numero_version': 1})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.data['errores']), {'fecha_inicio', 'numero_version'})
        for mensaje in r.data['errores'].values():
            self.assertEqual(str(mensaje), 'Campo no permitido.')
        self.assertEqual(Acudiente.objects.count(), 0)

    def test_admin_crea_contacto_con_payload_corregido_y_auditoria(self):
        r = self.post('acudientes/', self.contacto)
        self.assertEqual(r.status_code, 201)
        contacto = Acudiente.objects.get(pk=r.data['id'])
        for campo, valor in self.contacto.items():
            self.assertEqual(getattr(contacto, campo), valor)
        self.assertEqual(contacto.creado_por_id, self.admin.pk)
        self.assertTrue(CambioAdministrativo.objects.exists())
        self.assertEqual(VinculoAcudiente.objects.count(), 0)

    def test_vinculo_y_autorizacion_contratos_separados_y_acciones(self):
        contacto = self.post('acudientes/', self.contacto).data['id']
        datos = {'deportista': self.persona.pk, 'acudiente': contacto, 'fecha_inicio': str(self.hoy)}
        r = self.post('vinculos-acudientes/', {**datos, 'numero_version': 1})
        self.assertEqual(r.status_code, 400)
        self.assertIn('numero_version', r.data['errores'])
        r = self.post('vinculos-acudientes/', datos)
        self.assertEqual(r.status_code, 201)
        vinculo = r.data['id']
        self.assertEqual(self.post(f'vinculos-acudientes/{vinculo}/verificar/', {'version': 1}).status_code, 400)
        tipo = TipoAutorizacion.objects.create(codigo='contrato_ficticio', finalidad='Prueba aislada',
            referencia_texto_aprobado='Referencia ficticia', creado_por=self.admin, actualizado_por=self.admin)
        self.assertEqual(self.post(f'vinculos-acudientes/{vinculo}/verificar/', self.comprobacion(tipo)).status_code, 200)
        autorizacion = {'deportista': self.persona.pk, 'tipo': tipo.pk, 'otorgante': 'acudiente',
            'vinculo_acudiente': vinculo, 'decision': 'otorgada', 'declarada_en': timezone.now().isoformat(),
            'vigente_desde': str(self.hoy), 'referencia_evidencia': 'Referencia privada ficticia'}
        r = self.post('autorizaciones/', {**autorizacion, 'fecha_inicio': str(self.hoy), 'numero_version': 1})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.data['errores']), {'fecha_inicio', 'numero_version'})
        r = self.post('autorizaciones/', autorizacion)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.post(f"autorizaciones/{r.data['id']}/revocar/", {'version': 1, 'motivo': 'Solicitud ficticia'}).status_code, 200)
        self.assertEqual(Autorizacion.objects.count(), 1)

    def test_profesor_no_puede_crear_contactos_vinculos_ni_autorizaciones(self):
        self.c.force_authenticate(self.prof)
        for ruta in ('acudientes/', 'vinculos-acudientes/', 'autorizaciones/'):
            for datos in (self.contacto, {**self.contacto, 'fecha_inicio': str(self.hoy), 'numero_version': 1}):
                self.assertEqual(self.post(ruta, datos).status_code, 403)
        self.assertEqual(Acudiente.objects.count(), 0)
        self.assertEqual(VinculoAcudiente.objects.count(), 0)
        self.assertEqual(Autorizacion.objects.count(), 0)
