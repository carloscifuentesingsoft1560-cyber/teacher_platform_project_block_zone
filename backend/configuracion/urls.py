from django.contrib import admin
from django.urls import include, path
from cuentas.views_usuarios import ConfirmarRecuperacionVista

from rest_framework.routers import DefaultRouter
from cuentas.api_nucleo import IdentidadVista, PersonaVista
nucleo = DefaultRouter()
nucleo.register("identidad",IdentidadVista,basename="identidad")
nucleo.register("personas-institucionales",PersonaVista,basename="personas-institucionales")

urlpatterns = [
    path("api/recursos/", include("recursos.urls")),
    path("api/curriculo/", include("curriculo.urls")),
    path("api/biblioteca/", include("biblioteca.urls")),
    path("api/",include(nucleo.urls)),
    path("api/", include("deportistas.urls")),
    path("api/", include("inscripciones.urls")),
    path("api/usuarios/", include("cuentas.urls_usuarios")),
    path("api/organizacion/", include("organizacion.urls")),
    path("api/recuperacion/confirmar/", ConfirmarRecuperacionVista.as_view()),
    path("admin/", admin.site.urls),
    path("api/autenticacion/", include("cuentas.urls")),
    path("api/paneles/", include("paneles.urls")),
]
