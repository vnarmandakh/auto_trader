from django.test import TestCase

from markets.models import Symbol
from trades.api import TradeExecutionSerializer


class TradeExecutionSerializerTests(TestCase):
    def setUp(self) -> None:
        self.symbol = Symbol.objects.create(
            name="BTCUSDT",
            base="BTC",
            quote="USDT",
            binance_symbol="BTCUSDT",
            trademn_symbol="BTCUSDT",
        )

    def test_valid_payload(self):
        serializer = TradeExecutionSerializer(
            data={
                "symbol": self.symbol.pk,
                "side": "BUY",
                "qty": 1.5,
                "price": 21000,
                "exchange": "binance",
                "order_id": "ABC123",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_rejects_non_positive_qty(self):
        serializer = TradeExecutionSerializer(
            data={
                "symbol": self.symbol.pk,
                "side": "BUY",
                "qty": 0,
                "price": 21000,
                "exchange": "binance",
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("qty", serializer.errors)

    def test_rejects_missing_exchange(self):
        serializer = TradeExecutionSerializer(
            data={
                "symbol": self.symbol.pk,
                "side": "SELL",
                "qty": 1,
                "price": 21000,
                "exchange": "",
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("exchange", serializer.errors)
