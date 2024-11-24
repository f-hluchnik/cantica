
from rest_framework.generics import ListAPIView
from .models import Feast
from .utils.liturgy_api_client import LiturgyAPIClient
from .serializers import FeastSerializer
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from django.http import JsonResponse
from django.core.cache import cache
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin

class FeastListView(ListAPIView):
    queryset = Feast.objects.all()
    serializer_class = FeastSerializer

class ClearCacheView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        # Clear the cache
        cache.clear()
        return JsonResponse({"status": "Cache cleared successfully!"}, status=200)
    
class PreloadDataView(LoginRequiredMixin, View):
    def get(self, request, year, *args, **kwargs):
        client = LiturgyAPIClient()
        for month in range(1, 13):
            try:
                client.fetch_month(year=year, month=month)
            except Exception:
                raise
        return JsonResponse({"message": f"Data for {year} successfully preloaded."}, status=200)

