import os
from pathlib import Path
from dotenv import load_dotenv
BASE_DIR=Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR/".env")
SECRET_KEY=os.getenv("DJANGO_SECRET_KEY","insecure")
DEBUG=os.getenv("DJANGO_DEBUG","0")=="1"
ALLOWED_HOSTS=os.getenv("DJANGO_ALLOWED_HOSTS","*").split(",")
INSTALLED_APPS=["django.contrib.admin","django.contrib.auth","django.contrib.contenttypes","django.contrib.sessions","django.contrib.messages","django.contrib.staticfiles","rest_framework","channels","markets","datafeed","arbitrage","trades","dashboard"]
MIDDLEWARE=["django.middleware.security.SecurityMiddleware","django.contrib.sessions.middleware.SessionMiddleware","django.middleware.common.CommonMiddleware","django.middleware.csrf.CsrfViewMiddleware","django.contrib.auth.middleware.AuthenticationMiddleware","django.contrib.messages.middleware.MessageMiddleware","django.middleware.clickjacking.XFrameOptionsMiddleware"]
ROOT_URLCONF="arbmon.urls"
TEMPLATES=[{"BACKEND":"django.template.backends.django.DjangoTemplates","DIRS":[BASE_DIR/'templates'],"APP_DIRS":True,"OPTIONS":{"context_processors":["django.template.context_processors.debug","django.template.context_processors.request","django.contrib.auth.context_processors.auth","django.contrib.messages.context_processors.messages"]}}]
ASGI_APPLICATION="arbmon.asgi.application"
WSGI_APPLICATION="arbmon.wsgi.application"
REDIS_URL=os.getenv("REDIS_URL","redis://localhost:6379/0")
CHANNEL_LAYERS={"default":{"BACKEND":"channels_redis.core.RedisChannelLayer","CONFIG":{"hosts":[REDIS_URL]}}}
DATABASES={"default":{"ENGINE":"django.db.backends.postgresql","NAME":os.getenv("POSTGRES_DB","arbmon"),"USER":os.getenv("POSTGRES_USER","arbuser"),"PASSWORD":os.getenv("POSTGRES_PASSWORD","arbpass"),"HOST":os.getenv("POSTGRES_HOST","localhost"),"PORT":os.getenv("POSTGRES_PORT","5432")}}
LANGUAGE_CODE="en-us"; TIME_ZONE=os.getenv("DJANGO_TIMEZONE","Asia/Ulaanbaatar"); USE_I18N=True; USE_TZ=True
STATIC_URL="/static/"; STATIC_ROOT=BASE_DIR/"staticfiles"; STATICFILES_DIRS=[BASE_DIR/"static"]
DEFAULT_AUTO_FIELD="django.db.models.BigAutoField"
REST_FRAMEWORK={"DEFAULT_PERMISSION_CLASSES":["rest_framework.permissions.IsAuthenticatedOrReadOnly"]}
POLL_INTERVAL_SEC=float(os.getenv("POLL_INTERVAL_SEC","3"))
FEE_BINANCE_TAKER=float(os.getenv("FEE_BINANCE_TAKER","0.001")); FEE_BINANCE_MAKER=float(os.getenv("FEE_BINANCE_MAKER","0.001"))
FEE_TRADEMN_TAKER=float(os.getenv("FEE_TRADEMN_TAKER","0.0015")); FEE_TRADEMN_MAKER=float(os.getenv("FEE_TRADEMN_MAKER","0.001"))
ARBITRAGE_MIN_NOTIONAL=float(os.getenv("ARBITRAGE_MIN_NOTIONAL","100.0"))
ARBITRAGE_MIN_NET_SPREAD=float(os.getenv("ARBITRAGE_MIN_NET_SPREAD","0.001"))
BINANCE_BOOK_TICKER_URL=os.getenv("BINANCE_BOOK_TICKER_URL")
TRADEMN_BOOK_TICKER_URL=os.getenv("TRADEMN_BOOK_TICKER_URL")
TRADEMN_ORDERBOOK_URL=os.getenv("TRADEMN_ORDERBOOK_URL")
TRADEMN_ORDERBOOK_ASK_KEY=os.getenv("TRADEMN_ORDERBOOK_ASK_KEY","asks")
TRADEMN_ORDERBOOK_BID_KEY=os.getenv("TRADEMN_ORDERBOOK_BID_KEY","bids")
TRADEMN_PRICE_INDEX_ASK=int(os.getenv("TRADEMN_PRICE_INDEX_ASK","0"))
TRADEMN_PRICE_INDEX_BID=int(os.getenv("TRADEMN_PRICE_INDEX_BID","0"))
TRADEMN_QTY_INDEX=int(os.getenv("TRADEMN_QTY_INDEX","1"))
from celery.schedules import crontab
CELERY_BROKER_URL=REDIS_URL; CELERY_RESULT_BACKEND=REDIS_URL
CELERY_TASK_ALWAYS_EAGER=False
CELERY_BEAT_SCHEDULE={"poll-tickers":{"task":"datafeed.tasks.poll_all_symbols","schedule":POLL_INTERVAL_SEC},"scan-spreads":{"task":"arbitrage.tasks.scan_spreads","schedule":POLL_INTERVAL_SEC}}
