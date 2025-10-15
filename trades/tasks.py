"""Celery tasks orchestrating automated arbitrage execution."""

from __future__ import annotations

from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .execution import ArbitrageExecutor, BinanceRESTClient, TradeMNRESTClient


logger = get_task_logger(__name__)


def _require(value: str | None, name: str) -> str:
    if not value:
        raise ImproperlyConfigured(f"Missing required setting: {name}")
    return value


def _build_executor() -> ArbitrageExecutor:
    trademn_client = TradeMNRESTClient(
        api_key=_require(getattr(settings, "TRADEMN_API_KEY", None), "TRADEMN_API_KEY"),
        api_secret=_require(
            getattr(settings, "TRADEMN_API_SECRET", None), "TRADEMN_API_SECRET"
        ),
    )
    binance_client = BinanceRESTClient(
        api_key=_require(getattr(settings, "BINANCE_API_KEY", None), "BINANCE_API_KEY"),
        api_secret=_require(
            getattr(settings, "BINANCE_API_SECRET", None), "BINANCE_API_SECRET"
        ),
    )
    return ArbitrageExecutor(
        trademn_client,
        binance_client,
        deposit_addresses=getattr(settings, "ARBITRAGE_DEPOSIT_ADDRESSES", {}),
    )


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True)
def execute_arbitrage(self) -> int:
    """Trigger a single arbitrage execution pass."""

    executor = _build_executor()
    executed = executor.execute_once()
    logger.info("arbitrage.task.complete", extra={"executed": executed})
    return executed

