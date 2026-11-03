from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from cuentas.models import Usuario
from organizacion.models import Disciplina, Nivel, Periodo, Grupo, Asignacion

class PruebasResumenInstitucional(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hoy = timezone.localdate()
        cls.admin = Usuario.objects.create_user(username="demo_admin_res", rol="administrador")
        cls.coord = Usuario.objects.create_user(username="demo_coord_res", rol="coordinador")
        cls.p1 = Usuario.objects.create_user(username="demo_p1_res", rol="profesor")
        cls.p2 = Usuario.objects.create_user(username="demo_p2_res", rol="profesor")
        cls.inactivo = Usuario.objects.create_user(username="demo_p3_res", rol="profesor", is_active=False)
        cls.disciplina = Disciplina.objects.get(codigo="escalada")
        cls.n1 = Nivel.objects.get(codigo="nivel-1")
        cls.n2 = Nivel.objects.get(codigo="nivel-2")
        cls.periodo = Periodo.objects.create(codigo="demo-resumen", nombre="Ciclo ficticio", fecha_inicio=cls.hoy-timedelta(days=30), fecha_fin=cls.hoy+timedelta(days=30))
        cls.otro_periodo = Periodo.objects.create(codigo="demo-anterior", nombre="Anterior ficticio", activo=False, fecha_inicio=cls.hoy-timedelta(days=100), fecha_fin=cls.hoy-timedelta(days=50))
        cls.g1 = Grupo.objects.create(codigo="demo-res-a", nombre="Ficticio A", disciplina=cls.disciplina, nivel=cls.n1, periodo=cls.periodo, cupo_maximo=10)
        cls.g2 = Grupo.objects.create(codigo="demo-res-b", nombre="Ficticio B", disciplina=cls.disciplina, nivel=cls.n2, periodo=cls.periodo, cupo_maximo=10)
        Grupo.objects.create(codigo="demo-res-c", nombre="Ficticio C", disciplina=cls.disciplina, nivel=cls.n1, periodo=cls.periodo, cupo_maximo=10, activo=False)
        for usuario, grupo in [(cls.p1, cls.g1), (cls.p1, cls.g2), (cls.inactivo, cls.g1)]:
            Asignacion.objects.create(usuario=usuario, grupo=grupo, tipo="profesor", fecha_inicio=cls.hoy)

    def setUp(self):
        self.c = APIClient()
        self.c.force_authenticate(self.admin)

    def resumen(self, **filtros):
        r = self.c.get("/api/paneles/administrador/resumen/", filtros)
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    def test_estadisticas_reales_sin_duplicar_profesores(self):
        datos = self.resumen()
        self.assertEqual(datos["profesores"], {"activos": 2, "inactivos": 1, "sin_grupo": 1})
        self.assertEqual(datos["grupos"], {"activos": 2, "inactivos": 1})
        self.assertEqual(datos["asignaciones"], {"vigentes": 3, "operativas": 2})
        self.assertEqual(datos["periodos"], {"total": 2, "activos": 1, "en_curso": 1})

    def test_coordinador_activo_sin_datos_de_seguridad(self):
        datos = self.resumen()["coordinacion"]
        self.assertEqual(datos["estado"], "activo")
        self.assertEqual(set(datos["actual"]), {"id", "nombre"})

    def test_vacante_sin_inventar_titular(self):
        Usuario.objects.filter(pk=self.coord.pk).update(is_active=False)
        self.assertEqual(self.resumen()["coordinacion"], {"estado": "vacante", "cantidad_activos": 0, "actual": None})

    def test_filtra_por_nivel_y_preserva_personal_institucional(self):
        datos = self.resumen(nivel=self.n2.pk)
        self.assertEqual(datos["grupos"]["activos"], 1)
        self.assertEqual(datos["profesores"]["activos"], 2)
        self.assertEqual(datos["asignaciones"]["vigentes"], 1)
        self.assertEqual(len(datos["niveles"]), 1)

    def test_periodo_sin_grupos_y_catalogos_con_cero_real(self):
        datos = self.resumen(periodo=self.otro_periodo.pk)
        self.assertEqual(datos["grupos"]["activos"], 0)
        self.assertEqual(datos["profesores"]["sin_grupo"], 2)
        self.assertEqual(len(datos["niveles"]), 5)
        self.assertTrue(all(n["total"] == 0 for n in datos["niveles"]))

    def test_fecha_y_filtros_invalidos_rechazados(self):
        for filtro in [{"fecha": "invalida"}, {"periodo": 999999}, {"disciplina": "abc"}]:
            self.assertEqual(self.c.get("/api/paneles/administrador/resumen/", filtro).status_code, 400)

    def test_profesor_no_consulta_tableros_institucionales(self):
        self.c.force_authenticate(self.p1)
        for rol in ["administrador", "coordinador"]:
            self.assertEqual(self.c.get(f"/api/paneles/{rol}/resumen/").status_code, 403)

    def test_coordinador_operativo_y_admin_sin_asignacion_tienen_su_resumen(self):
        self.c.force_authenticate(self.coord)
        self.assertEqual(self.c.get("/api/paneles/coordinador/resumen/").status_code, 200)
        self.assertEqual(self.c.get("/api/paneles/administrador/resumen/").status_code, 403)

    def test_no_existen_estadisticas_de_modulos_futuros(self):
        datos = self.resumen()
        for nombre in ["sesiones", "asistencia", "valoraciones", "cumplimiento"]:
            self.assertNotIn(nombre, datos)

    def test_anonimo_rechazado(self):
        self.c.force_authenticate(None)
        self.assertEqual(self.c.get("/api/paneles/administrador/resumen/").status_code, 403)

    def test_conteos_y_enlaces_de_detalle_comparten_filtros(self):
        datos = self.resumen(nivel=self.n2.pk)
        grupos = self.c.get("/api/organizacion/grupos/", {"nivel": self.n2.pk, "activo": "true"})
        asignaciones = self.c.get("/api/organizacion/asignaciones/", {"nivel": self.n2.pk, "estado": "operativas", "fecha": str(self.hoy)})
        profesores = self.c.get("/api/organizacion/profesores/", {"nivel": self.n2.pk, "activo": "true", "sin_grupo": "true", "fecha": str(self.hoy)})
        self.assertEqual(grupos.data["count"], datos["grupos"]["activos"])
        self.assertEqual(asignaciones.data["count"], datos["asignaciones"]["operativas"])
        self.assertEqual(profesores.data["count"], datos["profesores"]["sin_grupo"])