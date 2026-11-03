"""SQLite en memoria exclusivamente para pruebas aisladas, nunca para servir la app."""
import os

os.environ["DJANGO_SECRET_KEY"] = "clave-ficticia-exclusiva-de-pruebas-aisladas-sin-uso-operativo-123456"
from .settings import *  # noqa: E402,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
