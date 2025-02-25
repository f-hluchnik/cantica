from django.http import JsonResponse
from django.core.cache import cache
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin

from datetime import date
from rest_framework.generics import ListAPIView
from .models import Celebration
from .utils.liturgy_api_client import LiturgyAPIClient
from .serializers import CelebrationSerializer
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CelebrationListView(ListAPIView):
    queryset = Celebration.objects.all()
    serializer_class = CelebrationSerializer


class ClearCacheView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        cache.clear()
        return JsonResponse(
            {"status": "Cache cleared successfully!"},
            status=200
        )


class PreloadDataView(LoginRequiredMixin, View):
    def get(self, request, year, *args, **kwargs):
        client = LiturgyAPIClient()
        for month in range(1, 13):
            try:
                client.fetch_month(year=year, month=month)
            except Exception:
                raise
        return JsonResponse(
            {"message": f"Data for {year} successfully preloaded."},
            status=200
        )


class PreloadMonthDataView(LoginRequiredMixin, View):
    def get(self, request, year, month, *args, **kwargs):
        client = LiturgyAPIClient()
        try:
            client.fetch_month(year=year, month=month)
        except Exception:
            raise
        return JsonResponse(
            {"message": f"Data for {year}-{month} successfully preloaded."},
            status=200
        )


class PreloadDayDataView(LoginRequiredMixin, View):
    def get(self, request, year, month, day, *args, **kwargs):
        client = LiturgyAPIClient()
        requested_day = date(year, month, day)
        try:
            client.fetch_day(day=requested_day)
        except Exception:
            raise
        return JsonResponse(
            {"message": f"Data for {year}-{month}-{day} successfully preloaded."},
            status=200
        )
