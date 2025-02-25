from django.views.generic import TemplateView
from datetime import datetime, timedelta
from celebrations.models import Celebration, LiturgicalCalendarEvent
from songs.utils.song_recommender import SongRecommender
from songs.utils.liturgical_season import LiturgicalSeasonEnum


class HomePageView(TemplateView):
    template_name = 'home/homepage.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = datetime.now()
        date_str = self.request.GET.get('date', datetime.now().strftime('%Y-%m-%d'))  # noqa E501
        if not date_str:
            date_str = datetime.now().strftime('%Y-%m-%d')
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        liturgical_day = LiturgicalCalendarEvent.objects.filter(date=date_str)
        celebration_slugs = liturgical_day.values_list('celebrations__slug', flat=True)  # noqa E501
        liturgical_season = liturgical_day.values_list('season', flat=True).first()  # noqa E501
        season = LiturgicalSeasonEnum.from_string(liturgical_season)

        celebrations = Celebration.objects.filter(slug__in=celebration_slugs)

        # Fetch song recommendations for each celebration
        recommender = SongRecommender()
        celebrations_with_songs = []
        for celebration in celebrations:
            recommended_songs = recommender.recommmend_songs(
                day=selected_date,
                celebration=celebration,
                season=season
            )

            detailed_recommended_songs = recommender.recommend_song_for_mass_parts(  # noqa E501
                already_recommended_songs=recommended_songs,
                season=season
            )

            celebrations_with_songs.append({
                'celebration': celebration,
                'recommended_songs': recommended_songs,
                'detailed_recommended_songs': detailed_recommended_songs
            })

        # Add to context
        context = {
            'celebrations_with_songs': celebrations_with_songs,
            'today': today,
            'selected_date': selected_date,
            'previous_date': selected_date - timedelta(days=1),
            'next_date': selected_date + timedelta(days=1),
        }
        return context


class AboutView(TemplateView):
    template_name = 'home/homepage.html'
