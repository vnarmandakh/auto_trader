from rest_framework import routers,serializers,viewsets
from .models import ArbitrageOpportunity
class S(serializers.ModelSerializer):
    class Meta: model=ArbitrageOpportunity; fields='__all__'
class V(viewsets.ReadOnlyModelViewSet): queryset=ArbitrageOpportunity.objects.all(); serializer_class=S
router=routers.DefaultRouter(); router.register(r'opps',V,basename='opps')
urlpatterns=router.urls
