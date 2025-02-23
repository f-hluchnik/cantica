import random

from datetime import date
from django.db import models
from enum import Enum
from typing import Dict, List, Optional

from celebrations.models import Celebration
from songs.models import Song, LiturgicalSeason, Occasion
from songs.utils.liturgical_season import LiturgicalSeasonEnum


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


class MassPart():
    def __init__(
        self,
        name: str,
        songs: List
    ) -> None:
        self.name = name
        self.songs = songs


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

    def recommmend_songs(
        self,
        day: date,
        celebration: Celebration,
        season: LiturgicalSeasonEnum,
    ) -> Dict:
        """
        Recommend song based on several criteria.
        """
        specific_songs = Song.objects.filter(celebration=celebration)
        typical_songs = Song.objects.filter(celebration_types__in=celebration.types.all()).distinct()
        section = self.get_song_section_for_liturgical_season(season)
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
            section = self.get_song_section_for_liturgical_season(LiturgicalSeasonEnum.JESUS_CHRIST)
            recommended_songs.seasonal = 'písně z oddílu {}'.format(section)

    def handle_virgin_mary_celebrations(self, celebration: Celebration, recommended_songs: RecommendedSongs) -> None:
        is_virgin_mary_celebration = 'virgin mary' in [celebration_type.name for celebration_type in celebration.types.all()]
        if is_virgin_mary_celebration:
            recommended_songs.typical = []
            section = self.get_song_section_for_liturgical_season(LiturgicalSeasonEnum.VIRGIN_MARY)
            recommended_songs.seasonal = 'mariánské písně z oddílu {}'.format(section)

    def handle_advent_before_christmas(self, date_to_check: date, recommended_songs: RecommendedSongs):
        """
        In the last week before christmas, specific seasonal songs are recommended.
        """
        before_christmas_start = (12, 17)
        before_christmas_end = (12, 24)
        date_to_check_yearless = (date_to_check.month, date_to_check.day)
        if before_christmas_start <= date_to_check_yearless <= before_christmas_end:
            section = self.get_song_section_for_liturgical_season(LiturgicalSeasonEnum.ADVENT)
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
            section = self.get_song_section_for_liturgical_season(LiturgicalSeasonEnum.CHRISTMAS)
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

    def recommend_song_for_mass_parts(
        self,
        already_recommended_songs: Optional[RecommendedSongs],
        season: LiturgicalSeasonEnum,
    ) -> Dict:
        """
        Recommend song for each part of the mass.
        """
        detailed_recommended_songs = {
            'main': MassPart(name='mešní píseň', songs=[]),
            'entrance': MassPart(name='vstup', songs=[]),
            'ordinarium': MassPart(name='ordinárium', songs=[]),
            'psalm': MassPart(name='žalm', songs=[]),
            'aleluia': MassPart(name='aleluja', songs=[]),
            'gospel': MassPart(name='evangelium', songs=[]),
            'offertory': MassPart(name='obětování', songs=[]),
            'communion': MassPart(name='přijímání', songs=[]),
            'recessional': MassPart(name='závěr', songs=[]),
        }

        self.try_assign_songs(detailed_recommended_songs, already_recommended_songs.specific, season=season)
        self.try_assign_songs(detailed_recommended_songs, already_recommended_songs.typical, season=season)
        if not detailed_recommended_songs['main'].songs:
            detailed_recommended_songs['main'].songs = [self.select_song(season, 'main')]
        print(detailed_recommended_songs)
        filtered_dict = {key: value for key, value in detailed_recommended_songs.items() if value}
        return filtered_dict

    def try_assign_songs(self, detailed_recommended_songs: Dict, songs: List, season: LiturgicalSeasonEnum):
        """
        Try assign songs to the mass parts.
        """
        for song in songs:
            if self.can_be_main_song(song=song, liturgical_season=season):
                detailed_recommended_songs['main'].songs.append(song)
            else:
                for occasion in song.occasions.all():
                    if occasion.name != 'main':  # Skip the main song check
                        detailed_recommended_songs[occasion.name].songs.append(song)
                        print(detailed_recommended_songs)

    @staticmethod
    def can_be_main_song(song: Song, liturgical_season: LiturgicalSeasonEnum) -> bool:
        """
        Check if the song can be used as the main song for the mass.
        Criteria: It must match the liturgical season and occasion.
        """
        # Check if the song's liturgical time is suitable or not specified (None)
        if song.liturgical_season and song.liturgical_season.name != liturgical_season.value:
            return False

        # Check if the song's occasion is suitable or not specified (None)
        if song.occasions.exists() and not song.occasions.filter(name='main').exists():
            return False

        return True

    @staticmethod
    def get_song_section_for_liturgical_season(liturgical_season: LiturgicalSeasonEnum) -> str:
        """
        Map the given liturgical season to its corresponding song section.
        """
        mapping = {
            LiturgicalSeasonEnum.ADVENT: SongSection.ADVENT.value,
            LiturgicalSeasonEnum.CHRISTMAS: SongSection.CHRISTMAS.value,
            LiturgicalSeasonEnum.LENT: SongSection.LENT.value,
            LiturgicalSeasonEnum.EASTER: SongSection.EASTER.value,
            LiturgicalSeasonEnum.ORDINARY: SongSection.ORDINARY.value,
            LiturgicalSeasonEnum.JESUS_CHRIST: SongSection.JESUS_CHRIST.value,
            LiturgicalSeasonEnum.VIRGIN_MARY: SongSection.VIRGIN_MARY.value,
            LiturgicalSeasonEnum.SAINTS: SongSection.SAINTS.value,
            LiturgicalSeasonEnum.OCCASIONAL: SongSection.OCCASIONAL.value,
        }

        return mapping.get(liturgical_season, '')

    def select_song(self, liturgical_season: LiturgicalSeasonEnum, occasion: str) -> Optional[Song]:
        try:
            liturgical_season_instance = LiturgicalSeason.objects.get(name=liturgical_season.value)
        except LiturgicalSeason.DoesNotExist:
            return None
        try:
            occasion_instance = Occasion.objects.get(name=occasion)
        except Occasion.DoesNotExist:
            return None
        # songs = Song.objects.filter(
        #     models.Q(liturgical_season=liturgical_season_instance) | models.Q(liturgical_season__isnull=True),
        #     models.Q(occasions__in=[occasion_instance]) | models.Q(occasions__isnull=True)
        # )
        songs = Song.objects.filter(
            models.Q(liturgical_season=liturgical_season_instance),
            models.Q(occasions__in=[occasion_instance])
        )
        return random.choice(list(songs)) if songs.exists() else None
