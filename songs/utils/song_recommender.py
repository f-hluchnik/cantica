import random
from collections import defaultdict
from datetime import date
from typing import Dict, List, Optional

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, QuerySet

from celebrations.models import Celebration, CelebrationType
from songs.models import LiturgicalSeason, LiturgicalSubSeason, Song, SongRule
from songs.utils.helpers import (
    get_song_section_for_liturgical_season,
    is_christmas_octave,
    is_late_advent,
    is_late_lent,
    is_pentecost_novena,
    is_week_of_prayer_for_christian_unity,
)
from songs.utils.liturgical_season import LiturgicalSeasonEnum


class MassPartSelector():
    def __init__(
        self,
        name: str,
        songs: List,
    ) -> None:
        translations = {
            'main': 'mešní píseň',
            'entrance': 'vstup',
            'asperges': 'asperges',
            'ordinarium': 'ordinárium',
            'psalm': 'žalm',
            'sequence': 'sekvence',
            'aleluia': 'aleluja',
            'gospel': 'evangelium',
            'imposition of ashes': 'udělování popelce',
            'offertory': 'obětování',
            'communion': 'přijímání',
            'recessional': 'závěr',
        }
        self.name = translations.get(name, name)
        self.songs = songs

    def __str__(self) -> None:
        return '{}: {}'.format(self.name, self.songs)


class RecommendedSongs():
    def __init__(
        self,
        specific: QuerySet[Song, Song],
        typical: QuerySet[Song, Song],
        seasonal: str,
        detailed: Dict[str, List[SongRule]],
    ) -> None:
        self.specific = specific
        self.typical = typical
        self.seasonal = seasonal
        self.detailed = detailed


