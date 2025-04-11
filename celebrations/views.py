import logging
from datetime import date
from urllib.request import Request

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.http import JsonResponse
from django.views import View
from rest_framework.generics import ListAPIView

from .models import Celebration
from .serializers import CelebrationSerializer
from .utils.liturgy_api_client import LiturgyAPIClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CelebrationListView(ListAPIView):
    queryset = Celebration.objects.all()
    serializer_class = CelebrationSerializer


class ClearCacheView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs) -> JsonResponse:
        cache.clear()
        return JsonResponse(
            {'status': 'Cache cleared successfully!'},
            status=200,
        )


class PreloadDataView(LoginRequiredMixin, View):
    def get(self, request: Request, year: int, *args, **kwargs) -> JsonResponse:
        client = LiturgyAPIClient()
        for month in range(1, 13):
            try:
                client.fetch_month(year=year, month=month)
            except Exception:
                raise
        return JsonResponse(
            {'message': f'Data for {year} successfully preloaded.'},
            status=200,
        )


class PreloadMonthDataView(LoginRequiredMixin, View):
    def get(self, request: Request, year: int, month: int, *args, **kwargs) -> JsonResponse:
        client = LiturgyAPIClient()
        try:
            client.fetch_month(year=year, month=month)
        except Exception:
            raise
        return JsonResponse(
            {'message': f'Data for {year}-{month} successfully preloaded.'},
            status=200,
        )


class PreloadDayDataView(LoginRequiredMixin, View):
    def get(self, request: Request, year: int, month: int, day: int, *args, **kwargs) -> JsonResponse:
        client = LiturgyAPIClient()
        requested_day = date(year, month, day)
        try:
            client.fetch_day(day=requested_day)
        except Exception:
            raise
        return JsonResponse(
            {'message': f'Data for {year}-{month}-{day} successfully preloaded.'},
            status=200,
        )
