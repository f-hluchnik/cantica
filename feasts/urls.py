from django.urls import path
from .views import ClearCacheView, FeastListView

urlpatterns = [
    path('', FeastListView.as_view(), name='feast-list'),
    path('clear-cache', ClearCacheView.as_view(), name='clear_cache'),
]
