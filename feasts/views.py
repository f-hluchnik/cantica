from django.shortcuts import render
from rest_framework.generics import ListAPIView
from django.views.generic import TemplateView
from .models import Feast
from songs.models import Song
from datetime import date
from .serializers import FeastSerializer
from .utils.fetch_today import LiturgyAPIClient
from django.utils.text import slugify
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


class HomePageView(TemplateView):
    template_name = "feasts/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()

        api_client = LiturgyAPIClient()
        feast_slugs = api_client.fetch_today()

        feasts = Feast.objects.filter(slug__in=feast_slugs)

        # Fetch song recommendations for each feast
        feast_songs = []
        for feast in feasts:
            specific_songs = Song.objects.filter(feast=feast)
            type_songs = Song.objects.filter(feast_types__in=feast.types.all()).distinct()
            feast_songs.append({
                "feast": feast,
                "specific_songs": specific_songs,
                "type_songs": type_songs,
            })
        # liturgical_season = self.get_liturgical_season(feasts)
        liturgical_season = 'ordinary'
        default_songs = Song.objects.filter(liturgical_season=liturgical_season)

        # Add to context
        context = {
            "date": date.today(),
            "feast_songs": feast_songs,
            "default_songs": default_songs,
        }
        return context
    
    def get_liturgical_season(self, feasts):
        """
        Infer the liturgical season from today's feasts.
        Fallback to a default season if no explicit season is found.
        """
        for feast in feasts:
            if feast.season:
                return feast.season
        return "ordinary"