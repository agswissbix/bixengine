from pathlib import Path
import environ
import os

env = environ.Env()
environ.Env.read_env()

BASE_DIR = Path(__file__).resolve().parent.parent

UPLOADS_URL = '/uploads/'
UPLOADS_ROOT = os.path.join(BASE_DIR, '..', 'uploads')
MEDIA_ROOT = os.path.join(BASE_DIR, '..', 'uploads')
STATIC_ROOT = os.path.join(BASE_DIR, '..', 'bixengine', 'commonapp', 'static')

XML_DIR = os.path.join(BASE_DIR, '..', 'xml')
TEMPFILE_URL = '/tempfile/'
TEMPFILE_ROOT = BASE_DIR

SECRET_KEY = env('SECRET_KEY')

DEBUG = True

ALLOWED_HOSTS = [
    'localhost',
    '10.0.0.161',
    env('BIXENGINE_DOMAIN'),
    env('BIXPORTAL_DOMAIN'),
    env('BIXMOBILE_DOMAIN'),
    env('BIXENGINE_IP'),
    env('BIXPORTAL_IP'),
    env('BIXMOBILE_IP'),
    env('BIXVERIFY_IP')
]

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST')
EMAIL_PORT = env('EMAIL_PORT')
EMAIL_USE_TLS = env('EMAIL_TLS')
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # App comuni e custom
    'commonapp',
    'customapp_telefonoamico',
    'customapp_winteler',
    'customapp_pitservice',
    'customapp_belotti',
    'customapp_swissbix',
    'bixsettings',
    'corsheaders',

    # App migrate da bixadmin
    'bixscheduler',
    'bixmonitoring',

    # Scheduler task queue (se serve)
    'django_q',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'commonapp.utils.middleware.PerformanceLoggingMiddleware',
    # 'django_user_agents.middleware.UserAgentMiddleware',  # Scommenta se lo usi ancora
]

ROOT_URLCONF = 'bixengine.urls'

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

WSGI_APPLICATION = 'bixengine.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': env('DATABASE_ENGINE'),
        'NAME': env('DATABASE_NAME'),
        'USER': env('DATABASE_USER'),
        'PASSWORD': env('DATABASE_PASSWORD'),
        'HOST': env('DATABASE_HOST'),
        'PORT': env('DATABASE_PORT'),
        'ATOMIC_REQUESTS': True,
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CORS_ORIGIN_ALLOW_ALL = False
CORS_ALLOWED_ORIGINS = [
    env('BIXENGINE_SERVER'),
    env('BIXPORTAL_SERVER'),
    'http://' + env('BIXENGINE_IP') + ':' + env('BIXENGINE_PORT'),
    'http://' + env('BIXPORTAL_IP') + ':' + env('BIXPORTAL_PORT'),
    'http://' + env('BIXPORTAL_IP') + ':' + env('BIXCUSTOM_PORT'),
    'http://' + env('BIXPORTAL_IP') + ':' + env('BIXPORTAL_NGINX_PORT'),
    'http://' + env('BIXPORTAL_DOMAIN') + ':' + env('BIXPORTAL_NGINX_PORT'),
    'https://' + env('BIXPORTAL_DOMAIN') + ':' + env('BIXPORTAL_NGINX_PORT'),
    'http://' + env('BIXPORTAL_DOMAIN') + ':' + env('BIXCUSTOM_PORT'),
    'https://' + env('BIXPORTAL_DOMAIN') + ':' + env('BIXCUSTOM_PORT'),
    'http://' + env('BIXPORTAL_DOMAIN') + ':' + env('BIXCUSTOM_NGINX_PORT'),
    'https://' + env('BIXPORTAL_DOMAIN') + ':' + env('BIXCUSTOM_NGINX_PORT'),
    'https://' + env('BIXMOBILE_DOMAIN') + ':' + env('BIXMOBILE_PORT'),
    'https://' + env('BIXPORTAL_DOMAIN'),
    'https://' + env('BIXMOBILE_DOMAIN') 
]

CORS_ALLOW_CREDENTIALS = True

CSRF_COOKIE_NAME = "csrftoken"
SESSION_COOKIE_AGE = 1209600  # 2 settimane
SESSION_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = False
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

CSRF_TRUSTED_ORIGINS = [
    env('BIXENGINE_SERVER'),
    env('BIXPORTAL_SERVER'),
    'http://' + env('BIXENGINE_IP') + ':' + env('BIXENGINE_PORT'),
    'http://' + env('BIXPORTAL_IP') + ':' + env('BIXPORTAL_PORT'),
    'http://' + env('BIXPORTAL_IP') + ':' + env('BIXCUSTOM_PORT'),
    'http://' + env('BIXPORTAL_IP') + ':' + env('BIXPORTAL_NGINX_PORT'),
    'http://' + env('BIXPORTAL_DOMAIN') + ':' + env('BIXPORTAL_NGINX_PORT'),
    'https://' + env('BIXPORTAL_DOMAIN') + ':' + env('BIXPORTAL_NGINX_PORT'),
    'http://' + env('BIXPORTAL_DOMAIN') + ':' + env('BIXCUSTOM_PORT'),
    'https://' + env('BIXPORTAL_DOMAIN') + ':' + env('BIXCUSTOM_PORT'),
    'http://' + env('BIXPORTAL_DOMAIN') + ':' + env('BIXCUSTOM_NGINX_PORT'),
    'https://' + env('BIXPORTAL_DOMAIN') + ':' + env('BIXCUSTOM_NGINX_PORT'),
    'https://' + env('BIXMOBILE_DOMAIN') + ':' + env('BIXMOBILE_PORT'),
    'https://' + env('BIXPORTAL_DOMAIN'),
    'https://' + env('BIXMOBILE_DOMAIN')
]

QR_FERNET_KEY = os.getenv("QR_FERNET_KEY")
if not QR_FERNET_KEY:
    raise RuntimeError("QR_FERNET_KEY non impostata nell'ambiente (.env)")

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        # 'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        # 'rest_framework.permissions.IsAuthenticated',
    ),
}

DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024

# Django Q config (mantenuta da bixadmin)
Q_CLUSTER = {
    'name': 'DjangoQ',
    'workers': 4,
    'retry': 120,
    'timeout': 90,
    'queue_limit': 50,
    'bulk': 10,
    'orm': 'default',
    'HOOKS': ['bixscheduler.hooks.on_task_success'],
}
