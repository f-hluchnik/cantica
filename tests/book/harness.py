"""Run the real engine on the committed data (no Django): calendar snapshots, catalogs, rules."""
from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

from catalog.curation import Curation
from engine.context import day_ctx
from engine.load import snapshot_from_curation
from engine.model import Snapshot
from engine.recommend import DayResult, recommend
from liturgy.catalog import Catalog
from liturgy.constants import DIOCESES
from liturgy.days import BuiltDay, build
from liturgy.periods import Periods
from liturgy.snapshot import read_snapshots

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data'
CALENDAR_OF = {d.code: d.calapi_calendar for d in DIOCESES}


@lru_cache(maxsize=1)
def catalog() -> Catalog:
    return Catalog.load(DATA / 'liturgy' / 'celebrations.yaml')


@lru_cache(maxsize=1)
def snapshot() -> Snapshot:
    return snapshot_from_curation(
        Curation.load(DATA / 'curated' / 'curation.yaml'),
        Periods.load(DATA / 'liturgy' / 'periods.yaml'),
    )


@lru_cache(maxsize=None)
def calendar_days(calendar: str) -> dict[date, BuiltDay]:
    snapshots = [s for s in read_snapshots(DATA / 'calendar' / 'raw') if s.calendar == calendar]
    result = build(snapshots, catalog())
    assert result.ok, result.problems[:5]
    return {d.date: d for d in result.days}


@lru_cache(maxsize=1)
def categories() -> dict[str, frozenset[str]]:
    return {key: frozenset(e.categories) for key, e in catalog().entries.items()}


def day(day: date, diocese: str = 'czech') -> DayResult:
    ctx = day_ctx(calendar_days(CALENDAR_OF[diocese]), day, diocese, categories())
    assert ctx is not None, f'no calendar data for {day}'
    return recommend(ctx, snapshot())


def date_of(celebration_key: str, year: int, diocese: str = 'czech') -> date:
    for d, built in sorted(calendar_days(CALENDAR_OF[diocese]).items()):
        if d.year == year and any(o.celebration_key == celebration_key for o in built.occurrences):
            return d
    raise LookupError(f'{celebration_key} not found in {year}')
