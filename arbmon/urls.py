from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
urlpatterns=[path('admin/',admin.site.urls),path('api/',include('markets.api_urls')),path('api/',include('datafeed.api_urls')),path('api/',include('arbitrage.api_urls')),path('api/',include('trades.api_urls')),path('',TemplateView.as_view(template_name='dashboard.html'))]
