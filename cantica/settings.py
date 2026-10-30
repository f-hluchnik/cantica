"""Django settings for Directus Cantica.

Everything environment-specific comes from environment variables:

    CANTICA_ENV      'production' on Fly; anything else = development (default)
    DEBUG            '1' to enable debug mode
    SECRET_KEY       required in production
    ALLOWED_HOSTS    comma-separated host names (production)
    DATABASE_PATH    SQLite file (default: <repo>/db.sqlite3; production: /data/cantica.sqlite3)
    SENTRY_DSN       optional; Sentry is enabled only when set
    UMAMI_WEBSITE_ID optional; the analytics script is rendered only when set
"""
import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

CANTICA_ENV = os.environ.get('CANTICA_ENV', 'development')
PRODUCTION = CANTICA_ENV == 'production'
DEBUG = os.environ.get('DEBUG', '0') == '1'

_DEV_SECRET_KEY = 'insecure-development-key-do-not-use-in-production'  # noqa: S105
SECRET_KEY = os.environ.get('SECRET_KEY', _DEV_SECRET_KEY)
if PRODUCTION and SECRET_KEY == _DEV_SECRET_KEY:
    raise ImproperlyConfigured('SECRET_KEY must be set in production')

_hosts = os.environ.get('ALLOWED_HOSTS', '')
ALLOWED_HOSTS = [h.strip() for h in _hosts.split(',') if h.strip()] or ['localhost', '127.0.0.1', '[::1]']
CSRF_TRUSTED_ORIGINS = [f'https://{h}' for h in ALLOWED_HOSTS if h not in ('localhost', '127.0.0.1', '[::1]')]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    'liturgy',
    'catalog',
    'rules',
    'web',
]

MIDDLEWARE = [
    'web.middleware.LiveMiddleware',  # first: answers /live before host validation
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'cantica.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'web.context_processors.site',
            ],
        },
    },
]

WSGI_APPLICATION = 'cantica.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('DATABASE_PATH', str(BASE_DIR / 'db.sqlite3')),
        'OPTIONS': {
            'init_command': 'PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;',
            'transaction_mode': 'IMMEDIATE',
            'timeout': 20,
        },
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'cs'
TIME_ZONE = 'Europe/Prague'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
TESTING = sys.argv[1:2] == ['test']
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    # Hashed + compressed files need collectstatic (done in the Docker build); elsewhere use the plain storage.
    'staticfiles': {
        'BACKEND': (
            'whitenoise.storage.CompressedManifestStaticFilesStorage'
            if PRODUCTION and not TESTING
            else 'django.contrib.staticfiles.storage.StaticFilesStorage'
        ),
    },
}

# Outside production, WhiteNoise serves files straight from the app static/ dirs (no collectstatic),
# so runserver shows CSS/JS even without DEBUG=1.
WHITENOISE_USE_FINDERS = not PRODUCTION
WHITENOISE_AUTOREFRESH = not PRODUCTION

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

if PRODUCTION:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': 'INFO'},
}

# --- Cantica ----------------------------------------------------------------------------

CANTICA_DATA_DIR = Path(os.environ.get('CANTICA_DATA_DIR', str(BASE_DIR / 'data')))
CANTICA_RAW_CALENDAR_DIR = CANTICA_DATA_DIR / 'calendar' / 'raw'
CANTICA_CELEBRATIONS_FILE = CANTICA_DATA_DIR / 'liturgy' / 'celebrations.yaml'
CANTICA_CURATION_FILE = CANTICA_DATA_DIR / 'curated' / 'curation.yaml'
CANTICA_PERIODS_FILE = CANTICA_DATA_DIR / 'liturgy' / 'periods.yaml'
# /health reports 'warn' when fewer days of calendar data remain.
CANTICA_HEALTH_MIN_DAYS_AHEAD = 180
CANTICA_DIOCESE_COOKIE = 'dieceze'
# Test instance: ask search engines to stay away (robots.txt), so crawlers don't keep waking it up.
CANTICA_NOINDEX = os.environ.get('CANTICA_NOINDEX', '0') == '1'
UMAMI_WEBSITE_ID = os.environ.get('UMAMI_WEBSITE_ID', '')

SENTRY_DSN = os.environ.get('SENTRY_DSN', '')
if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(dsn=SENTRY_DSN, environment=CANTICA_ENV, send_default_pii=False, traces_sample_rate=0)
