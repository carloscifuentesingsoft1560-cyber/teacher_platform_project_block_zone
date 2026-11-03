from django.urls import path
from .views import PanelVista
from .views_resumen import ResumenVista

urlpatterns = [
    path("administrador/resumen/", ResumenVista.as_view(rol_requerido="administrador")),
    path("coordinador/resumen/", ResumenVista.as_view(rol_requerido="coordinador")),
    path("profesor/", PanelVista.as_view(rol_requerido="profesor")),
    path("coordinador/", PanelVista.as_view(rol_requerido="coordinador")),
    path("administrador/", PanelVista.as_view(rol_requerido="administrador")),
]
