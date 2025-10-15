"""Automated arbitrage execution between TradeMN and Binance."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Protocol

import requests
from celery.utils.log import get_task_logger
from django.conf import settings
from django.db import transaction

from arbitrage.models import ArbitrageOpportunity
from markets.models import Symbol
from trades.models import TradeExecution


logger = get_task_logger(__name__)


class ExchangeClient(Protocol):
    """Protocol describing the methods required for execution clients."""

    name: str

    def get_balance(self, asset: str) -> float: ...

    def place_market_order(
        self, symbol: str, side: str, quantity: float, *, price: float | None = None
    ) -> Mapping[str, Any]: ...

    def withdraw(
        self, asset: str, amount: float, address: str, network: str
    ) -> Mapping[str, Any]: ...

    def wait_for_deposit(
        self,
        asset: str,
        expected_amount: float,
        *,
        timeout: float,
        poll_interval: float,
    ) -> bool: ...

    def deposit_address(self, asset: str, network: str) -> str: ...


@dataclass
class ExecutionResult:
    """Summary of an execution attempt."""

    opportunity: ArbitrageOpportunity
    quantity: float
    buy_execution: Mapping[str, Any]
    sell_execution: Mapping[str, Any]


class ExecutionError(RuntimeError):
    """Raised when arbitrage execution cannot be completed."""


class ArbitrageExecutor:
    """Executes arbitrage opportunities between TradeMN and Binance."""

    def __init__(
        self,
        trademn_client: ExchangeClient,
        binance_client: ExchangeClient,
        *,
        deposit_addresses: Optional[Mapping[str, Mapping[str, str]]] = None,
        min_notional: float | None = None,
        min_quantity: float | None = None,
        slippage_buffer: float | None = None,
        bridge_network: str | None = None,
        base_transfer_fee: float | None = None,
        quote_transfer_fee: float | None = None,
        transfer_timeout: float | None = None,
        transfer_poll_interval: float | None = None,
        rebalance_quote: bool | None = None,
    ) -> None:
        self.trademn = trademn_client
        self.binance = binance_client
        self.deposit_addresses = deposit_addresses or {}
        self.min_notional = min_notional or settings.ARBITRAGE_MIN_NOTIONAL
        self.min_quantity = min_quantity or settings.ARBITRAGE_MIN_QUANTITY
        self.slippage_buffer = slippage_buffer or settings.ARBITRAGE_SLIPPAGE_BUFFER
        self.bridge_network = bridge_network or settings.ARBITRAGE_BRIDGE_NETWORK
        self.base_transfer_fee = base_transfer_fee or settings.ARBITRAGE_BASE_TRANSFER_FEE
        self.quote_transfer_fee = quote_transfer_fee or settings.ARBITRAGE_QUOTE_TRANSFER_FEE
        self.transfer_timeout = transfer_timeout or settings.ARBITRAGE_TRANSFER_TIMEOUT
        self.transfer_poll_interval = (
            transfer_poll_interval or settings.ARBITRAGE_TRANSFER_POLL_INTERVAL
        )
        self.rebalance_quote = (
            settings.ARBITRAGE_REBALANCE_QUOTE if rebalance_quote is None else rebalance_quote
        )

    def execute_once(self) -> int:
        """Execute against the freshest opportunities and return count processed."""

        opportunities = (
            ArbitrageOpportunity.objects.select_related("symbol")
            .filter(net_spread_pct__gte=settings.ARBITRAGE_MIN_NET_SPREAD)
            .order_by("-ts")
        )
        processed_symbols: set[int] = set()
        executed = 0

        for opportunity in opportunities:
            if opportunity.symbol_id in processed_symbols:
                continue
            try:
                result = self._execute_opportunity(opportunity)
            except ExecutionError as exc:
                logger.warning(
                    "arbitrage.execution.failed",
                    extra={"symbol": opportunity.symbol.name, "error": str(exc)},
                )
                processed_symbols.add(opportunity.symbol_id)
                continue
            except Exception:
                logger.exception(
                    "arbitrage.execution.unexpected", extra={"symbol": opportunity.symbol.name}
                )
                processed_symbols.add(opportunity.symbol_id)
                continue

            processed_symbols.add(opportunity.symbol_id)
            if result:
                executed += 1
        return executed

    def _execute_opportunity(self, opportunity: ArbitrageOpportunity) -> ExecutionResult | None:
        symbol = opportunity.symbol
        quantity = max(self.min_quantity, self.min_notional / max(opportunity.buy_price, 1e-12))

        if opportunity.direction == "TRMN->BINA":
            buy_client = self.trademn
            sell_client = self.binance
            buy_symbol = symbol.trademn_symbol
            sell_symbol = symbol.binance_symbol
        elif opportunity.direction == "BINA->TRMN":
            buy_client = self.binance
            sell_client = self.trademn
            buy_symbol = symbol.binance_symbol
            sell_symbol = symbol.trademn_symbol
        else:
            raise ExecutionError(f"Unsupported direction: {opportunity.direction}")

        quote_asset = symbol.quote
        base_asset = symbol.base

        quote_required = quantity * opportunity.buy_price * (
            1 + opportunity.buy_fee + self.slippage_buffer
        )
        available_quote = buy_client.get_balance(quote_asset)
        if available_quote < quote_required:
            raise ExecutionError(
                f"Insufficient {quote_asset} balance on {buy_client.name}: "
                f"need {quote_required}, have {available_quote}"
            )

        logger.info(
            "arbitrage.execution.start",
            extra={
                "symbol": symbol.name,
                "direction": opportunity.direction,
                "quantity": quantity,
                "buy_price": opportunity.buy_price,
                "sell_price": opportunity.sell_price,
            },
        )

        buy_execution = buy_client.place_market_order(
            buy_symbol,
            "BUY",
            quantity,
            price=opportunity.buy_price * (1 + self.slippage_buffer),
        )
        self._record_trade(
            symbol,
            "BUY",
            quantity,
            float(buy_execution.get("avgPrice", opportunity.buy_price)),
            buy_client,
            buy_execution,
        )

        transfer_amount = max(quantity - self.base_transfer_fee, 0)
        if transfer_amount <= 0:
            raise ExecutionError("Transfer amount non-positive after fees")

        destination_address = self._resolve_deposit_address(sell_client, base_asset)
        buy_client.withdraw(
            base_asset,
            transfer_amount,
            destination_address,
            self.bridge_network,
        )

        if not sell_client.wait_for_deposit(
            base_asset,
            transfer_amount,
            timeout=self.transfer_timeout,
            poll_interval=self.transfer_poll_interval,
        ):
            raise ExecutionError("Timed out waiting for bridged funds")

        sell_execution = sell_client.place_market_order(
            sell_symbol,
            "SELL",
            quantity,
            price=opportunity.sell_price * (1 - self.slippage_buffer),
        )
        self._record_trade(
            symbol,
            "SELL",
            quantity,
            float(sell_execution.get("avgPrice", opportunity.sell_price)),
            sell_client,
            sell_execution,
        )

        if self.rebalance_quote:
            self._rebalance_quote(
                source=sell_client,
                destination=buy_client,
                symbol=symbol,
                quantity=quantity,
                sell_execution=sell_execution,
                opportunity=opportunity,
            )

        logger.info(
            "arbitrage.execution.complete",
            extra={"symbol": symbol.name, "direction": opportunity.direction},
        )
        return ExecutionResult(opportunity, quantity, buy_execution, sell_execution)

    def _rebalance_quote(
        self,
        *,
        source: ExchangeClient,
        destination: ExchangeClient,
        symbol: Symbol,
        quantity: float,
        sell_execution: Mapping[str, Any],
        opportunity: ArbitrageOpportunity,
    ) -> None:
        quote_asset = symbol.quote
        gross_proceeds = quantity * float(
            sell_execution.get("avgPrice", opportunity.sell_price)
        )
        net_proceeds = gross_proceeds * (1 - opportunity.sell_fee) - self.quote_transfer_fee
        if net_proceeds <= 0:
            logger.warning(
                "arbitrage.rebalance.skipped",
                extra={"symbol": symbol.name, "reason": "non-positive proceeds"},
            )
            return

        destination_address = self._resolve_deposit_address(destination, quote_asset)
        source.withdraw(
            quote_asset,
            net_proceeds,
            destination_address,
            self.bridge_network,
        )

        destination.wait_for_deposit(
            quote_asset,
            net_proceeds,
            timeout=self.transfer_timeout,
            poll_interval=self.transfer_poll_interval,
        )

        logger.info(
            "arbitrage.rebalance.complete",
            extra={"symbol": symbol.name, "amount": net_proceeds},
        )

    def _resolve_deposit_address(self, client: ExchangeClient, asset: str) -> str:
        key = f"{asset}:{self.bridge_network}"
        client_addresses = self.deposit_addresses.get(client.name.lower(), {})
        if key in client_addresses:
            return client_addresses[key]
        address = client.deposit_address(asset, self.bridge_network)
        if not address:
            raise ExecutionError(
                f"Unable to resolve deposit address for {client.name} {key}"
            )
        return address

    def _record_trade(
        self,
        symbol: Symbol,
        side: str,
        quantity: float,
        price: float,
        client: ExchangeClient,
        execution_payload: Mapping[str, Any],
    ) -> TradeExecution:
        with transaction.atomic():
            trade = TradeExecution.objects.create(
                symbol=symbol,
                side=side,
                qty=quantity,
                price=price,
                exchange=client.name,
                order_id=str(
                    execution_payload.get("orderId")
                    or execution_payload.get("id")
                    or execution_payload.get("clientOrderId")
                    or execution_payload.get("order_id")
                    or ""
                ),
                raw=json.loads(json.dumps(execution_payload)),
            )
        return trade


class BinanceRESTClient:
    """Minimal Binance REST client for market orders and transfers."""

    name = "binance"

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        *,
        base_url: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret.encode()
        self.base_url = base_url or settings.BINANCE_API_BASE_URL
        self.session = session or requests.Session()

    def get_balance(self, asset: str) -> float:
        data = self._signed_request("GET", "/api/v3/account", {})
        for balance in data.get("balances", []):
            if balance.get("asset") == asset:
                return float(balance.get("free", 0))
        return 0.0

    def place_market_order(
        self, symbol: str, side: str, quantity: float, *, price: float | None = None
    ) -> Mapping[str, Any]:
        payload = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": f"{quantity:.8f}",
        }
        if price:
            payload["newOrderRespType"] = "FULL"
        return self._signed_request("POST", "/api/v3/order", payload)

    def withdraw(self, asset: str, amount: float, address: str, network: str) -> Mapping[str, Any]:
        payload = {
            "coin": asset,
            "amount": f"{amount:.8f}",
            "address": address,
            "network": network,
        }
        return self._signed_request(
            "POST", "/sapi/v1/capital/withdraw/apply", payload
        )

    def wait_for_deposit(
        self,
        asset: str,
        expected_amount: float,
        *,
        timeout: float,
        poll_interval: float,
    ) -> bool:
        start = time.time()
        baseline = self.get_balance(asset)
        while time.time() - start < timeout:
            current = self.get_balance(asset)
            if current >= baseline + expected_amount - 1e-8:
                return True
            time.sleep(poll_interval)
        return False

    def deposit_address(self, asset: str, network: str) -> str:
        payload = {"coin": asset, "network": network}
        data = self._signed_request(
            "GET", "/sapi/v1/capital/deposit/address", payload
        )
        return data.get("address", "")

    def _signed_request(self, method: str, path: str, params: Dict[str, Any]) -> Mapping[str, Any]:
        timestamp = int(time.time() * 1000)
        params = {**params, "timestamp": timestamp}
        query = self._encode(params)
        signature = self._sign(query)
        query = f"{query}&signature={signature}"
        headers = {"X-MBX-APIKEY": self.api_key}
        url = f"{self.base_url}{path}"
        timeout = settings.DATAFEED_HTTP_TIMEOUT
        if method == "GET":
            response = self.session.get(
                f"{url}?{query}", headers=headers, timeout=timeout
            )
        elif method == "POST":
            response = self.session.post(
                url, headers=headers, data=query, timeout=timeout
            )
        else:
            raise ValueError(f"Unsupported method: {method}")
        response.raise_for_status()
        return response.json()

    def _sign(self, payload: str) -> str:
        import hashlib
        import hmac

        return hmac.new(self.api_secret, payload.encode(), hashlib.sha256).hexdigest()

    def _encode(self, params: Dict[str, Any]) -> str:
        from urllib.parse import urlencode

        return urlencode(params, doseq=True)


class TradeMNRESTClient:
    """REST client for the TradeMN exchange."""

    name = "trademn"

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        *,
        base_url: str | None = None,
        order_path: str | None = None,
        balance_path: str | None = None,
        withdraw_path: str | None = None,
        deposit_path: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret.encode()
        self.base_url = base_url or settings.TRADEMN_API_BASE_URL
        self.order_path = order_path or settings.TRADEMN_API_ORDER_PATH
        self.balance_path = balance_path or settings.TRADEMN_API_BALANCE_PATH
        self.withdraw_path = withdraw_path or settings.TRADEMN_API_WITHDRAW_PATH
        self.deposit_path = deposit_path or settings.TRADEMN_API_DEPOSIT_PATH
        self.session = session or requests.Session()

    def get_balance(self, asset: str) -> float:
        data = self._private_request("GET", self.balance_path, None)
        balances = data.get("balances") or data
        if isinstance(balances, dict):
            value = balances.get(asset) or {}
            if isinstance(value, dict):
                return float(
                    value.get("available")
                    or value.get("free")
                    or value.get("balance")
                    or 0
                )
            return float(value or 0)
        if isinstance(balances, list):
            for entry in balances:
                if entry.get("asset") == asset or entry.get("currency") == asset:
                    return float(entry.get("available") or entry.get("balance") or 0)
        return 0.0

    def place_market_order(
        self, symbol: str, side: str, quantity: float, *, price: float | None = None
    ) -> Mapping[str, Any]:
        payload: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": "market",
            "quantity": quantity,
        }
        if price is not None:
            payload["price"] = price
        return self._private_request("POST", self.order_path, payload)

    def withdraw(self, asset: str, amount: float, address: str, network: str) -> Mapping[str, Any]:
        payload = {
            "asset": asset,
            "amount": amount,
            "address": address,
            "network": network,
        }
        return self._private_request("POST", self.withdraw_path, payload)

    def wait_for_deposit(
        self,
        asset: str,
        expected_amount: float,
        *,
        timeout: float,
        poll_interval: float,
    ) -> bool:
        start = time.time()
        baseline = self.get_balance(asset)
        while time.time() - start < timeout:
            current = self.get_balance(asset)
            if current >= baseline + expected_amount - 1e-8:
                return True
            time.sleep(poll_interval)
        return False

    def deposit_address(self, asset: str, network: str) -> str:
        params = {"asset": asset, "network": network}
        data = self._private_request("GET", self.deposit_path, params)
        if isinstance(data, dict):
            return data.get("address") or data.get("depositAddress") or ""
        return ""

    def _private_request(
        self, method: str, path: str, payload: Optional[Dict[str, Any]]
    ) -> Mapping[str, Any]:
        body = json.dumps(payload or {}, separators=(",", ":")) if payload else ""
        timestamp = str(int(time.time() * 1000))
        message = f"{timestamp}{method.upper()}{path}{body}"
        signature = self._sign(message)
        headers = {
            "X-API-KEY": self.api_key,
            "X-API-TIMESTAMP": timestamp,
            "X-API-SIGNATURE": signature,
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}{path}"
        timeout = settings.DATAFEED_HTTP_TIMEOUT
        if method == "GET":
            params = payload or {}
            response = self.session.get(
                url, params=params, headers=headers, timeout=timeout
            )
        elif method == "POST":
            response = self.session.post(
                url, data=body, headers=headers, timeout=timeout
            )
        else:
            raise ValueError(f"Unsupported method: {method}")
        response.raise_for_status()
        return response.json()

    def _sign(self, payload: str) -> str:
        import hashlib
        import hmac

        return hmac.new(self.api_secret, payload.encode(), hashlib.sha256).hexdigest()


__all__ = [
    "ArbitrageExecutor",
    "BinanceRESTClient",
    "ExecutionError",
    "ExecutionResult",
    "TradeMNRESTClient",
]

