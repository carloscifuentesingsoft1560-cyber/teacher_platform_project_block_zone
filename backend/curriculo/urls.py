from rest_framework.routers import DefaultRouter
from .api import ProgramaVista, MallaVista, ImportacionVista
router = DefaultRouter()
for ruta, vista in [('programas', ProgramaVista), ('versiones', MallaVista), ('importaciones', ImportacionVista)]:
    router.register(ruta, vista, basename='curriculo-'+ruta)
urlpatterns = router.urls
