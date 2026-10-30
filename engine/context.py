"""Build DayCtx from calendar days (liturgy.days.BuiltDay). Pure: no Django.

The Django side converts DB rows into BuiltDay, so tests and the website share this code.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from decimal import Decimal

from engine.model import DayCtx, NeighbourCtx, OccurrenceCtx
from liturgy.constants import RANK_VOTIVE
from liturgy.days import BuiltDay, BuiltOccurrence

NEIGHBOUR_WINDOW = 7


FIRST_FRIDAY_KEY = 'prvni-patek'
FIRST_FRIDAY_TITLE = 'První pátek v měsíci – votivní mše o Nejsvětějším Srdci Ježíšově'
VOTIVE_ALLOWED_FROM = Decimal('3.12')  # only ferias and optional memorials leave room for a votive mass


def first_friday_votive(day: BuiltDay) -> BuiltOccurrence | None:
    """The customary votive mass of the first Friday: weekdays of Ordinary Time only (votive masses are not
    said in the strong seasons), and only when no obligatory memorial or higher celebration occurs."""
    if day.date.weekday() != 4 or day.date.day > 7 or day.season != 'ordinary':
        return None
    if any(o.is_mass_option and o.rank_num < VOTIVE_ALLOWED_FROM for o in day.occurrences):
        return None
    return BuiltOccurrence(
        position=max((o.position for o in day.occurrences), default=0) + 1,
        title=FIRST_FRIDAY_TITLE,
        rank_label=RANK_VOTIVE,
        rank_num=Decimal('3.13'),
        colour='white',
        celebration_key=FIRST_FRIDAY_KEY,
    )


def occurrence_ctx(day: BuiltDay, categories: Mapping[str, frozenset[str]]) -> tuple[OccurrenceCtx, ...]:
    votive = first_friday_votive(day)
    occurrences = (*day.occurrences, votive) if votive else day.occurrences
    return tuple(
        OccurrenceCtx(
            title=o.title,
            rank_label=o.rank_label,
            rank_num=o.rank_num,
            colour=o.colour,
            celebration_key=o.celebration_key,
            categories=categories.get(o.celebration_key, frozenset()) if o.celebration_key else frozenset(),
            position=o.position,
        )
        for o in occurrences
    )


def day_ctx(
    days: Mapping[date, BuiltDay],
    day: date,
    diocese: str,
    categories: Mapping[str, frozenset[str]],
    with_previous_week: bool = True,
) -> DayCtx | None:
    """Context for `day`; `days` must contain day ± NEIGHBOUR_WINDOW (and day - 7 ± window for variety)."""
    built = days.get(day)
    if built is None:
        return None
    neighbours = []
    for delta in range(-NEIGHBOUR_WINDOW, NEIGHBOUR_WINDOW + 1):
        other = days.get(day + timedelta(days=delta))
        if other is None or delta == 0:
            continue
        for o in other.occurrences:
            if o.celebration_key and o.is_mass_option:
                neighbours.append(NeighbourCtx(other.date, o.title, o.celebration_key, o.rank_num, other.season,
                                              o.rank_label))
    previous = None
    if with_previous_week:
        previous = day_ctx(days, day - timedelta(days=7), diocese, categories, with_previous_week=False)
    return DayCtx(
        date=built.date,
        diocese=diocese,
        season=built.season,
        season_week=built.season_week,
        sunday_cycle=built.sunday_cycle,
        ferial_cycle=built.ferial_cycle,
        occurrences=occurrence_ctx(built, categories),
        neighbours=tuple(neighbours),
        previous_week=previous,
    )


def context_range(day: date) -> tuple[date, date]:
    """Dates whose calendar rows day_ctx needs."""
    return day - timedelta(days=7 + NEIGHBOUR_WINDOW), day + timedelta(days=NEIGHBOUR_WINDOW)
