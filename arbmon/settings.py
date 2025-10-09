"""Django settings for arbmon project with hardened defaults."""

from __future__ import annotations

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

dotenv_path = BASE_DIR / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)


def _require_setting(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ImproperlyConfigured(f"Missing required setting: {name}")
    return value


SECRET_KEY = _require_setting("DJANGO_SECRET_KEY")
DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"
default_hosts = "localhost,127.0.0.1" if DEBUG else ""
hosts = os.getenv("DJANGO_ALLOWED_HOSTS", default_hosts)
if not hosts:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS must be set for non-debug deployments"
    )
ALLOWED_HOSTS = [host.strip() for host in hosts.split(",") if host.strip()]


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "channels",
    "markets",
    "datafeed",
    "arbitrage",
    "trades",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "arbmon.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

ASGI_APPLICATION = "arbmon.asgi.application"
WSGI_APPLICATION = "arbmon.wsgi.application"

REDIS_URL = _require_setting("REDIS_URL")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

if os.getenv("DJANGO_USE_SQLITE", "0") == "1":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.getenv("DJANGO_SQLITE_NAME", BASE_DIR / "db.sqlite3"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _require_setting("POSTGRES_DB"),
            "USER": _require_setting("POSTGRES_USER"),
            "PASSWORD": _require_setting("POSTGRES_PASSWORD"),
            "HOST": os.getenv("POSTGRES_HOST", "localhost"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }
    }

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("DJANGO_TIMEZONE", "Asia/Ulaanbaatar")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly"
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": int(os.getenv("API_PAGE_SIZE", "100")),
    "DEFAULT_FILTER_BACKENDS": [
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user": os.getenv("API_USER_THROTTLE", "1000/hour"),
        "anon": os.getenv("API_ANON_THROTTLE", "100/hour"),
        "trades": os.getenv("API_TRADES_THROTTLE", "60/hour"),
    },
}

POLL_INTERVAL_SEC = float(os.getenv("POLL_INTERVAL_SEC", "3"))
SCAN_INTERVAL_SEC = float(os.getenv("SCAN_INTERVAL_SEC", str(max(POLL_INTERVAL_SEC * 2, 6))))
DATAFEED_HTTP_TIMEOUT = float(os.getenv("DATAFEED_HTTP_TIMEOUT", "5"))
DATAFEED_MAX_RETRIES = int(os.getenv("DATAFEED_MAX_RETRIES", "3"))
DATAFEED_RETRY_BACKOFF = float(os.getenv("DATAFEED_RETRY_BACKOFF", "1.5"))

FEE_BINANCE_TAKER = float(os.getenv("FEE_BINANCE_TAKER", "0.001"))
FEE_BINANCE_MAKER = float(os.getenv("FEE_BINANCE_MAKER", "0.001"))
FEE_TRADEMN_TAKER = float(os.getenv("FEE_TRADEMN_TAKER", "0.0015"))
FEE_TRADEMN_MAKER = float(os.getenv("FEE_TRADEMN_MAKER", "0.001"))

ARBITRAGE_MIN_NOTIONAL = float(os.getenv("ARBITRAGE_MIN_NOTIONAL", "100.0"))
ARBITRAGE_MIN_NET_SPREAD = float(os.getenv("ARBITRAGE_MIN_NET_SPREAD", "0.001"))

BINANCE_BOOK_TICKER_URL = _require_setting("BINANCE_BOOK_TICKER_URL")
TRADEMN_BOOK_TICKER_URL = os.getenv("TRADEMN_BOOK_TICKER_URL")
TRADEMN_ORDERBOOK_URL = os.getenv("TRADEMN_ORDERBOOK_URL")
if not (TRADEMN_BOOK_TICKER_URL or TRADEMN_ORDERBOOK_URL):
    raise ImproperlyConfigured(
        "One of TRADEMN_BOOK_TICKER_URL or TRADEMN_ORDERBOOK_URL must be configured"
    )

TRADEMN_ORDERBOOK_ASK_KEY = os.getenv("TRADEMN_ORDERBOOK_ASK_KEY", "asks")
TRADEMN_ORDERBOOK_BID_KEY = os.getenv("TRADEMN_ORDERBOOK_BID_KEY", "bids")
TRADEMN_PRICE_INDEX_ASK = int(os.getenv("TRADEMN_PRICE_INDEX_ASK", "0"))
TRADEMN_PRICE_INDEX_BID = int(os.getenv("TRADEMN_PRICE_INDEX_BID", "0"))
TRADEMN_QTY_INDEX = int(os.getenv("TRADEMN_QTY_INDEX", "1"))

DATA_RETENTION_DAYS = float(os.getenv("DATA_RETENTION_DAYS", "7"))
DATA_RETENTION_PRUNE_INTERVAL = int(
    os.getenv("DATA_RETENTION_PRUNE_INTERVAL", "3600")
)
WEBSOCKET_MAX_CONNECTIONS_PER_USER = int(
    os.getenv("WEBSOCKET_MAX_CONNECTIONS_PER_USER", "20")
)
WEBSOCKET_CONNECTION_WINDOW_SEC = int(
    os.getenv("WEBSOCKET_CONNECTION_WINDOW_SEC", "60")
)


CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_ALWAYS_EAGER = False

CELERY_BEAT_SCHEDULE = {
    "poll-tickers": {
        "task": "datafeed.tasks.poll_all_symbols",
        "schedule": POLL_INTERVAL_SEC,
        "options": {"expires": POLL_INTERVAL_SEC},
    },
    "scan-spreads": {
        "task": "arbitrage.tasks.scan_spreads",
        "schedule": SCAN_INTERVAL_SEC,
        "options": {"expires": SCAN_INTERVAL_SEC},
    },
    "prune-stale-data": {
        "task": "datafeed.tasks.prune_timeseries",
        "schedule": DATA_RETENTION_PRUNE_INTERVAL,
        "options": {"expires": DATA_RETENTION_PRUNE_INTERVAL},
    },
}


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
        }
    },
    "loggers": {
        "": {"handlers": ["console"], "level": os.getenv("DJANGO_LOG_LEVEL", "INFO")}
    },
}

