"""Django side of the engine: snapshot from the DB, day context from calendar rows, cached results."""
from __future__ import annotations

import threading
from collections import OrderedDict
from datetime import date

from django.conf import settings

from catalog.dbsync import db_to_curation
from catalog.models import CurationState
from engine.context import context_range, day_ctx
from engine.load import snapshot_from_curation
from engine.model import Snapshot
from engine.recommend import DayResult, recommend
from liturgy.days import BuiltDay, BuiltOccurrence
from liturgy.dbbuild import latest_build
from liturgy.models import CalendarDay, Celebration
from liturgy.periods import Periods

_lock = threading.Lock()
_snapshot: tuple[tuple, Snapshot, dict[str, frozenset[str]]] | None = None
_results: OrderedDict[tuple, DayResult | None] = OrderedDict()
RESULT_CACHE_SIZE = 512


def cache_key() -> tuple:
    """Changes whenever curated data (admin) or the calendar (calendar_build) changes."""
    build = latest_build()
    return (CurationState.current().version, build.pk if build else None)


def _categories() -> dict[str, frozenset[str]]:
    result: dict[str, set[str]] = {}
    for key, category in Celebration.categories.through.objects.values_list('celebration_id', 'category_id'):
        result.setdefault(key, set()).add(category)
    return {k: frozenset(v) for k, v in result.items()}


def current_snapshot() -> tuple[Snapshot, dict[str, frozenset[str]]]:
    global _snapshot  # per-process cache, rebuilt when the key changes
    key = cache_key()
    with _lock:
        if _snapshot is None or _snapshot[0] != key:
            snap = snapshot_from_curation(db_to_curation(), Periods.load(settings.CANTICA_PERIODS_FILE), version=key)
            _snapshot = (key, snap, _categories())
            _results.clear()
        return _snapshot[1], _snapshot[2]


def built_days(diocese_code: str, start: date, end: date) -> dict[date, BuiltDay]:
    rows = (
        CalendarDay.objects
        .filter(diocese_id=diocese_code, date__range=(start, end))
        .select_related('diocese')
        .prefetch_related('occurrences')
    )
    return {
        row.date: BuiltDay(
            calendar=row.diocese.calapi_calendar,
            date=row.date,
            season=row.season,
            season_week=row.season_week,
            sunday_cycle=row.sunday_cycle,
            ferial_cycle=row.ferial_cycle,
            occurrences=tuple(
                BuiltOccurrence(
                    position=o.position,
                    title=o.title,
                    rank_label=o.rank_label,
                    rank_num=o.rank_num,
                    colour=o.colour,
                    celebration_key=o.celebration_id,
                )
                for o in sorted(row.occurrences.all(), key=lambda o: o.position)
            ),
        )
        for row in rows
    }


def day_result(diocese_code: str, day: date) -> DayResult | None:
    snap, categories = current_snapshot()
    key = (snap.version, diocese_code, day)
    with _lock:
        if key in _results:
            _results.move_to_end(key)
            return _results[key]
    start, end = context_range(day)
    ctx = day_ctx(built_days(diocese_code, start, end), day, diocese_code, categories)
    result = recommend(ctx, snap) if ctx else None
    with _lock:
        _results[key] = result
        while len(_results) > RESULT_CACHE_SIZE:
            _results.popitem(last=False)
    return result


def reset_caches() -> None:
    global _snapshot
    with _lock:
        _snapshot = None
        _results.clear()
