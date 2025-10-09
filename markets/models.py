from django.db import models
class Exchange(models.Model):
    name=models.CharField(max_length=50,unique=True)
    api_config=models.JSONField(default=dict,blank=True)
    fee_taker=models.FloatField(default=0.001)
    fee_maker=models.FloatField(default=0.001)
    def __str__(self): return self.name
class Symbol(models.Model):
    name=models.CharField(max_length=30)
    base=models.CharField(max_length=20,default='BTC')
    quote=models.CharField(max_length=20,default='USDT')
    binance_symbol=models.CharField(max_length=30,default='BTCUSDT')
    trademn_symbol=models.CharField(max_length=30,default='BTCUSDT')
    class Meta: unique_together=(('name','base','quote'),)
    def __str__(self): return self.name
