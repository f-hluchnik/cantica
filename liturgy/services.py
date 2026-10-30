"""Read-side queries for the web layer."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.utils import timezone

from liturgy import norms
from liturgy.constants import COLOURS, SEASON_LABELS
from liturgy.dbbuild import latest_build
from liturgy.models import CalendarDay, Occurrence


@dataclass(frozen=True)
class MassOption:
    title: str
    rank_label: str  # human label, '' = none
    colour: str
    colour_label: str
    norms: norms.MassNorms
    celebration_key: str | None


@dataclass(frozen=True)
class DayView:
    date: date
    season: str
    season_label: str
    season_week: int
    sunday_cycle: str
    ferial_cycle: int
    masses: list[MassOption]
    commemorations: list[str]


def day_view(diocese_code: str, day: date) -> DayView | None:
    calendar_day = (
        CalendarDay.objects
        .filter(diocese_id=diocese_code, date=day)
        .prefetch_related('occurrences')
        .first()
    )
    if calendar_day is None:
        return None
    occurrences: list[Occurrence] = sorted(
        calendar_day.occurrences.all(),
        key=lambda o: norms.rank_sort_key(o.rank_num, o.position),
    )
    masses = [
        MassOption(
            title=o.title,
            rank_label=norms.rank_display(day, o.rank_label, o.title),
            colour=o.colour,
            colour_label=COLOURS.get(o.colour, o.colour),
            norms=norms.mass_norms(day, calendar_day.season, o.rank_label, o.title),
            celebration_key=o.celebration_id,
        )
        for o in occurrences
        if o.is_mass_option
    ]
    return DayView(
        date=day,
        season=calendar_day.season,
        season_label=SEASON_LABELS.get(calendar_day.season, calendar_day.season),
        season_week=calendar_day.season_week,
        sunday_cycle=calendar_day.sunday_cycle,
        ferial_cycle=calendar_day.ferial_cycle,
        masses=masses,
        commemorations=[o.title for o in occurrences if not o.is_mass_option],
    )


@dataclass(frozen=True)
class Health:
    status: str  # 'ok' | 'warn' | 'error'
    last_date: date | None
    days_ahead: int | None
    built_at: str | None


def health(min_days_ahead: int) -> Health:
    build = latest_build()
    if build is None:
        return Health(status='error', last_date=None, days_ahead=None, built_at=None)
    days_ahead = (build.last_date - timezone.localdate()).days
    return Health(
        status='ok' if days_ahead >= min_days_ahead else 'warn',
        last_date=build.last_date,
        days_ahead=days_ahead,
        built_at=build.built_at.isoformat(),
    )
