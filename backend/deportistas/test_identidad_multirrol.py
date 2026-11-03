from uuid import uuid4
from django.test import TestCase
from .tests import DatosFase3
from .models import Acudiente, Deportista
from cuentas.models import Usuario, Persona
from cuentas.servicios_roles import otorgar
from cuentas.servicios_identidad import acreditar, revocar_enlace


class IdentidadMultirrol(DatosFase3,TestCase):
    def setUp(self): self.preparar()

    def test_persona_compartida_conserva_tres_perfiles_y_matricula(self):
        inscripcion=self.inscribir()
        contacto=Acudiente.objects.create(nombres='Ficticio',apellidos='Tutor',telefono='000',creado_por=self.admin,actualizado_por=self.admin)
        a=acreditar(self.admin,None,'usuario',self.prof.pk,uuid4())
        p=a.persona;p.refresh_from_db()
        b=acreditar(self.admin,p.pk,'deportista',self.persona.pk,uuid4(),p.version)
        p.refresh_from_db()
        c=acreditar(self.admin,p.pk,'acudiente',contacto.pk,uuid4(),p.version)
        self.assertEqual(Persona.objects.count(),1)
        self.assertEqual({a.persona_id,b.persona_id,c.persona_id},{p.pk})
        revocar_enlace(self.admin,c.pk,c.version)
        inscripcion.refresh_from_db()
        self.assertEqual(inscripcion.deportista_id,self.persona.pk)
        self.assertEqual(Deportista.objects.count(),1)
        self.assertTrue(Acudiente.objects.filter(pk=contacto.pk).exists())

    def test_profesor_routesetter_no_ve_ni_modifica_persona_ajena(self):
        self.inscribir()
        ajena=self.persona_nueva('Ajena')
        otorgar(self.admin,self.prof.pk,'routesetter','Función adicional ficticia')
        self.c.force_authenticate(self.prof)
        self.assertEqual(self.c.get('/api/deportistas/').data['count'],1)
        ruta=f'/api/deportistas/{ajena.identificador_publico}/'
        self.assertEqual(self.c.get(ruta).status_code,404)
        self.assertEqual(self.c.patch(ruta,{'nombres':'No autorizado','version':1},format='json').status_code,403)
        ajena.refresh_from_db();self.assertEqual(ajena.nombres,'Ajena')

    def test_revocacion_docente_quita_grupos_sin_revocar_routesetter(self):
        from cuentas.models import PertenenciaRol
        from cuentas.servicios_roles import revocar
        self.inscribir();otorgar(self.admin,self.prof.pk,'routesetter','Función adicional')
        r=PertenenciaRol.objects.get(usuario=self.prof,rol='profesor',vigente=True)
        revocar(self.admin,r.pk,r.version,'Fin de docencia')
        self.c.force_authenticate(self.prof)
        self.assertEqual(self.c.get('/api/organizacion/grupos/').status_code,403)
        self.assertEqual(self.c.get('/api/deportistas/').data['count'],0)
        self.assertTrue(self.prof.tiene_rol('routesetter'))
