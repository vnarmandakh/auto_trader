from django.db import models
from django.utils import timezone
from markets.models import Symbol
class ArbitrageOpportunity(models.Model):
    symbol=models.ForeignKey(Symbol,on_delete=models.CASCADE)
    ts=models.DateTimeField(default=timezone.now)
    direction=models.CharField(max_length=32)
    net_spread_pct=models.FloatField()
    buy_price=models.FloatField(); sell_price=models.FloatField()
    buy_fee=models.FloatField(); sell_fee=models.FloatField()
    class Meta: indexes=[models.Index(fields=['symbol','ts'])]; ordering=['-ts']
