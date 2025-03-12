from django.urls import path

from .views import ConditionValueAutocomplete, SongListView

urlpatterns = [
    path('', SongListView.as_view(), name='song-list'),
    path('condition-value-autocomplete/', ConditionValueAutocomplete.as_view(), name='condition-value-autocomplete'),
]
