from datetime import date, datetime
from enum import Enum
from typing import Dict, List

from celebrations.models import Celebration
from songs.models import Song

class LiturgicalSeason(Enum):
    ADVENT = 'advent'
    CHRISTMAS = 'christmas'
    LENT = 'lent'
    EASTER = 'easter'
    ORDINARY = 'ordinary'
    JESUS_CHRIST = 'jesus christ'
    VIRGIN_MARY = 'virgin mary'
    SAINTS = 'saints'
    OCCASIONAL = 'occasional'

    @classmethod
    def from_string(cls, value: str):
        """
        Get the LiturgicalSeason instance corresponding to the given string value.
        Returns None if the value does not match any enum member.
        """
        try:
            return cls(value)
        except ValueError:
            return None

class SongSection(Enum):
    ADVENT = '100'
    CHRISTMAS = '200'
    LENT = '300'
    EASTER = '400'
    ORDINARY = '500'
    JESUS_CHRIST = '700'
    VIRGIN_MARY = '800'
    SAINTS = '800'
    OCCASIONAL = '900'

class RecommendedSongs():
    def __init__(
        self,
        specific: List,
        typical: List,
        seasonal: str
    ) -> None:
        self.specific = specific
        self.typical = typical
        self.seasonal = seasonal

class SongRecommender:
    def __init__(self):
        self.today = date.today()

    def recommmend_song(
        self,
        day: date,
        celebration: Celebration,
        season: str, 
    ) -> Dict:
        """
        Recommend song based on several criteria.
        """
        specific_songs = Song.objects.filter(celebration=celebration)
        typical_songs = Song.objects.filter(celebration_types__in=celebration.types.all()).distinct()
        section = self.get_song_section_for_liturgical_season(LiturgicalSeason.from_string(season))
        seasonal_songs = 'písně z oddílu {}'.format(section)
        recommended_songs = RecommendedSongs(
            specific=specific_songs,
            typical=typical_songs,
            seasonal=seasonal_songs
        )

        self.handle_jesus_christ_celebrations(celebration=celebration, recommended_songs=recommended_songs)
        self.handle_virgin_mary_celebrations(celebration=celebration, recommended_songs=recommended_songs)
        self.handle_advent_before_christmas(date_to_check=day, recommended_songs=recommended_songs)
        self.handle_christmas_octave_precedence(date_to_check=day, recommended_songs=recommended_songs)
        self.handle_week_of_prayer_for_christian_unity(date_to_check=day, recommended_songs=recommended_songs)
        
        return recommended_songs
    
    def handle_jesus_christ_celebrations(self, celebration: Celebration, recommended_songs: RecommendedSongs) -> None:
        is_jesus_christ_celebration = 'jesus christ' in [celebration_type.name for celebration_type in celebration.types.all()]
        if is_jesus_christ_celebration:
            recommended_songs.typical = []
            section = self.get_song_section_for_liturgical_season(LiturgicalSeason.JESUS_CHRIST)
            recommended_songs.seasonal = 'písně z oddílu {}'.format(section)

    def handle_virgin_mary_celebrations(self, celebration: Celebration, recommended_songs: RecommendedSongs) -> None:
        is_virgin_mary_celebration = 'virgin mary' in [celebration_type.name for celebration_type in celebration.types.all()]
        if is_virgin_mary_celebration:
            recommended_songs.typical = []
            section = self.get_song_section_for_liturgical_season(LiturgicalSeason.VIRGIN_MARY)
            recommended_songs.seasonal = 'mariánské písně z oddílu {}'.format(section)

    def handle_advent_before_christmas(self, date_to_check: date, recommended_songs: RecommendedSongs):
        """
        In the last week before christmas, specific seasonal songs are recommended.
        """
        before_christmas_start = (12, 17)
        before_christmas_end = (12, 24)
        date_to_check_yearless = (date_to_check.month, date_to_check.day)
        if before_christmas_start <= date_to_check_yearless <= before_christmas_end:
            section = self.get_song_section_for_liturgical_season(LiturgicalSeason.ADVENT)
            recommended_songs.seasonal = 'písně z oddílu {}, zvláště 122, 124, 130'.format(section)

    def handle_christmas_octave_precedence(self, date_to_check: date, recommended_songs: RecommendedSongs):
        """
        Check if date is in christmas octave. If so, overload the typical songs.
        The function compares tuples of (month, day) to be year-agnostic.
        """
        NARODIL_SE_KRISTUS_PAN = 201
        start_date = (12, 25)
        end_date = (12, 31)
        date_to_check_yearless = (date_to_check.month, date_to_check.day)
        if start_date <= date_to_check_yearless <= end_date:
            recommended_songs.typical = []
            section = self.get_song_section_for_liturgical_season(LiturgicalSeason.CHRISTMAS)
            recommended_songs.seasonal = 'písně z oddílu {}'.format(section)
            recommended_songs.specific = Song.objects.filter(number=NARODIL_SE_KRISTUS_PAN)

    def handle_week_of_prayer_for_christian_unity(self, date_to_check: date, recommended_songs: RecommendedSongs):
        """
        Check if the date falls between January 18 and January 25.
        The function compares tuples of (month, day) to be year-agnostic.
        """
        JEDEN_PAN = 910
        start_date = (1, 18)
        end_date = (1, 25)
        date_to_check_yearless = (date_to_check.month, date_to_check.day)
        if start_date <= date_to_check_yearless <= end_date:
            recommended_songs.specific = Song.objects.filter(number=JEDEN_PAN)
    
    @staticmethod
    def get_song_section_for_liturgical_season(liturgical_season: LiturgicalSeason) -> str:
        """
        Map the given liturgical season to its corresponding song section.
        """
        mapping = {
            LiturgicalSeason.ADVENT: SongSection.ADVENT.value,
            LiturgicalSeason.CHRISTMAS: SongSection.CHRISTMAS.value,
            LiturgicalSeason.LENT: SongSection.LENT.value,
            LiturgicalSeason.EASTER: SongSection.EASTER.value,
            LiturgicalSeason.ORDINARY: SongSection.ORDINARY.value,
            LiturgicalSeason.JESUS_CHRIST: SongSection.JESUS_CHRIST.value,
            LiturgicalSeason.VIRGIN_MARY: SongSection.VIRGIN_MARY.value,
            LiturgicalSeason.SAINTS: SongSection.SAINTS.value,
            LiturgicalSeason.OCCASIONAL: SongSection.OCCASIONAL.value,
        }

        return mapping.get(liturgical_season, '')
