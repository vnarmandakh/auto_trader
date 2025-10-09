from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import filters as drf_filters, routers, serializers, viewsets

from .models import ArbitrageOpportunity


class ArbitrageOpportunitySerializer(serializers.ModelSerializer):
    class Meta:
        model = ArbitrageOpportunity
        fields = "__all__"


class ArbitrageOpportunityViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ArbitrageOpportunity.objects.select_related("symbol")
    serializer_class = ArbitrageOpportunitySerializer
    filter_backends = [drf_filters.OrderingFilter, drf_filters.SearchFilter]
    search_fields = ["symbol__name", "direction"]
    ordering_fields = ["ts", "net_spread_pct", "symbol__name"]
    ordering = ["-ts"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        symbol = params.get("symbol")
        if symbol:
            queryset = queryset.filter(symbol__name__iexact=symbol)
        direction = params.get("direction")
        if direction:
            queryset = queryset.filter(direction__iexact=direction)
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
router.register(r"opps", ArbitrageOpportunityViewSet, basename="opps")
urlpatterns = router.urls