class SongRecommender:
    def __init__(self) -> None:
        self.today = date.today()

    def get_song_rules(
        self,
        day: date,
        celebration: Optional[Celebration],
        season: Optional[LiturgicalSeasonEnum],
    ) -> Dict[str, List[SongRule]]:
        """
        Retrieve song rules based on season, subseason, and celebration.
        """
        try:
            current_season = LiturgicalSeason.objects.get(name__iexact=season.value)
        except LiturgicalSeason.DoesNotExist:
            current_season = None

        current_subseasons = self.get_current_subseasons(day)
        subseason_rules = SongRule.objects.none()
        if current_subseasons:
            subseason_content_type = ContentType.objects.get_for_model(LiturgicalSubSeason)
            subseason_rules = SongRule.objects.filter(
                content_type=subseason_content_type,
                object_id__in=LiturgicalSubSeason.objects.filter(
                    name__in=current_subseasons,
                ).values_list('id', flat=True),
            )

        season_content_type = ContentType.objects.get_for_model(LiturgicalSeason)
        tmp_seasonal_rules = SongRule.objects.filter(
            content_type=season_content_type, object_id=current_season.id,
        )
        seasonal_rules = list(tmp_seasonal_rules) + list(subseason_rules)

        celebration_type_ct = ContentType.objects.get_for_model(CelebrationType)
        typical_rules = SongRule.objects.filter(
            content_type=celebration_type_ct,
            object_id__in=celebration.types.values_list('id', flat=True),
        ).distinct()

        celebration_ct = ContentType.objects.get_for_model(Celebration)
        specific_rules = SongRule.objects.filter(
            content_type=celebration_ct,
            object_id=celebration.id,
        )
        all_rules = list(specific_rules) + list(typical_rules) + list(seasonal_rules)
        filtered_rules = self.apply_rule_priority(all_rules)

        specific_filtered = [r for r in filtered_rules if r in specific_rules]
        typical_filtered = [r for r in filtered_rules if r in typical_rules]
        seasonal_filtered = [r for r in filtered_rules if r in seasonal_rules]

        return {
            'specific_rules': specific_filtered,
            'typical_rules': typical_filtered,
            'seasonal_rules': seasonal_filtered,
        }

    def recommend_songs(
        self,
        day: date,
        celebration: Celebration,
        liturgical_season: LiturgicalSeasonEnum,
    ) -> RecommendedSongs:
        """
        Recommend songs based on liturgical criteria.
        """
        rules = self.get_song_rules(day, celebration, liturgical_season)
        section = get_song_section_for_liturgical_season(liturgical_season)
        seasonal_songs = 'písně z oddílu {section}'.format(section=section)
        detailed_recommendation = self.get_detailed_recommendation(rules=rules, liturgical_season=liturgical_season)

        return RecommendedSongs(
            specific=[rule.song for rule in rules['specific_rules']],
            typical=[rule.song for rule in rules['typical_rules']],
            seasonal=seasonal_songs,
            detailed=detailed_recommendation,
        )

    def get_detailed_recommendation(
        self,
        rules: Dict[str, List[SongRule]],
        liturgical_season: LiturgicalSeasonEnum,
    ) -> Dict[str, MassPartSelector]:
        """
        Recommend songs for different mass parts, prioritizing specific songs over typical and seasonal.
        """
        detailed_song_recommendations = defaultdict(lambda: MassPartSelector(name='', songs=[]))
        priority_order = ['specific_rules', 'typical_rules', 'seasonal_rules']
        basic_mass_parts = {'entrance', 'gospel', 'offertory', 'communion', 'recessional'}

        available_main_songs = None
        main_song = None

        for category in priority_order:
            if category not in rules:
                continue

            rules_list = rules[category]

            if category == 'seasonal_rules' and main_song is None:
                first_song_rule = random.choice(rules_list)  # noqa S311

                if first_song_rule.can_be_main:
                    main_song = first_song_rule.song
                else:
                    mass_part_name = first_song_rule.mass_part.name
                    remaining_parts = basic_mass_parts - {mass_part_name}

                    detailed_song_recommendations.setdefault(mass_part_name, MassPartSelector(mass_part_name, []))
                    if not detailed_song_recommendations[mass_part_name].songs:
                        detailed_song_recommendations[mass_part_name].songs = [first_song_rule.song]

                    rules_dict = {rule.mass_part.name: rule for rule in rules_list}
                    for part in remaining_parts:
                        if part not in rules_dict:
                            continue

                        detailed_song_recommendations.setdefault(part, MassPartSelector(part, []))
                        if not detailed_song_recommendations[part].songs:
                            detailed_song_recommendations[part].songs = [rules_dict[part].song]
            else:
                if available_main_songs is None:
                    available_main_songs = [rule.song for rule in rules_list if rule.can_be_main]

                if available_main_songs and main_song is None:
                    main_song = random.choice(available_main_songs)  # noqa S311

            # suplement missing songs
            for rule in rules_list:
                mass_part_name = rule.mass_part.name

                if mass_part_name == 'main':
                    if all(detailed_song_recommendations[part].songs for part in basic_mass_parts) or main_song:
                        continue
                elif main_song and rule.priority < 1:
                    continue

                detailed_song_recommendations.setdefault(mass_part_name, MassPartSelector(mass_part_name, []))
                if not detailed_song_recommendations[mass_part_name].songs:
                    detailed_song_recommendations[mass_part_name].songs = [rule.song]

        if main_song:
            detailed_song_recommendations['main'] = MassPartSelector('main', [main_song])

        # Handle conditional mass parts
        changeable_mass_parts = {
            'communion': (
                'has_communion_verse',
                [liturgical_season, LiturgicalSeasonEnum.JESUS_CHRIST],
            ),
            'recessional': (
                'has_recessional_verse',
                [liturgical_season, LiturgicalSeasonEnum.JESUS_CHRIST, LiturgicalSeasonEnum.VIRGIN_MARY],
            ),
        }

        for part, (verse_attr, seasons) in changeable_mass_parts.items():
            if not getattr(main_song, verse_attr, False) and not detailed_song_recommendations[part].songs:
                song = self.get_song_for_mass_part(mass_part=part, liturgical_seasons=seasons)
                if song:
                    detailed_song_recommendations[part] = MassPartSelector(part, [song])

        detailed_song_recommendations = self.get_ordered_recommendations(detailed_song_recommendations)

        return dict(detailed_song_recommendations)

    def get_ordered_recommendations(
        self,
        detailed_song_recommendations: Dict[str, MassPartSelector],
    ) -> Dict[str, MassPartSelector]:
        """
        Orders the song recommendations based on a predefined order.
        Main song should come first, followed by the specific mass parts in a set order.
        """
        mass_part_order = ['main', 'entrance', 'sequence', 'gospel', 'offertory', 'communion', 'recessional']

        ordered_recommendations = {}

        for part in mass_part_order:
            if part in detailed_song_recommendations:
                ordered_recommendations[part] = detailed_song_recommendations[part]

        return ordered_recommendations

    def get_song_for_mass_part(
        self,
        mass_part: str,
        liturgical_seasons: List[LiturgicalSeasonEnum],
    ) -> str:
        season_content_type = ContentType.objects.get_for_model(LiturgicalSeason)

        season_names = [season.value for season in liturgical_seasons]
        seasons = LiturgicalSeason.objects.filter(name__in=season_names)

        if not seasons.exists():
            return None

        conditions = Q(content_type=season_content_type) & Q(mass_part__name=mass_part)
        conditions &= Q(object_id__in=seasons.values_list('id', flat=True))

        song_rule_qs = SongRule.objects.filter(conditions)

        selected_rule = song_rule_qs.order_by('?').first()
        return selected_rule.song if selected_rule else None

    def get_current_subseasons(self, current_date: date) -> set:
        """
        Check if provided date falls into some subseason.
        """
        subseason_checks = {
            'late_advent': is_late_advent,
            'christmas_octave': is_christmas_octave,
            'week_of_prayer_for_christian_unity': is_week_of_prayer_for_christian_unity,
            'late_lent': is_late_lent,
            'pentecost_novena': is_pentecost_novena,
        }

        matching_subseasons = set()
        for name, check in subseason_checks.items():
            if check(date_to_check=current_date):
                matching_subseasons.add(name)

        return matching_subseasons

    def apply_rule_priority(self, rules: List[SongRule]) -> List[SongRule]:
        """
        Group rules by mass part and apply priority:
        - If any rule for a mass part is exclusive, keep only the highest-priority exclusive rule(s).
        - Otherwise, keep all rules sorted by priority.
        """
        rules_by_mass_part = defaultdict(list)

        for rule in rules:
            rules_by_mass_part[rule.mass_part.name].append(rule)

        filtered_rules = []

        for part_rules in rules_by_mass_part.values():
            part_rules.sort(key=lambda r: r.priority, reverse=True)  # Sort once per group
            exclusive_rules = [rule for rule in part_rules if rule.exclusive]

            if exclusive_rules:
                highest_priority = exclusive_rules[0].priority
                filtered_rules.extend(rule for rule in exclusive_rules if rule.priority == highest_priority)
            else:
                filtered_rules.extend(part_rules)

        return filtered_rules
