from django.urls import path
from .views import FeastListView

urlpatterns = [
    path('', FeastListView.as_view(), name='feast-list'),
]
