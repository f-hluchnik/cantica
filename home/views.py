from datetime import datetime, timedelta
from typing import Any, Dict

from django.views.generic import TemplateView

from celebrations.models import Celebration, LiturgicalCalendarEvent
from songs.models import LiturgicalSeason, LiturgicalSubSeason
from songs.utils.helpers import is_may
from songs.utils.liturgical_season import LiturgicalSeasonEnum
from songs.utils.song_recommender import SongRecommender


class HomePageView(TemplateView):
    template_name = 'home/homepage.html'

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        today = datetime.now()
        date_str = self.request.GET.get('date', datetime.now().strftime('%Y-%m-%d'))
        if not date_str:
            date_str = datetime.now().strftime('%Y-%m-%d')
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        liturgical_day = LiturgicalCalendarEvent.objects.filter(date=date_str)
        celebration_slugs = liturgical_day.values_list('celebrations__slug', flat=True)
        liturgical_season = liturgical_day.values_list('season', flat=True).first()
        season = LiturgicalSeasonEnum.from_string(liturgical_season)
        ls = LiturgicalSeason.objects.filter(name=liturgical_season).first()
        custom_description = ''
        if is_may(selected_date):
            custom_description = 'Měsíc květen je v lidové zbožnosti věnován úctě Panny Marie. Vyjma mší o Panně' \
                'Marii, však mariánské písně ke mši nehrajeme - ty se mohou hrát po mši nebo při májových pobožnostech.'

        recommender = SongRecommender()

        subseasons = list(recommender.get_current_subseasons(current_date=selected_date))
        liturgical_subseasons = LiturgicalSubSeason.objects.filter(name__in=subseasons)
        subseasons_descriptions = ''
        for subseason in liturgical_subseasons:
            subseasons_descriptions += subseason.description

        celebrations = Celebration.objects.filter(slug__in=celebration_slugs)
        celebrations_with_songs = []
        for celebration in celebrations:
            recommended_songs = recommender.recommend_songs(
                day=selected_date,
                celebration=celebration,
                liturgical_season=season,
                liturgical_subseasons=liturgical_subseasons,
            )
            description = '\n'.join(filter(None, [
                celebration.description,
                ls.description,
                custom_description,
                subseasons_descriptions,
            ]))

            celebrations_with_songs.append({
                'celebration': celebration,
                'recommended_songs': recommended_songs,
                'description': description,
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
