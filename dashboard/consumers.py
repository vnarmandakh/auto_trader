from channels.generic.websocket import AsyncWebsocketConsumer
class TickerConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add('tickers', self.channel_name); await self.accept()
    async def disconnect(self, code):
        await self.channel_layer.group_discard('tickers', self.channel_name)
    async def receive(self, text_data=None, bytes_data=None): pass
    async def broadcast_message(self, event): await self.send(text_data=event['text'])
