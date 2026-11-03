from rest_framework.routers import DefaultRouter
from cuentas.views_coordinacion import CoordinacionVista
from .views import DisciplinaVista, NivelVista, PeriodoVista, GrupoVista, AsignacionVista, ProfesoresVista, CalendarioVista

router = DefaultRouter()
for ruta, vista in [("coordinacion", CoordinacionVista), ("disciplinas", DisciplinaVista), ("niveles", NivelVista), ("periodos", PeriodoVista), ("grupos", GrupoVista), ("asignaciones", AsignacionVista), ("profesores", ProfesoresVista), ("calendario", CalendarioVista)]:
    router.register(ruta, vista, basename=ruta)
urlpatterns = router.urls
