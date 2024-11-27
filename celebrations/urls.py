from django.urls import path
from .views import ClearCacheView, CelebrationListView, PreloadDataView, PreloadMonthDataView

urlpatterns = [
    path('', CelebrationListView.as_view(), name='celebration_list'),
    path('clear-cache', ClearCacheView.as_view(), name='clear_cache'),
    path('preload-calendar/<int:year>/', PreloadDataView.as_view(), name='preload_calendar'),
    path('preload-calendar/<int:year>/<int:month>', PreloadMonthDataView.as_view(), name='preload_calendar'),
]
