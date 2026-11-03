from rest_framework.routers import DefaultRouter
from .api import EjercicioVista, MaterialVista, TerminoVista, CandidatoVista
router = DefaultRouter()
for ruta, vista in [('versiones', EjercicioVista), ('materiales', MaterialVista), ('terminos', TerminoVista), ('candidatos', CandidatoVista)]:
    router.register(ruta, vista, basename='biblioteca-'+ruta)
urlpatterns = router.urls
