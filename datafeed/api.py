from rest_framework import routers,serializers,viewsets
from .models import TickerSnapshot
class S(serializers.ModelSerializer):
    class Meta: model=TickerSnapshot; fields='__all__'
class V(viewsets.ReadOnlyModelViewSet): queryset=TickerSnapshot.objects.all(); serializer_class=S
router=routers.DefaultRouter(); router.register(r'tickers',V,basename='tickers')
urlpatterns=router.urls
