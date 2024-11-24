from django.views.generic import TemplateView
from feasts.utils.fetch_today import LiturgyAPIClient
from datetime import date, datetime, timedelta
from feasts.models import Feast
from songs.models import Song

class HomePageView(TemplateView):
    template_name = "home/homepage.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = datetime.now()
        date_str = self.request.GET.get('date', datetime.now().strftime('%Y-%m-%d'))
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            selected_date = datetime.now().strftime('%Y-%m-%d')

        api_client = LiturgyAPIClient()
        feast_slugs = api_client.fetch_today(day=selected_date)

        feasts = Feast.objects.filter(slug__in=feast_slugs)

        # Fetch song recommendations for each feast
        feast_songs = []
        for feast in feasts:
            specific_songs = Song.objects.filter(feast=feast)
            type_songs = Song.objects.filter(feast_types__in=feast.types.all()).distinct()
            is_jesus_christ_feast = "jesus christ" in [ft.name for ft in feast.types.all()]
            is_virgin_mary_feast = "virgin mary" in [ft.name for ft in feast.types.all()]
            feast_songs.append({
                "feast": feast,
                "specific_songs": specific_songs,
                "type_songs": type_songs,
                "is_jesus_christ_feast": is_jesus_christ_feast,
                "is_virgin_mary_feast": is_virgin_mary_feast,
            })
        # liturgical_season = self.get_liturgical_season(feasts)
        liturgical_season = 'ordinary'
        default_songs = Song.objects.filter(liturgical_season=liturgical_season)

        # Add to context
        context = {
            "feast_songs": feast_songs,
            "default_songs": default_songs,
            "today": today,
            "selected_date": selected_date,
            "previous_date": selected_date - timedelta(days=1),
            "next_date": selected_date + timedelta(days=1),
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