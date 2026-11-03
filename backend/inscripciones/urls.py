from rest_framework.routers import DefaultRouter
from .views import InscripcionVista, PropuestaVista
from .views_ascensos import AscensoVista
router=DefaultRouter()
router.register("inscripciones",InscripcionVista,basename="inscripciones")
router.register("propuestas",PropuestaVista,basename="propuestas")
router.register('ascensos', AscensoVista, basename='ascensos')
urlpatterns=router.urls
