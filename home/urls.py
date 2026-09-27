# home/urls.py

from django.urls import path
from . import views

app_name = 'home'

urlpatterns = [
    path('', views.home_view, name='index'),
    path('parsian-prices/', views.ParsianCoinListView.as_view(), name='parsian_prices'),
    path('parsian/', views.landing_coin_view, name='parsian'),
    path('calculator/', views.calculator_view, name='calculator'),
    path('tarahe-site/', views.TaraheSiteView.as_view(), name='tarahe_site'),
    path('akase/', views.AkasSiteView.as_view(), name='akase'),
    path('subscribe/', views.email_subscribe, name='email_subscribe'),
    # API
    path('api/n8n/coins/', views.ParsianCoinPriceN8nAPIView.as_view(), name='n8n_coins'),
    path('subscribe/', views.email_subscribe, name='email_subscribe'),
]
