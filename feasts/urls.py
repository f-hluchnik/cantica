from django.urls import path
from .views import FeastListView, HomePageView

urlpatterns = [
    path('', FeastListView.as_view(), name='feast-list'),
    path('home', HomePageView.as_view(), name='homepage'),
]
