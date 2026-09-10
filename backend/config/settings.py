"""
Django settings for the ProofHalt thin indexer.

Ownership rule (IMPLEMENTATION_PLAN.md §2.2): this service caches on-chain
reads only. It never invents or overrides halt verdicts.
"""

from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

from .env import env_bool, env_csv, env_float, env_int, env_str

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

SECRET_KEY = env_str("DJANGO_SECRET_KEY", "insecure-dev-key-change-me")
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = env_csv("ALLOWED_HOSTS", ["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env_csv("CSRF_TRUSTED_ORIGINS", [])

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "apps.protocols",
    "apps.cases",
    "apps.sync",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# No sessions, cookies or CSRF: reads are public and the sync POSTs are
# guarded by SYNC_SHARED_SECRET instead.
X_FRAME_OPTIONS = "DENY"

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASE_URL = env_str(
    "DATABASE_URL", "postgres://postgres:postgres@localhost:5432/emergency_halt"
)
DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=env_int("DB_CONN_MAX_AGE", 600),
        ssl_require=env_bool("DB_SSL_REQUIRE", False),
    )
}

# ---------------------------------------------------------------------------
# i18n / static
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# ---------------------------------------------------------------------------
# DRF
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.OffsetLimitPagination",
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"]
    + (["rest_framework.renderers.BrowsableAPIRenderer"] if DEBUG else []),
    "DEFAULT_THROTTLE_RATES": {
        # Caps GenLayer RPC amplification via POST /api/sync/*.
        "sync": env_str("SYNC_THROTTLE_RATE", "30/min"),
    },
}

# Matches the contract's DEFAULT_PAGE_LIMIT / MAX_PAGE_LIMIT so API and chain
# pagination agree.
API_DEFAULT_PAGE_SIZE = env_int("API_DEFAULT_PAGE_SIZE", 20)
API_MAX_PAGE_SIZE = env_int("API_MAX_PAGE_SIZE", 50)

CORS_ALLOWED_ORIGINS = env_csv("CORS_ORIGINS", ["http://localhost:3000"])
CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", False)
CORS_ALLOW_HEADERS = (
    "accept",
    "content-type",
    "origin",
    "x-requested-with",
    "x-sync-secret",
)

# ---------------------------------------------------------------------------
# GenLayer (studionet only — see IMPLEMENTATION_PLAN.md §8.1)
# ---------------------------------------------------------------------------

GENLAYER_RPC_URL = env_str("GENLAYER_RPC_URL", "https://studio.genlayer.com/api")
GENLAYER_CHAIN_ID = env_int("GENLAYER_CHAIN_ID", 61999)
HALT_MODULE_ADDRESS = env_str("HALT_MODULE_ADDRESS", "")
DEMO_VAULT_ADDRESS = env_str("DEMO_VAULT_ADDRESS", "")

# `from` address for read-only `gen_call`s. Reads need no funds; this is only
# echoed back as the message sender inside the view.
GENLAYER_READER_ADDRESS = env_str(
    "GENLAYER_READER_ADDRESS", "0x1111111111111111111111111111111111111111"
)
GENLAYER_RPC_TIMEOUT = env_float("GENLAYER_RPC_TIMEOUT", 30.0)
# Throttle between RPC calls to stay clear of studionet rate limits (-32006 / 429).
GENLAYER_RPC_THROTTLE_SECONDS = env_float("GENLAYER_RPC_THROTTLE_SECONDS", 0.25)
GENLAYER_RPC_MAX_RETRIES = env_int("GENLAYER_RPC_MAX_RETRIES", 3)

# Shared secret for POST /api/sync/* fast-path.
# Empty is allowed only when DEBUG=True (local). Production must set a strong secret.
SYNC_SHARED_SECRET = env_str("SYNC_SHARED_SECRET", "")
SYNC_PAGE_LIMIT = env_int("SYNC_PAGE_LIMIT", 50)

if not DEBUG and not SYNC_SHARED_SECRET:
    raise ImproperlyConfigured(
        "SYNC_SHARED_SECRET must be set when DEBUG=False. "
        "An empty secret leaves POST /api/sync/* open to GenLayer RPC abuse."
    )

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------

REDIS_URL = env_str("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = env_str("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = env_str("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TIMEZONE = "UTC"
CELERY_TASK_TIME_LIMIT = env_int("CELERY_TASK_TIME_LIMIT", 300)
CELERY_TASK_SOFT_TIME_LIMIT = env_int("CELERY_TASK_SOFT_TIME_LIMIT", 240)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Beat cadence for the poll-and-diff indexer.
SYNC_POLL_INTERVAL_SECONDS = env_int("SYNC_POLL_INTERVAL_SECONDS", 300)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"}
    },
    "root": {"handlers": ["console"], "level": env_str("LOG_LEVEL", "INFO")},
    "loggers": {
        "apps": {
            "handlers": ["console"],
            "level": env_str("LOG_LEVEL", "INFO"),
            "propagate": False,
        }
    },
}

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)
    SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 0)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
    SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0
