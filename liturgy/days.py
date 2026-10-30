"""Turn raw snapshots + the celebration catalog into validated calendar days.

Pure module: must not import Django. The calendar_build command writes the result to the DB.
Validation is strict and reports every problem at once; nothing is written if any problem exists.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from itertools import pairwise

from liturgy import norms
from liturgy.catalog import Catalog
from liturgy.constants import RANK_COMMEMORATION, RANK_FERIA, RANK_LABELS, SEASON_KEYS
from liturgy.snapshot import MonthSnapshot


@dataclass(frozen=True)
class BuiltOccurrence:
    position: int
    title: str
    rank_label: str
    rank_num: Decimal
    colour: str
    celebration_key: str | None  # None for plain ferias (not catalogued)

    @property
    def is_mass_option(self) -> bool:
        """Commemorations (připomínka) are shown as a note, not as a separate mass."""
        return self.rank_label != RANK_COMMEMORATION


@dataclass(frozen=True)
class BuiltDay:
    calendar: str
    date: date
    season: str
    season_week: int
    sunday_cycle: str
    ferial_cycle: int
    occurrences: tuple[BuiltOccurrence, ...]


@dataclass
class BuildResult:
    days: list[BuiltDay]
    problems: list[str]
    unknown_titles: dict[str, list[str]]  # title -> where it occurs (for --register-new and reports)

    @property
    def ok(self) -> bool:
        return not self.problems


def needs_catalog_entry(rank_label: str) -> bool:
    """Every occurrence except a plain feria must map to a catalogued celebration."""
    return rank_label != RANK_FERIA


def unknown_titles(snapshots: Iterable[MonthSnapshot], catalog: Catalog) -> dict[str, list[str]]:
    found: dict[str, list[str]] = defaultdict(list)
    for snapshot in snapshots:
        for day in snapshot.days():
            for occ in day.occurrences:
                if needs_catalog_entry(occ.rank_label) and catalog.resolve(occ.title) is None:
                    found[occ.title].append(f'{snapshot.calendar} {day.date.isoformat()}')
    return dict(found)


def build(snapshots: Iterable[MonthSnapshot], catalog: Catalog) -> BuildResult:
    snapshots = list(snapshots)
    problems: list[str] = []
    days: list[BuiltDay] = []

    by_calendar: dict[str, list[MonthSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        by_calendar[snapshot.calendar].append(snapshot)
    for calendar, items in sorted(by_calendar.items()):
        problems.extend(_month_gaps(calendar, items))

    unknown = unknown_titles(snapshots, catalog)
    for title, places in sorted(unknown.items()):
        shown = ', '.join(places[:3]) + (f' (+{len(places) - 3})' if len(places) > 3 else '')
        problems.append(f'unknown celebration title {title!r} at {shown}')

    for snapshot in snapshots:
        for day in snapshot.days():
            where = f'{snapshot.calendar} {day.date.isoformat()}'
            if day.season not in SEASON_KEYS:
                problems.append(f'{where}: unknown season {day.season!r}')
            occurrences = []
            for position, occ in enumerate(day.occurrences):
                if occ.rank_label not in RANK_LABELS:
                    problems.append(f'{where}: unknown rank label {occ.rank_label!r}')
                key = catalog.resolve(occ.title) if needs_catalog_entry(occ.rank_label) else None
                occurrences.append(BuiltOccurrence(
                    position=position,
                    title=occ.title,
                    rank_label=occ.rank_label,
                    rank_num=occ.rank_num,
                    colour=occ.colour,
                    celebration_key=key,
                ))
            if not any(o.is_mass_option for o in occurrences):
                problems.append(f'{where}: no celebration other than a commemoration')
            days.append(BuiltDay(
                calendar=snapshot.calendar,
                date=day.date,
                season=day.season,
                season_week=day.season_week,
                sunday_cycle=norms.sunday_cycle(day.date),
                ferial_cycle=norms.ferial_cycle(day.date),
                occurrences=tuple(occurrences),
            ))
    return BuildResult(days=days, problems=problems, unknown_titles=unknown)


def _month_gaps(calendar: str, snapshots: list[MonthSnapshot]) -> list[str]:
    months = sorted({(s.year, s.month) for s in snapshots})
    problems = []
    for (y1, m1), (y2, m2) in pairwise(months):
        expected = (y1 + m1 // 12, m1 % 12 + 1)
        if (y2, m2) != expected:
            problems.append(
                f'{calendar}: months not contiguous ({y1:04d}-{m1:02d} is followed by {y2:04d}-{m2:02d})',
            )
    return problems
