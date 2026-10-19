"""
Configuración del backend de Vortic.
Ver Doc/Informe_Avance_Vortic_Formato.docx, sección 8 (Arquitectura del Sistema).
"""
from pathlib import Path
from datetime import timedelta
from decouple import Csv, config
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# Todo lo que cambia entre la máquina local y el servidor se lee de
# variables de entorno (archivo .env en local, panel de Render en producción).
SECRET_KEY = config('SECRET_KEY', default='dev-secret-key-cambiar-en-produccion')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())

if not DEBUG and SECRET_KEY.startswith('dev-'):
    raise RuntimeError('Configurá SECRET_KEY en las variables de entorno antes de correr en producción.')

# Stock y proveedores: activos por defecto. Se pueden apagar con
# FEATURE_STOCK_PROVEEDORES=False (oculta rutas y la carga de repuestos).
FEATURE_STOCK_PROVEEDORES = config('FEATURE_STOCK_PROVEEDORES', default=True, cast=bool)

# Motor de priorización en n8n (taller/priorizacion.py y taller/motor.py).
# N8N_WEBHOOK_URL vacío = no se usa n8n, solo la regla de respaldo.
N8N_WEBHOOK_URL = config('N8N_WEBHOOK_URL', default='')
N8N_WEBHOOK_SECRETO = config('N8N_WEBHOOK_SECRETO', default='')
# Token con el que n8n se identifica al llamar a /api/motor/...
MOTOR_TOKEN = config('MOTOR_TOKEN', default='')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',

    'usuarios',
    'clientes',
    'taller',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Base de datos: SQLite en local (DATABASE_URL vacío) y PostgreSQL en
# producción (Render completa DATABASE_URL). Mismo código en ambos casos.
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        env='DATABASE_URL', conn_max_age=600,
    )
}

AUTH_USER_MODEL = 'usuarios.Usuario'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Cordoba'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
# Al correr las pruebas se usa un hash de contraseñas rápido (solo en tests).
import sys
if 'test' in sys.argv:
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- DRF / JWT (RNF-10: sin sesión activa no se puede ver ningún dato) ---
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}

# --- CORS: orígenes desde los que el frontend puede llamar a la API ---
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS', default='http://localhost:5173,http://127.0.0.1:5173', cast=Csv(),
)

# --- Producción: cookies seguras y HTTPS detrás del proxy de Render ---
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
    SECURE_HSTS_SECONDS = 3600

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'loggers': {'taller': {'handlers': ['console'], 'level': 'INFO'}},
}
