import requests, json
from django.conf import settings
from celery import shared_task
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from markets.models import Symbol
from .models import TickerSnapshot

def http_get(url, timeout=8):
    r = requests.get(url, timeout=timeout); r.raise_for_status(); return r.json()

def binance(sym):
    d=http_get(settings.BINANCE_BOOK_TICKER_URL.format(symbol=sym))
    return float(d["bidPrice"]), float(d["askPrice"])

def trademn(sym):
    if settings.TRADEMN_BOOK_TICKER_URL:
        d=http_get(settings.TRADEMN_BOOK_TICKER_URL.format(symbol=sym))
        bid=float(d.get("bidPrice") or d.get("bestBid") or d["bid"][0]); ask=float(d.get("askPrice") or d.get("bestAsk") or d["ask"][0]); return bid, ask
    d=http_get(settings.TRADEMN_ORDERBOOK_URL.format(symbol=sym))
    asks=d.get(settings.TRADEMN_ORDERBOOK_ASK_KEY,[]); bids=d.get(settings.TRADEMN_ORDERBOOK_BID_KEY,[])
    ia=settings.TRADEMN_PRICE_INDEX_ASK; ib=settings.TRADEMN_PRICE_INDEX_BID
    best_ask=float(asks[0][ia]) if asks else float('inf'); best_bid=float(bids[0][ib]) if bids else 0.0
    return best_bid, best_ask

@shared_task
def poll_all_symbols():
    ch=get_channel_layer()
    for s in Symbol.objects.all():
        b_bid,b_ask=binance(s.binance_symbol); t_bid,t_ask=trademn(s.trademn_symbol)
        snap=TickerSnapshot.objects.create(symbol=s,bi_bid=b_bid,bi_ask=b_ask,tr_bid=t_bid,tr_ask=t_ask)
        payload={"type":"ticker","payload":{"symbol":s.name,"bi_bid":b_bid,"bi_ask":b_ask,"tr_bid":t_bid,"tr_ask":t_ask,"ts":snap.ts.isoformat()}}
        async_to_sync(ch.group_send)("tickers",{"type":"broadcast.message","text":json.dumps(payload)})
