"""Build DayCtx from calendar days (liturgy.days.BuiltDay). Pure: no Django.

The Django side converts DB rows into BuiltDay, so tests and the website share this code.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta

from engine.model import DayCtx, NeighbourCtx, OccurrenceCtx
from liturgy.days import BuiltDay

NEIGHBOUR_WINDOW = 7


def occurrence_ctx(day: BuiltDay, categories: Mapping[str, frozenset[str]]) -> tuple[OccurrenceCtx, ...]:
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
        for o in day.occurrences
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
