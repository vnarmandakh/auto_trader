"""Celery tasks for polling external data feeds."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Dict, Tuple

import requests
from celery import shared_task
from celery.utils.log import get_task_logger
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from markets.models import Symbol

from .models import TickerSnapshot


logger = get_task_logger(__name__)

_retry_strategy = Retry(
    total=int(getattr(settings, "DATAFEED_MAX_RETRIES", 3)),
    backoff_factor=float(getattr(settings, "DATAFEED_RETRY_BACKOFF", 1.5)),
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset({"GET"}),
)

_http_session = requests.Session()
_adapter = HTTPAdapter(max_retries=_retry_strategy)
_http_session.mount("http://", _adapter)
_http_session.mount("https://", _adapter)


def _http_get(url: str, timeout: float) -> dict:
    response = _http_session.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _binance(symbol: str, timeout: float) -> Tuple[float, float]:
    data = _http_get(settings.BINANCE_BOOK_TICKER_URL.format(symbol=symbol), timeout)
    return float(data["bidPrice"]), float(data["askPrice"])


def _trademn(symbol: str, timeout: float) -> Tuple[float, float]:
    if settings.TRADEMN_BOOK_TICKER_URL:
        data = _http_get(settings.TRADEMN_BOOK_TICKER_URL.format(symbol=symbol), timeout)
        bid = float(data.get("bidPrice") or data.get("bestBid") or data["bid"][0])
        ask = float(data.get("askPrice") or data.get("bestAsk") or data["ask"][0])
        return bid, ask

    data = _http_get(settings.TRADEMN_ORDERBOOK_URL.format(symbol=symbol), timeout)
    asks = data.get(settings.TRADEMN_ORDERBOOK_ASK_KEY, [])
    bids = data.get(settings.TRADEMN_ORDERBOOK_BID_KEY, [])
    ask_index = settings.TRADEMN_PRICE_INDEX_ASK
    bid_index = settings.TRADEMN_PRICE_INDEX_BID
    best_ask = float(asks[0][ask_index]) if asks else float("inf")
    best_bid = float(bids[0][bid_index]) if bids else 0.0
    return best_bid, best_ask


def _should_persist(last_snapshot: TickerSnapshot | None, payload: Dict[str, float]) -> bool:
    if not last_snapshot:
        return True
    return not (
        last_snapshot.bi_bid == payload["bi_bid"]
        and last_snapshot.bi_ask == payload["bi_ask"]
        and last_snapshot.tr_bid == payload["tr_bid"]
        and last_snapshot.tr_ask == payload["tr_ask"]
    )


@shared_task(bind=True)
def poll_all_symbols(self):
    """Poll all configured symbols with resilience to upstream failures."""

    timeout = float(getattr(settings, "DATAFEED_HTTP_TIMEOUT", 5.0))
    channel_layer = get_channel_layer()
    symbols = list(Symbol.objects.all())

    for symbol in symbols:
        try:
            binance_bid, binance_ask = _binance(symbol.binance_symbol, timeout)
            trademn_bid, trademn_ask = _trademn(symbol.trademn_symbol, timeout)
        except Exception as exc:  # noqa: BLE001 - log and continue
            logger.warning(
                "ticker.poll.failed",
                extra={
                    "symbol": symbol.name,
                    "binance_symbol": symbol.binance_symbol,
                    "trademn_symbol": symbol.trademn_symbol,
                    "error": str(exc),
                },
            )
            continue

        payload = {
            "symbol": symbol.name,
            "bi_bid": binance_bid,
            "bi_ask": binance_ask,
            "tr_bid": trademn_bid,
            "tr_ask": trademn_ask,
        }

        last_snapshot = (
            TickerSnapshot.objects.filter(symbol=symbol).order_by("-ts").first()
        )

        if not _should_persist(last_snapshot, payload):
            logger.debug("ticker.poll.skipped", extra={"symbol": symbol.name})
            continue

        with transaction.atomic():
            snapshot = TickerSnapshot.objects.create(
                symbol=symbol,
                bi_bid=binance_bid,
                bi_ask=binance_ask,
                tr_bid=trademn_bid,
                tr_ask=trademn_ask,
            )

        payload_with_ts = {
            "type": "ticker",
            "payload": {**payload, "ts": snapshot.ts.isoformat()},
        }

        async_to_sync(channel_layer.group_send)(
            "tickers",
            {"type": "broadcast.message", "text": json.dumps(payload_with_ts)},
        )
        logger.info("ticker.poll.ok", extra={"symbol": symbol.name})


@shared_task
def prune_timeseries():
    """Remove aged rows from ticker and arbitrage tables."""

    cutoff = timezone.now() - timedelta(days=settings.DATA_RETENTION_DAYS)
    ticker_deleted, _ = TickerSnapshot.objects.filter(ts__lt=cutoff).delete()

    from arbitrage.models import ArbitrageOpportunity
    from trades.models import TradeExecution

    arbitrage_deleted, _ = ArbitrageOpportunity.objects.filter(ts__lt=cutoff).delete()
    trades_deleted, _ = TradeExecution.objects.filter(ts__lt=cutoff).delete()

    logger.info(
        "timeseries.pruned",
        extra={
            "cutoff": cutoff.isoformat(),
            "ticker_deleted": ticker_deleted,
            "arbitrage_deleted": arbitrage_deleted,
            "trades_deleted": trades_deleted,
        },
    )
