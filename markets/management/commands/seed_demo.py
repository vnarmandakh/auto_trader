from django.core.management.base import BaseCommand
from django.conf import settings
from markets.models import Exchange, Symbol
class Command(BaseCommand):
    def handle(self,*args,**kwargs):
        Exchange.objects.get_or_create(name='BINANCE',defaults={'fee_taker':settings.FEE_BINANCE_TAKER,'fee_maker':settings.FEE_BINANCE_MAKER,'api_config':{'book_ticker':settings.BINANCE_BOOK_TICKER_URL}})
        Exchange.objects.get_or_create(name='TRADEMN',defaults={'fee_taker':settings.FEE_TRADEMN_TAKER,'fee_maker':settings.FEE_TRADEMN_MAKER,'api_config':{'book_ticker':settings.TRADEMN_BOOK_TICKER_URL,'orderbook':settings.TRADEMN_ORDERBOOK_URL}})
        Symbol.objects.get_or_create(name='BTCUSDT',base='BTC',quote='USDT',binance_symbol='BTCUSDT',trademn_symbol='BTCUSDT')
        self.stdout.write(self.style.SUCCESS('Seeded demo data'))
