from rest_framework import routers,serializers,viewsets
from .models import Exchange, Symbol
class ExS(serializers.ModelSerializer):
    class Meta: model=Exchange; fields='__all__'
class SyS(serializers.ModelSerializer):
    class Meta: model=Symbol; fields='__all__'
class ExV(viewsets.ModelViewSet): queryset=Exchange.objects.all(); serializer_class=ExS
class SyV(viewsets.ModelViewSet): queryset=Symbol.objects.all(); serializer_class=SyS
router=routers.DefaultRouter(); router.register(r'exchanges',ExV); router.register(r'symbols',SyV)
urlpatterns=router.urls
