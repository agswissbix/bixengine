"""
Django settings for bixengine project.

Generated by 'django-admin startproject' using Django 5.0.9.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.0/ref/settings/
"""

from pathlib import Path
import environ

env = environ.Env()
environ.Env.read_env()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-in)&iyx749f@sq53z%%lbf(y7o_ch8&ifst-dk3od373(*%gj('

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['localhost','192.168.10.10']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'commonapp',
    'corsheaders',
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


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'sqllite': {
        'ENGINE': 'django.db.bixdata_backend.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    },
    'default': {
        'ENGINE': env('DATABASE_ENGINE'),
        'NAME': env('DATABASE_NAME'),
        'USER': env('DATABASE_USER'),
        'PASSWORD': env('DATABASE_PASSWORD'),
        'HOST': env('DATABASE_HOST'),
        'PORT': env('DATABASE_PORT'),
        'ATOMIC_REQUESTS': True,  # gestione automatica delle transazioni. ogni funzione della view è trattata come singola transazione e se capitano errori va in rollback
    },
}


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CORS_ORIGIN_ALLOW_ALL = False
CORS_ALLOWED_ORIGINS = [
    'http://localhost:8000',
    'http://localhost:8001',
    'https://localhost:8002',
    'http://localhost:3000',
    'http://localhost:3001',
    'https://localhost:3002',
    'http://192.168.10.11:3000',
    'http://192.168.10.11:3001',
    'https://192.168.10.11:3002',
    'https://192.168.10.11:443',
    'https://192.168.10.11',
    env('BIXENGINE_SERVER'),
    env('BIXPORTAL_SERVER'),
]

CORS_ALLOW_CREDENTIALS = True

CSRF_COOKIE_NAME = "csrftoken"
SESSION_COOKIE_AGE = 1209600  # 2 settimane, ad esempio


# 2. Se usi Django >= 4.0, devi aggiungere l'origin di frontend qui:
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://localhost:8001',
    'https://localhost:8002',
    'http://localhost:3000',
    'http://localhost:3001',
    'https://localhost:3002',
    'http://192.168.10.11:3000',
    'http://192.168.10.11:3001',
    'https://192.168.10.11:3002',
    'https://192.168.10.11:443',
    'https://192.168.10.11',
    env('BIXENGINE_SERVER'),
    env('BIXPORTAL_SERVER'),
]

SESSION_COOKIE_SAMESITE = 'None'  # Add this
CSRF_COOKIE_SAMESITE = 'None'    # Add this

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = False  # Per ora, per testare in locale
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')