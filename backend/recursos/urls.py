from rest_framework.routers import DefaultRouter
from .api import ArchivosVista, FuentesVista, FuentesVersionVista, FragmentosVista
router = DefaultRouter()
for ruta, vista in [('archivos', ArchivosVista), ('fuentes', FuentesVista), ('fuentes-version', FuentesVersionVista), ('fragmentos', FragmentosVista)]:
    router.register(ruta, vista, basename='recursos-'+ruta)
urlpatterns = router.urls
