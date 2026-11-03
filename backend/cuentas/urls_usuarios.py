from rest_framework.routers import DefaultRouter
from .views_usuarios import UsuariosVista

router = DefaultRouter()
router.register("", UsuariosVista, basename="usuarios")
urlpatterns = router.urls
