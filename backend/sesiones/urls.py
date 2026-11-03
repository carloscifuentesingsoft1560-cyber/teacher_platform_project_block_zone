from rest_framework.routers import DefaultRouter
from .views import SesionVista

router = DefaultRouter()
router.register('sesiones', SesionVista, basename='sesiones')
urlpatterns = router.urls
