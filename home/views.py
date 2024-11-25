from django.views.generic import TemplateView
from celebrations.utils.liturgy_api_client import LiturgyAPIClient
from datetime import date, datetime, timedelta
from celebrations.models import Celebration, LiturgicalCalendarEvent
from songs.models import Song

class HomePageView(TemplateView):
    template_name = 'home/homepage.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = datetime.now()
        date_str = self.request.GET.get('date', datetime.now().strftime('%Y-%m-%d'))
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            selected_date = datetime.now().strftime('%Y-%m-%d')

        liturgical_day = LiturgicalCalendarEvent.objects.filter(date=date_str)
        celebration_slugs = liturgical_day.values_list('celebrations__slug', flat=True)
        liturgical_season = liturgical_day.values_list('season', flat=True).first()

        celebrations = Celebration.objects.filter(slug__in=celebration_slugs)

        # Fetch song recommendations for each celebration
        celebration_songs = []
        for celebration in celebrations:
            specific_songs = Song.objects.filter(celebration=celebration)
            type_songs = Song.objects.filter(celebration_types__in=celebration.types.all()).distinct()
            is_jesus_christ_celebration = 'jesus christ' in [ft.name for ft in celebration.types.all()]
            is_virgin_mary_celebration = 'virgin mary' in [ft.name for ft in celebration.types.all()]
            celebration_songs.append({
                'celebration': celebration,
                'specific_songs': specific_songs,
                'type_songs': type_songs,
                'is_jesus_christ_celebration': is_jesus_christ_celebration,
                'is_virgin_mary_celebration': is_virgin_mary_celebration,
            })
        seasonal_songs_section = self.get_song_section_for_liturgical_season(liturgical_season=liturgical_season)

        # Add to context
        context = {
            'celebration_songs': celebration_songs,
            'seasonal_songs_section': seasonal_songs_section,
            'today': today,
            'selected_date': selected_date,
            'previous_date': selected_date - timedelta(days=1),
            'next_date': selected_date + timedelta(days=1),
        }
        return context
    
    def get_song_section_for_liturgical_season(self, liturgical_season: str) -> str:
        '''
        Map the given liturgical season to its corresponding song section.
        '''
        song_sections = {
            'advent': '100',
            'christmas': '200',
            'lent': '300',
            'easter': '400',
            'ordinary': '500',
            'jesus christ': '700',
            'virgin mary': '800',
            'saints': '800',
            'occasional': '900',
        }
        return song_sections.get(liturgical_season, '')
        