from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import filters as drf_filters, permissions, routers, serializers, viewsets

from .models import TradeExecution


class TradeExecutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradeExecution
        fields = "__all__"

    def validate_qty(self, value: float) -> float:
        if value <= 0:
            raise serializers.ValidationError("Quantity must be positive")
        return value

    def validate_price(self, value: float) -> float:
        if value <= 0:
            raise serializers.ValidationError("Price must be positive")
        return value

    def validate_exchange(self, value: str) -> str:
        if not value:
            raise serializers.ValidationError("Exchange is required")
        return value


class TradeExecutionViewSet(viewsets.ModelViewSet):
    queryset = TradeExecution.objects.select_related("symbol")
    serializer_class = TradeExecutionSerializer
    filter_backends = [drf_filters.OrderingFilter, drf_filters.SearchFilter]
    search_fields = ["symbol__name", "order_id", "exchange"]
    ordering_fields = ["ts", "qty", "price", "symbol__name"]
    ordering = ["-ts"]
    throttle_scope = "trades"

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        symbol = params.get("symbol")
        if symbol:
            queryset = queryset.filter(symbol__name__iexact=symbol)
        side = params.get("side")
        if side:
            queryset = queryset.filter(side__iexact=side)
        exchange = params.get("exchange")
        if exchange:
            queryset = queryset.filter(exchange__iexact=exchange)
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

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.IsAuthenticatedOrReadOnly()]
        return [permissions.IsAdminUser()]


router = routers.DefaultRouter()
router.register(r"execs", TradeExecutionViewSet, basename="execs")
urlpatterns = router.urls
