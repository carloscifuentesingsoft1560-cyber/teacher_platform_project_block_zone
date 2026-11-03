from django.urls import path
from .views import CsrfVista, IngresarVista, SalirVista, SesionVista

urlpatterns = [
    path("csrf/", CsrfVista.as_view(), name="csrf"),
    path("ingresar/", IngresarVista.as_view(), name="ingresar"),
    path("sesion/", SesionVista.as_view(), name="sesion"),
    path("salir/", SalirVista.as_view(), name="salir"),
]
