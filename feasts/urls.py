from django.urls import path
from .views import ClearCacheView, FeastListView, HomePageView

urlpatterns = [
    path('', FeastListView.as_view(), name='feast-list'),
    path('home', HomePageView.as_view(), name='homepage'),
    path('clear-cache', ClearCacheView.as_view(), name='clear_cache'),
]
