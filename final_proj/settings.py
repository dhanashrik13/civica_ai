import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

from .secrets import get_secret

SECRET_KEY = get_secret("DJANGO_SECRET_KEY", "django-insecure-dev-only-key")
DEBUG = get_secret("DJANGO_DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = [host.strip() for host in get_secret("DJANGO_ALLOWED_HOSTS", "*").split(",") if host.strip()]

CSRF_TRUSTED_ORIGINS = [
    "https://*.ngrok-free.dev",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]


# Application definition

INSTALLED_APPS = [
    'accounts',
    'assistant',
    'dashboards',
    'notifications',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',  # REQUIRED by allauth
    'issues',
    'landing',

    # ALLAUTH
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

    # ENTERPRISE STACK
    'health_check',
    'simple_history',
    'django_softdelete',
]

SITE_ID = 3

# ALLAUTH SETTINGS
ACCOUNT_USER_MODEL_USERNAME_FIELD = 'username'
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_ADAPTER = 'accounts.adapters.MySocialAccountAdapter'
ACCOUNT_ADAPTER = 'allauth.account.adapter.DefaultAccountAdapter'




LOGIN_REDIRECT_URL = '/redirect-dashboard/'


LOGOUT_REDIRECT_URL = 'accounts:login'
SOCIALACCOUNT_LOGIN_ON_GET = True 

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'OAUTH_PKCE_ENABLED': True,
        'FETCH_USERINFO': True,
    }
}


# SECURITY NOTE: OAuth 2.0 requires HTTPS in production.
# Ensure redirect URIs are validated and SECURE_SSL_REDIRECT is enabled.

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'accounts.middleware.DomainIdentityMiddleware',
    'accounts.middleware.OperationalForensicsMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'accounts.middleware.RBACMiddleware',
    'dashboards.middleware.language_middleware.AutoDetectLanguageMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

ROOT_URLCONF = 'final_proj.urls'

LANGUAGES = [
    ('en', 'English'),
    ('hi', 'Hindi'),
    ('mr', 'Marathi'),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]



TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'final_proj.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en'
TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_TZ = True


STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = "accounts.User"
from django.contrib.messages import constants as messages
MESSAGE_TAGS = {
    messages.DEBUG: 'debug',
    messages.INFO: 'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR: 'error',
}


MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


SESSION_COOKIE_AGE = 1209600  # 2 weeks in seconds
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")
LOGOUT_REDIRECT_URL = 'accounts:login'

# Celery Configuration Options
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# RESILIENCE HARDENING
CELERY_BROKER_RECONNECT_ON_STARTUP = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_ACKS_LATE = True # Ensure task is not lost if worker crashes
CELERY_WORKER_PREFETCH_MULTIPLIER = 1 # Prevent one worker from hoarding tasks
CELERY_TASK_SOFT_TIME_LIMIT = 30 # 30 seconds soft limit
CELERY_TASK_TIME_LIMIT = 60      # 60 seconds hard limit

# PERFORMANCE HARDENING: Strict timeouts for broker connection
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'socket_timeout': 5.0,
    'socket_connect_timeout': 5.0,
    'max_retries': 3,
    'interval_start': 0.2,
    'interval_step': 0.5,
    'interval_max': 2.0,
}
# Prevent result backend connection from blocking
CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS = {
    'socket_timeout': 2.0,
    'socket_connect_timeout': 2.0,
    'retry_policy': {
        'timeout': 5.0
    }
}

import sys
if 'test' in sys.argv:
    CELERY_TASK_ALWAYS_EAGER = True

# Priority Queues
from kombu import Exchange, Queue

CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TASK_QUEUES = (
    Queue('default', Exchange('default'), routing_key='default'),
    Queue('high_priority', Exchange('high_priority'), routing_key='high_priority'),
    Queue('medium_priority', Exchange('medium_priority'), routing_key='medium_priority'),
    Queue('low_priority', Exchange('low_priority'), routing_key='low_priority'),
    Queue('dlq', Exchange('dlq'), routing_key='dlq'), # Dead Letter Queue
)

# Celery Beat Schedule
CELERY_BEAT_SCHEDULE = {
    'scan-overdue-escalations': {
        'task': 'issues.tasks.scan_and_escalate_issues',
        'schedule': 3600.0, # Every hour
    },
    'refresh-governance-analytics': {
        'task': 'dashboards.tasks.refresh_analytics_cache',
        'schedule': 3600.0 * 6, # Every 6 hours
    },
    'daily-db-backup': {
        'task': 'final_proj.tasks.run_database_backup',
        'schedule': 86400.0, # Every 24 hours
    },
}

CELERY_TASK_ROUTES = {
    'issues.tasks.scan_and_escalate_issues': {'queue': 'high_priority'},
    'dashboards.tasks.refresh_analytics_cache': {'queue': 'low_priority'},
    'issues.tasks.enrich_issue_context': {'queue': 'high_priority'},
    'accounts.tasks.recalculate_officer_metrics': {'queue': 'low_priority'},
    'accounts.tasks.sync_citizen_profile_counters': {'queue': 'medium_priority'},
    'issues.tasks.update_dashboard_projections': {'queue': 'low_priority'},
}

# ==========================================
# PRODUCTION SECURITY HARDENING
# ==========================================
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Ratelimit settings
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = 'default'

# ==========================================
# OBSERVABILITY & LOGGING
# ==========================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s',
        },
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'production.log',
            'formatter': 'json',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'final_proj': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# Ensure log directory exists
if not os.path.exists(BASE_DIR / 'logs'):
    os.makedirs(BASE_DIR / 'logs')
