from rest_framework import routers,serializers,viewsets
from .models import TradeExecution
class S(serializers.ModelSerializer):
    class Meta: model=TradeExecution; fields='__all__'
class V(viewsets.ModelViewSet): queryset=TradeExecution.objects.all(); serializer_class=S
router=routers.DefaultRouter(); router.register(r'execs',V,basename='execs')
urlpatterns=router.urls
