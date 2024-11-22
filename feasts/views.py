from django.shortcuts import render
from rest_framework.generics import ListAPIView
from django.views.generic import TemplateView
from .models import Feast
from songs.models import Song
from datetime import date
from .serializers import FeastSerializer
from .services.fetch_today import Command

class FeastListView(ListAPIView):
    queryset = Feast.objects.all()
    serializer_class = FeastSerializer

class HomePageView(TemplateView):
    template_name = "feasts/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()

        if not Feast.objects.filter(date=today).exists():
            # Fetch feasts automatically if not present
            cmd = Command()
            cmd.handle()

        # Fetch today's feasts
        feasts = Feast.objects.filter(date=today)

        # Fetch song recommendations for each feast
        feast_songs = []
        for feast in feasts:
            songs = Song.objects.filter(feast_types__in=feast.types.all()).distinct()
            feast_songs.append({
                "feast": feast,
                "songs": songs
            })

        # Add to context
        context["date"] = today
        context["feast_songs"] = feast_songs
        return context