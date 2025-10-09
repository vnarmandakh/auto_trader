from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import filters as drf_filters, routers, serializers, viewsets

from .models import TickerSnapshot


class TickerSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TickerSnapshot
        fields = "__all__"


class TickerSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TickerSnapshot.objects.select_related("symbol")
    serializer_class = TickerSnapshotSerializer
    filter_backends = [drf_filters.OrderingFilter, drf_filters.SearchFilter]
    search_fields = ["symbol__name"]
    ordering_fields = ["ts", "bi_bid", "bi_ask", "tr_bid", "tr_ask"]
    ordering = ["-ts"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        symbol = params.get("symbol")
        if symbol:
            queryset = queryset.filter(symbol__name__iexact=symbol)
        since = self._parse_datetime(params.get("since"))
        if since:
            queryset = queryset.filter(ts__gte=since)
        until = self._parse_datetime(params.get("until"))
        if until:
            queryset = queryset.filter(ts__lte=until)
        return queryset

    def _parse_datetime(self, value: str | None):
        if not value:
            return None
        parsed = parse_datetime(value)
        if not parsed:
            return None
        if timezone.is_naive(parsed) and timezone.is_aware(timezone.now()):
            return timezone.make_aware(parsed)
        return parsed


router = routers.DefaultRouter()
router.register(r"tickers", TickerSnapshotViewSet, basename="tickers")
urlpatterns = router.urls
