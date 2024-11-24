from django.urls import path
from .views import ClearCacheView, FeastListView, PreloadDataView

urlpatterns = [
    path('', FeastListView.as_view(), name='feast-list'),
    path('clear-cache', ClearCacheView.as_view(), name='clear_cache'),
    path('preload-calendar/<int:year>/', PreloadDataView.as_view(), name='preload_calendar'),
]
