from datetime import timedelta
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.test import TestCase
from rest_framework.test import APIClient
from cuentas.models import Usuario
from auditoria.models import CambioAdministrativo
from organizacion.models import Disciplina, Nivel, Periodo, Grupo, Horario, Asignacion

class PruebasOrganizacion(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hoy = timezone.localdate()
        cls.admin = Usuario.objects.create_user(username="demo_admin_org", rol="administrador")
        cls.profe = Usuario.objects.create_user(username="demo_profe_org", rol="profesor")
        cls.otro = Usuario.objects.create_user(username="demo_otro_org", rol="profesor")
        cls.coord = Usuario.objects.create_user(username="demo_coord_org", rol="coordinador")
        cls.disciplina = Disciplina.objects.get(codigo="escalada")
        cls.nivel = Nivel.objects.get(codigo="nivel-1")
        cls.periodo = Periodo.objects.create(codigo="demo-ciclo", nombre="Ciclo ficticio", fecha_inicio=cls.hoy-timedelta(days=90), fecha_fin=cls.hoy+timedelta(days=90))
        cls.grupo = Grupo.objects.create(codigo="demo-a", nombre="Grupo ficticio A", disciplina=cls.disciplina, nivel=cls.nivel, periodo=cls.periodo, cupo_maximo=12)
        cls.ajeno = Grupo.objects.create(codigo="demo-b", nombre="Grupo ficticio B", disciplina=cls.disciplina, nivel=cls.nivel, periodo=cls.periodo, cupo_maximo=8)
        Horario.objects.create(grupo=cls.grupo, dia=cls.hoy.weekday(), hora_inicio="10:00", hora_fin="11:30")
        Horario.objects.create(grupo=cls.ajeno, dia=cls.hoy.weekday(), hora_inicio="11:00", hora_fin="12:00")

    def setUp(self):
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.admin)

    def asignar(self, usuario=None, grupo=None, tipo="profesor", inicio=None, fin=None):
        return self.cliente.post("/api/organizacion/asignaciones/", {
            "usuario": (usuario or self.profe).pk, "grupo": (grupo or self.grupo).pk,
            "tipo": tipo, "fecha_inicio": str(inicio or self.hoy), "fecha_fin": str(fin) if fin else None,
        }, format="json")

    def datos_grupo(self, **cambios):
        datos = {"codigo": "demo-nuevo", "nombre": "Grupo nuevo ficticio", "disciplina": self.disciplina.pk, "nivel": self.nivel.pk, "periodo": self.periodo.pk, "cupo_maximo": 10,
            "horarios": [{"dia": 1, "hora_inicio": "15:00", "hora_fin": "17:00"}]}
        datos.update(cambios)
        return datos

    def test_catalogos_iniciales_exactos(self):
        self.assertEqual(Nivel.objects.filter(disciplina=self.disciplina).count(), 5)
        self.assertTrue(Nivel.objects.filter(nombre="Alto rendimiento").exists())

    def test_admin_crea_grupo_y_horario_con_auditoria(self):
        r = self.cliente.post("/api/organizacion/grupos/", self.datos_grupo(), format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["horarios"][0]["duracion_minutos"], 120)
        self.assertTrue(CambioAdministrativo.objects.filter(actor=self.admin, accion="crear").exists())

    def test_cupo_cero_rechazado(self):
        self.assertEqual(self.cliente.post("/api/organizacion/grupos/", self.datos_grupo(cupo_maximo=0), format="json").status_code, 400)

    def test_grupo_codigo_duplicado(self):
        self.assertEqual(self.cliente.post("/api/organizacion/grupos/", self.datos_grupo(codigo="demo-a"), format="json").status_code, 400)

    def test_nivel_de_otra_disciplina_rechazado(self):
        d = Disciplina.objects.create(codigo="demo-otra", nombre="Otra ficticia")
        n = Nivel.objects.create(disciplina=d, codigo="demo", nombre="Nivel ficticio")
        self.assertEqual(self.cliente.post("/api/organizacion/grupos/", self.datos_grupo(nivel=n.pk), format="json").status_code, 400)

    def test_horarios_solapados_rechazados(self):
        horarios = [{"dia": 2, "hora_inicio": "10:00", "hora_fin": "12:00"}, {"dia": 2, "hora_inicio": "11:00", "hora_fin": "13:00"}]
        self.assertEqual(self.cliente.post("/api/organizacion/grupos/", self.datos_grupo(horarios=horarios), format="json").status_code, 400)

    def test_horarios_invertidos_y_dia_invalido(self):
        for horario in [{"dia": 7, "hora_inicio": "10:00", "hora_fin": "12:00"}, {"dia": 1, "hora_inicio": "12:00", "hora_fin": "10:00"}]:
            self.assertEqual(self.cliente.post("/api/organizacion/grupos/", self.datos_grupo(horarios=[horario]), format="json").status_code, 400)

    def test_periodo_fechas_invertidas(self):
        r = self.cliente.post("/api/organizacion/periodos/", {"codigo": "invalido", "nombre": "Demo", "fecha_inicio": str(self.hoy), "fecha_fin": str(self.hoy-timedelta(days=1))}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_asigna_profesor_y_coordinador(self):
        self.assertEqual(self.asignar().status_code, 201)
        self.assertEqual(self.asignar(self.coord, tipo="coordinador").status_code, 201)
        self.assertEqual(Asignacion.objects.count(), 2)

    def test_tipo_incompatible_con_rol(self):
        self.assertEqual(self.asignar(self.coord, tipo="profesor").status_code, 400)

    def test_usuario_inactivo_no_se_asigna(self):
        self.profe.is_active = False
        self.profe.save()
        self.assertEqual(self.asignar().status_code, 400)

    def test_asignacion_duplicada_o_solapada(self):
        self.assertEqual(self.asignar().status_code, 201)
        self.assertEqual(self.asignar(inicio=self.hoy+timedelta(days=1)).status_code, 400)
        self.assertEqual(Asignacion.objects.count(), 1)

    def test_asignaciones_no_solapadas_conservan_historial(self):
        self.assertEqual(self.asignar(inicio=self.hoy-timedelta(days=5), fin=self.hoy-timedelta(days=1)).status_code, 201)
        self.assertEqual(self.asignar().status_code, 201)
        self.assertEqual(Asignacion.objects.count(), 2)

    def test_profesor_no_se_asigna_a_horarios_cruzados(self):
        self.asignar()
        self.assertEqual(self.asignar(grupo=self.ajeno).status_code, 400)

    def test_coordinador_puede_responsabilizarse_de_grupos_simultaneos(self):
        self.assertEqual(self.asignar(self.coord, tipo="coordinador").status_code, 201)
        self.assertEqual(self.asignar(self.coord, self.ajeno, tipo="coordinador").status_code, 201)

    def test_asignacion_fuera_periodo_rechazada(self):
        self.assertEqual(self.asignar(inicio=self.periodo.fecha_inicio-timedelta(days=1)).status_code, 400)
        self.assertEqual(self.asignar(fin=self.periodo.fecha_fin+timedelta(days=1)).status_code, 400)

    def test_profesor_solo_consulta_grupo_propio(self):
        self.asignar()
        self.cliente.force_authenticate(self.profe)
        r = self.cliente.get("/api/organizacion/grupos/")
        self.assertEqual([g["id"] for g in r.data["results"]], [self.grupo.pk])
        self.assertEqual(self.cliente.get(f"/api/organizacion/grupos/{self.ajeno.pk}/").status_code, 404)

    def test_coordinador_consulta_todos_los_grupos_y_profesores(self):
        self.asignar()
        self.asignar(self.otro, self.ajeno)
        self.asignar(self.coord, tipo="coordinador")
        self.cliente.force_authenticate(self.coord)
        r = self.cliente.get("/api/organizacion/profesores/")
        self.assertEqual({p["id"] for p in r.data["results"]}, {self.profe.pk, self.otro.pk})
        self.assertEqual(self.cliente.get(f"/api/organizacion/grupos/{self.ajeno.pk}/").status_code, 200)

    def test_no_admin_no_modifica_catalogos_grupos_asignaciones(self):
        for cuenta in [self.profe, self.coord]:
            self.cliente.force_authenticate(cuenta)
            for ruta in ["disciplinas", "niveles", "periodos", "grupos", "asignaciones"]:
                self.assertEqual(self.cliente.post("/api/organizacion/"+ruta+"/", {}, format="json").status_code, 400 if cuenta.rol == "coordinador" and ruta in ("grupos", "asignaciones") else 403)

    def test_anonimo_no_consulta_organizacion(self):
        self.cliente.force_authenticate(None)
        for ruta in ["grupos", "calendario", "asignaciones", "profesores"]:
            self.assertEqual(self.cliente.get("/api/organizacion/"+ruta+"/").status_code, 403)

    def test_finalizar_preserva_registro_y_restringe_acceso(self):
        r = self.asignar(inicio=self.hoy-timedelta(days=3))
        pk = r.data["id"]
        r = self.cliente.post(f"/api/organizacion/asignaciones/{pk}/finalizar/", {"fecha_fin": str(self.hoy-timedelta(days=1))}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(Asignacion.objects.filter(pk=pk).exists())
        self.cliente.force_authenticate(self.profe)
        self.assertEqual(self.cliente.get("/api/organizacion/grupos/").data["count"], 0)

    def test_grupo_no_admite_delete(self):
        self.assertEqual(self.cliente.delete(f"/api/organizacion/grupos/{self.grupo.pk}/").status_code, 405)
        self.assertTrue(Grupo.objects.filter(pk=self.grupo.pk).exists())

    def test_archivo_grupo_conserva_asignaciones(self):
        self.asignar()
        r = self.cliente.patch(f"/api/organizacion/grupos/{self.grupo.pk}/", {"activo": False}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Asignacion.objects.count(), 1)
        self.assertEqual(self.cliente.get("/api/organizacion/calendario/").data["eventos"][0]["grupo"], self.ajeno.pk)

    def test_no_desactiva_catalogo_con_grupos_activos(self):
        r = self.cliente.patch(f"/api/organizacion/disciplinas/{self.disciplina.pk}/", {"activo": False}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_cambio_horario_con_conflicto_es_atomico(self):
        self.asignar()
        self.cliente.patch(f"/api/organizacion/grupos/{self.ajeno.pk}/", {"horarios": [{"dia": self.hoy.weekday(), "hora_inicio": "12:00", "hora_fin": "13:00"}]}, format="json")
        self.assertEqual(self.asignar(grupo=self.ajeno).status_code, 201)
        r = self.cliente.patch(f"/api/organizacion/grupos/{self.ajeno.pk}/", {"horarios": [{"dia": self.hoy.weekday(), "hora_inicio": "10:00", "hora_fin": "11:00"}]}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(str(self.ajeno.horarios.get(activo=True).hora_inicio), "12:00:00")

    def test_calendario_filtra_por_vigencia_y_no_crea_sesiones(self):
        self.asignar()
        self.cliente.force_authenticate(self.profe)
        r = self.cliente.get("/api/organizacion/calendario/", {"desde": str(self.hoy), "hasta": str(self.hoy)})
        self.assertEqual(r.data["tipo"], "horarios_recurrentes")
        self.assertEqual([e["grupo"] for e in r.data["eventos"]], [self.grupo.pk])
        self.assertEqual(r.data["eventos"][0]["duracion_minutos"], 90)

    def test_calendario_rechaza_rango_excesivo(self):
        r = self.cliente.get("/api/organizacion/calendario/", {"desde": str(self.hoy), "hasta": str(self.hoy+timedelta(days=93))})
        self.assertEqual(r.status_code, 400)

    def test_asignacion_futura_no_da_acceso_hoy(self):
        self.asignar(inicio=self.hoy+timedelta(days=1))
        self.cliente.force_authenticate(self.profe)
        self.assertEqual(self.cliente.get("/api/organizacion/grupos/").data["count"], 0)

    def test_restricciones_db(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Grupo.objects.filter(pk=self.grupo.pk).update(cupo_maximo=0)

    def test_no_modifica_estructura_grupo_con_historial(self):
        self.asignar()
        n = Nivel.objects.get(codigo="nivel-2")
        r = self.cliente.patch(f"/api/organizacion/grupos/{self.grupo.pk}/", {"nivel": n.pk}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_periodo_terminado_cierra_asignacion_sin_fecha_final(self):
        self.asignar(inicio=self.hoy-timedelta(days=7))
        Periodo.objects.filter(pk=self.periodo.pk).update(fecha_fin=self.hoy-timedelta(days=1))
        self.cliente.force_authenticate(self.profe)
        self.assertEqual(self.cliente.get("/api/organizacion/grupos/").data["count"], 0)
        r = self.cliente.get("/api/organizacion/calendario/", {"desde": str(self.hoy-timedelta(days=7)), "hasta": str(self.hoy-timedelta(days=1))})
        self.assertEqual(r.data["eventos"], [])

    def test_no_reabre_asignacion_finalizada(self):
        r = self.asignar(inicio=self.hoy-timedelta(days=5), fin=self.hoy-timedelta(days=1))
        respuesta = self.cliente.post(f"/api/organizacion/asignaciones/{r.data['id']}/finalizar/", {"fecha_fin": str(self.hoy)}, format="json")
        self.assertEqual(respuesta.status_code, 400)