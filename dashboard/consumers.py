from __future__ import annotations

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.core.cache import cache


class TickerConsumer(AsyncWebsocketConsumer):
    """Authenticated WebSocket consumer with lightweight rate limiting."""

    rate_limit = getattr(settings, "WEBSOCKET_MAX_CONNECTIONS_PER_USER", 20)
    rate_window = getattr(settings, "WEBSOCKET_CONNECTION_WINDOW_SEC", 60)

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4003)
            return

        allowed = await sync_to_async(self._check_rate_limit)(user.pk)
        if not allowed:
            await self.close(code=4408)  # policy violation
            return

        await self.channel_layer.group_add("tickers", self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard("tickers", self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Read-only channel – clients should not send payloads.
        return None

    async def broadcast_message(self, event):
        await self.send(text_data=event["text"])

    def _check_rate_limit(self, user_pk: int) -> bool:
        key = f"ws:ticker:{user_pk}"
        if cache.add(key, 0, timeout=self.rate_window):
            pass
        try:
            current = cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=self.rate_window)
            current = 1
        return current <= self.rate_limit
