from rest_framework.routers import DefaultRouter
from .views import DeportistaVista, AcudienteVista, VinculoVista, TipoVista, AutorizacionVista, PoliticaVista
from .documentos_views import TipoDocumentoVista

router=DefaultRouter()
router.register("tipos-documento",TipoDocumentoVista,basename="tipos-documento")
for ruta,vista in [("deportistas",DeportistaVista),("acudientes",AcudienteVista),("vinculos-acudientes",VinculoVista),("tipos-autorizacion",TipoVista),("autorizaciones",AutorizacionVista),("politicas-datos",PoliticaVista)]:
    router.register(ruta,vista,basename=ruta)
urlpatterns=router.urls
