"""
Test settings: SQLite by default so `pytest` needs no Postgres role, and no
network/broker access.

Set `TEST_DATABASE_URL` to run the same suite against Postgres:
    TEST_DATABASE_URL=postgres://user:pass@localhost:5432/emergency_halt_test pytest
"""

import dj_database_url

from .env import env_str
from .settings import *  # noqa: F401,F403
from .settings import BASE_DIR, MIDDLEWARE

SECRET_KEY = "test-secret-key"
DEBUG = False

# No collectstatic in tests.
MIDDLEWARE = [
    item for item in MIDDLEWARE if "whitenoise" not in item
]

TEST_DATABASE_URL = env_str("TEST_DATABASE_URL", "")
if TEST_DATABASE_URL:
    DATABASES = {"default": dj_database_url.parse(TEST_DATABASE_URL)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "test-db.sqlite3",
            "TEST": {"NAME": ":memory:"},
        }
    }

# A configured (but never contacted) halt module address — the reader is faked.
HALT_MODULE_ADDRESS = "0x" + "ab" * 20
GENLAYER_RPC_THROTTLE_SECONDS = 0.0
GENLAYER_RPC_MAX_RETRIES = 1
SYNC_SHARED_SECRET = ""

CELERY_TASK_ALWAYS_EAGER = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
