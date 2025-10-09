from django.db import models
from django.utils import timezone
from markets.models import Symbol
class TradeExecution(models.Model):
    symbol=models.ForeignKey(Symbol,on_delete=models.CASCADE)
    ts=models.DateTimeField(default=timezone.now)
    side=models.CharField(max_length=4,choices=[('BUY','BUY'),('SELL','SELL')])
    qty=models.FloatField(); price=models.FloatField(); exchange=models.CharField(max_length=16)
    order_id=models.CharField(max_length=64,blank=True,default=''); raw=models.JSONField(default=dict,blank=True)
    class Meta: ordering=['-ts']
