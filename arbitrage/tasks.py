"""Arbitrage spread scanning tasks."""

from __future__ import annotations

import json
import math
from datetime import timedelta

from asgiref.sync import async_to_sync
from celery import shared_task
from celery.utils.log import get_task_logger
from channels.layers import get_channel_layer
from django.conf import settings
from django.utils import timezone

from datafeed.models import TickerSnapshot
from markets.models import Symbol

from .models import ArbitrageOpportunity


logger = get_task_logger(__name__)


def _net_spread(buy_price: float, sell_price: float, buy_fee: float, sell_fee: float) -> float:
    denominator = buy_price * (1 + buy_fee)
    if denominator == 0:
        return 0.0
    return (sell_price * (1 - sell_fee) - buy_price * (1 + buy_fee)) / denominator


def _should_emit(symbol: Symbol, direction: str, spread: float) -> bool:
    if spread < settings.ARBITRAGE_MIN_NET_SPREAD:
        return False
    last_opportunity = (
        ArbitrageOpportunity.objects.filter(symbol=symbol, direction=direction)
        .order_by("-ts")
        .first()
    )
    return not last_opportunity or not math.isclose(
        last_opportunity.net_spread_pct, spread, rel_tol=1e-6, abs_tol=1e-8
    )


@shared_task(bind=True)
def scan_spreads(self):
    """Evaluate most recent ticker snapshots and emit actionable opportunities."""

    min_net = settings.ARBITRAGE_MIN_NET_SPREAD
    channel_layer = get_channel_layer()
    stale_cutoff = timezone.now() - timedelta(seconds=settings.SCAN_INTERVAL_SEC * 5)

    for symbol in Symbol.objects.all():
        snapshot = (
            TickerSnapshot.objects.filter(symbol=symbol).order_by("-ts").first()
        )
        if not snapshot:
            logger.debug("arbitrage.snapshot.missing", extra={"symbol": symbol.name})
            continue
        if snapshot.ts < stale_cutoff:
            logger.warning(
                "arbitrage.snapshot.stale",
                extra={"symbol": symbol.name, "snapshot_ts": snapshot.ts.isoformat()},
            )
            continue

        legs = [
            (
                "TRMN->BINA",
                _net_spread(
                    snapshot.tr_ask,
                    snapshot.bi_bid,
                    settings.FEE_TRADEMN_TAKER,
                    settings.FEE_BINANCE_TAKER,
                ),
                snapshot.tr_ask,
                snapshot.bi_bid,
                settings.FEE_TRADEMN_TAKER,
                settings.FEE_BINANCE_TAKER,
            ),
            (
                "BINA->TRMN",
                _net_spread(
                    snapshot.bi_ask,
                    snapshot.tr_bid,
                    settings.FEE_BINANCE_TAKER,
                    settings.FEE_TRADEMN_TAKER,
                ),
                snapshot.bi_ask,
                snapshot.tr_bid,
                settings.FEE_BINANCE_TAKER,
                settings.FEE_TRADEMN_TAKER,
            ),
        ]

        for direction, spread, buy_price, sell_price, buy_fee, sell_fee in legs:
            if not math.isfinite(spread):
                logger.debug(
                    "arbitrage.spread.invalid",
                    extra={"symbol": symbol.name, "direction": direction},
                )
                continue
            if not _should_emit(symbol, direction, spread):
                continue

            opportunity = ArbitrageOpportunity.objects.create(
                symbol=symbol,
                direction=direction,
                net_spread_pct=spread,
                buy_price=buy_price,
                sell_price=sell_price,
                buy_fee=buy_fee,
                sell_fee=sell_fee,
            )

            payload = {
                "type": "opportunity",
                "payload": {
                    "symbol": symbol.name,
                    "dir": direction,
                    "net_pct": spread,
                    "min_net": min_net,
                    "buy": buy_price,
                    "sell": sell_price,
                    "ts": opportunity.ts.isoformat(),
                },
            }

            async_to_sync(channel_layer.group_send)(
                "tickers", {"type": "broadcast.message", "text": json.dumps(payload)}
            )

            logger.info(
                "arbitrage.opportunity",
                extra={
                    "symbol": symbol.name,
                    "direction": direction,
                    "spread": spread,
                },
            )
