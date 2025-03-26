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
        Recommend song for each mass part.
        Priority of assignment:
            specific, typical, seasonal
            mandatory -> default
        """
        detailed_song_recommendations = defaultdict(lambda: MassPartSelector(name='', songs=[]))
        rules_categories = ['specific_rules', 'typical_rules', 'seasonal_rules']
        priorities = [3, 2, 1, 0]  # ['mandatory', 'strongly preferred', 'preferred', 'default']

        for rules_category in rules_categories:
            for priority in priorities:
                current_rules = self.get_rules_by_priority(rules_list=rules.get(rules_category, []), priority=priority)
                random.shuffle(current_rules)
                for rule in current_rules:
                    detailed_song_recommendations = self.assign_song(
                        song_rule=rule,
                        recommendations=detailed_song_recommendations,
                    )

        detailed_song_recommendations = self.fill_in_changeables(
            recommendations=detailed_song_recommendations,
            liturgical_season=liturgical_season,
        )

        detailed_song_recommendations = self.get_ordered_recommendations(detailed_song_recommendations)

        return dict(detailed_song_recommendations)

    def get_rules_by_priority(
        self,
        rules_list: List[SongRule],
        priority: int,
    ) -> List[SongRule]:
        return [rule for rule in rules_list if rule.priority == priority]

    def fill_in_changeables(
        self,
        recommendations: Dict[str, MassPartSelector],
        liturgical_season: LiturgicalSeasonEnum,
    ) -> Dict[str, MassPartSelector]:
        """
        Sometimes the main song doesn't have sufficient verses for these parts. Fill in appropriate songs.
        """
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

        main_song_ = recommendations.get('main')
        main_song = main_song_.songs[0] if main_song_ is not None else None
        if main_song is None:
            return recommendations
        for part, (verse_attr, seasons) in changeable_mass_parts.items():
            if not getattr(main_song, verse_attr, False) and not recommendations[part].songs:
                song = self.get_song_for_mass_part(mass_part=part, liturgical_seasons=seasons)
                if song:
                    recommendations[part] = MassPartSelector(part, [song])
        return recommendations

    def assign_song(
        self,
        song_rule: SongRule,
        recommendations: Dict[str, MassPartSelector],
    ) -> Dict[str, MassPartSelector]:
        """
        Assign song to mass part based on provided rule.
        """
        if song_rule.can_be_main:
            if not any(recommendations.get(part) for part in ('main', 'gospel', 'offertory')):
                recommendations.setdefault('main', MassPartSelector('main', [song_rule.song]))
            return recommendations

        mass_part_name = song_rule.mass_part.name
        if recommendations.get(mass_part_name) is not None:
            return recommendations

        if recommendations.get('main') is not None:
            if mass_part_name in {'entrance', 'gospel', 'offertory'}:
                return recommendations
            if mass_part_name == 'communion' and recommendations['main'].songs[0].has_communion_verse:
                return recommendations
            if mass_part_name == 'recessional' and recommendations['main'].songs[0].has_recessional_verse:
                return recommendations

        recommendations.setdefault(mass_part_name, MassPartSelector(mass_part_name, [song_rule.song]))
        return recommendations

    def get_ordered_recommendations(
        self,
        detailed_song_recommendations: Dict[str, MassPartSelector],
    ) -> Dict[str, MassPartSelector]:
        """
        Orders the song recommendations based on a predefined order.
        Main song should come first, followed by the specific mass parts in a set order.
        """
        mass_part_order = [
            'main',
            'entrance',
            'asperges',
            'ordinarium',
            'psalm',
            'sequence',
            'aleluia',
            'gospel',
            'imposition of ashes',
            'offertory',
            'communion',
            'recessional',
        ]

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
