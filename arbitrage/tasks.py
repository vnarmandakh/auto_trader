from celery import shared_task
from django.conf import settings
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from datafeed.models import TickerSnapshot
from markets.models import Symbol
from .models import ArbitrageOpportunity
import json

def net(buy,sell,bf,sf): return (sell*(1-sf) - buy*(1+bf)) / (buy*(1+bf))

@shared_task
def scan_spreads():
    ch=get_channel_layer(); min_net=settings.ARBITRAGE_MIN_NET_SPREAD
    for s in Symbol.objects.all():
        last=TickerSnapshot.objects.filter(symbol=s).order_by("-ts").first()
        if not last: continue
        net1=net(last.tr_ask,last.bi_bid,settings.FEE_TRADEMN_TAKER,settings.FEE_BINANCE_TAKER)
        net2=net(last.bi_ask,last.tr_bid,settings.FEE_BINANCE_TAKER,settings.FEE_TRADEMN_TAKER)
        for name, val, buy, sell, bf, sf in [("TRMN->BINA",net1,last.tr_ask,last.bi_bid,settings.FEE_TRADEMN_TAKER,settings.FEE_BINANCE_TAKER),("BINA->TRMN",net2,last.bi_ask,last.tr_bid,settings.FEE_BINANCE_TAKER,settings.FEE_TRADEMN_TAKER)]:
            ArbitrageOpportunity.objects.create(symbol=s,direction=name,net_spread_pct=val,buy_price=buy,sell_price=sell,buy_fee=bf,sell_fee=sf)
            payload={"type":"opportunity","payload":{"symbol":s.name,"dir":name,"net_pct":val,"min_net":min_net,"buy":buy,"sell":sell}}
            async_to_sync(ch.group_send)("tickers",{"type":"broadcast.message","text":json.dumps(payload)})
