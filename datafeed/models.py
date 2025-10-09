from django.db import models
from django.utils import timezone
from markets.models import Symbol
class TickerSnapshot(models.Model):
    symbol=models.ForeignKey(Symbol,on_delete=models.CASCADE)
    ts=models.DateTimeField(default=timezone.now)
    bi_bid=models.FloatField(); bi_ask=models.FloatField(); tr_bid=models.FloatField(); tr_ask=models.FloatField()
    class Meta:
        indexes=[models.Index(fields=['symbol','ts'])]
        ordering=['-ts']
