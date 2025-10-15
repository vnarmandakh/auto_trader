from __future__ import annotations

from django.test import TestCase

from arbitrage.models import ArbitrageOpportunity
from markets.models import Symbol
from trades.execution import ArbitrageExecutor
from trades.models import TradeExecution


class DummyClient:
    def __init__(self, name: str, balances: dict[str, float], deposit_map: dict[tuple[str, str], str]):
        self.name = name
        self._balances = balances
        self._deposit_map = deposit_map
        self.orders: list[dict[str, object]] = []
        self.withdrawals: list[dict[str, object]] = []
        self.wait_requests: list[dict[str, object]] = []

    def get_balance(self, asset: str) -> float:
        return self._balances.get(asset, 0.0)

    def place_market_order(
        self, symbol: str, side: str, quantity: float, *, price: float | None = None
    ):
        payload = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "avgPrice": price or 0,
        }
        self.orders.append(payload)
        return {"orderId": f"{self.name}-{len(self.orders)}", **payload}

    def withdraw(self, asset: str, amount: float, address: str, network: str):
        self.withdrawals.append(
            {"asset": asset, "amount": amount, "address": address, "network": network}
        )
        return {"id": f"{self.name}-wd-{len(self.withdrawals)}"}

    def wait_for_deposit(
        self,
        asset: str,
        expected_amount: float,
        *,
        timeout: float,
        poll_interval: float,
    ) -> bool:
        self.wait_requests.append(
            {"asset": asset, "amount": expected_amount, "timeout": timeout}
        )
        self._balances[asset] = self._balances.get(asset, 0.0) + expected_amount
        return True

    def deposit_address(self, asset: str, network: str) -> str:
        return self._deposit_map.get((asset, network), f"{self.name}-{asset}-{network}")


class ArbitrageExecutorTests(TestCase):
    def setUp(self) -> None:
        self.symbol = Symbol.objects.create(
            name="BTCUSDT",
            base="BTC",
            quote="USDT",
            binance_symbol="BTCUSDT",
            trademn_symbol="BTCUSDT",
        )
        deposit_addresses = {
            "binance": {"BTC:TRX": "bin-btc-trx", "USDT:TRX": "bin-usdt-trx"},
            "trademn": {"BTC:TRX": "tm-btc-trx", "USDT:TRX": "tm-usdt-trx"},
        }
        self.trademn = DummyClient(
            "trademn", {"USDT": 10_000.0, "BTC": 0.0}, {("BTC", "TRX"): "tm-btc-trx"}
        )
        self.binance = DummyClient(
            "binance", {"USDT": 10_000.0, "BTC": 1.0}, {("USDT", "TRX"): "bin-usdt-trx"}
        )
        self.executor = ArbitrageExecutor(
            self.trademn,
            self.binance,
            deposit_addresses=deposit_addresses,
            min_notional=100.0,
            min_quantity=0.01,
            quote_transfer_fee=0.5,
            base_transfer_fee=0.0,
            rebalance_quote=True,
        )

    def test_execute_trademn_to_binance_cycle(self):
        ArbitrageOpportunity.objects.create(
            symbol=self.symbol,
            direction="TRMN->BINA",
            net_spread_pct=0.02,
            buy_price=10000.0,
            sell_price=10250.0,
            buy_fee=0.0015,
            sell_fee=0.001,
        )

        executed = self.executor.execute_once()

        self.assertEqual(executed, 1)
        self.assertEqual(len(self.trademn.orders), 1)
        self.assertEqual(len(self.binance.orders), 1)
        self.assertEqual(len(self.trademn.withdrawals), 1)
        self.assertEqual(len(self.binance.withdrawals), 1)
        trades = TradeExecution.objects.filter(symbol=self.symbol).order_by("ts")
        self.assertEqual(trades.count(), 2)
        self.assertEqual(trades.first().side, "BUY")
        self.assertEqual(trades.last().side, "SELL")

    def test_execute_binance_to_trademn_cycle(self):
        ArbitrageOpportunity.objects.create(
            symbol=self.symbol,
            direction="BINA->TRMN",
            net_spread_pct=0.015,
            buy_price=10050.0,
            sell_price=10180.0,
            buy_fee=0.001,
            sell_fee=0.0015,
        )

        executed = self.executor.execute_once()

        self.assertEqual(executed, 1)
        self.assertEqual(self.trademn.orders[0]["side"], "SELL")
        self.assertEqual(self.binance.orders[0]["side"], "BUY")
        self.assertEqual(len(TradeExecution.objects.all()), 2)

    def test_skip_when_balance_insufficient(self):
        self.trademn._balances["USDT"] = 10.0
        ArbitrageOpportunity.objects.create(
            symbol=self.symbol,
            direction="TRMN->BINA",
            net_spread_pct=0.02,
            buy_price=10000.0,
            sell_price=10250.0,
            buy_fee=0.0015,
            sell_fee=0.001,
        )

        executed = self.executor.execute_once()

        self.assertEqual(executed, 0)
        self.assertEqual(TradeExecution.objects.count(), 0)
