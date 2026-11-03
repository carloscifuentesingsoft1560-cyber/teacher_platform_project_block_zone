"""Configuración local por entorno; PostgreSQL es la base de aplicación."""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
RAIZ_PROYECTO = BASE_DIR.parent
# Esta rama solo puede operar con configuración de pruebas o clúster aislado.
# No constituye un perfil de despliegue autorizado.
if os.getenv('DJANGO_SETTINGS_MODULE') not in ('configuracion.settings_pruebas','configuracion.settings_pruebas_postgresql'):
    raise ImproperlyConfigured('Integración de Etapa 2 aislada: usa el ejecutor PostgreSQL temporal.')
load_dotenv(RAIZ_PROYECTO / ".env", override=False)

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY or len(SECRET_KEY) < 50:
    raise ImproperlyConfigured("Configura DJANGO_SECRET_KEY con al menos 50 caracteres en .env.")

DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() == "true"
ALLOWED_HOSTS = [valor.strip() for valor in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if valor.strip()]
CSRF_TRUSTED_ORIGINS = [valor.strip() for valor in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if valor.strip()]
INSTALLED_APPS = [
    "recursos", "curriculo", "biblioteca", "sesiones",
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "rest_framework", "cuentas.apps.CuentasConfig", "paneles.apps.PanelesConfig", "auditoria.apps.AuditoriaConfig", "organizacion.apps.OrganizacionConfig", "deportistas.apps.DeportistasConfig", "inscripciones.apps.InscripcionesConfig",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "comun.middleware.RespuestasPrivadasMiddleware",
]
ROOT_URLCONF = "configuracion.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request", "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "configuracion.wsgi.application"
ASGI_APPLICATION = "configuracion.asgi.application"
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": os.getenv("POSTGRES_DB", "zona_bloque"),
    "USER": os.getenv("POSTGRES_USER", "zona_bloque"),
    "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
    "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
    "PORT": os.getenv("POSTGRES_PORT", "5432"),
    "CONN_MAX_AGE": 60,
    "OPTIONS": {"connect_timeout": 5},
}}
AUTH_USER_MODEL = "cuentas.Usuario"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
ZDB_ARCHIVOS_PRIVADOS = RAIZ_PROYECTO / 'respaldos' / 'archivos_docentes_privados'
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = os.getenv("DJANGO_COOKIE_SECURE", "True").lower() == "true"
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
SESSION_COOKIE_AGE = 60 * 60 * 8
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
CSRF_FAILURE_VIEW = "comun.errores.error_csrf"
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "comun.errores.manejar_excepcion",
    "DEFAULT_THROTTLE_RATES": {"ingreso": "10/min", "recuperacion": "5/min"},
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
}
