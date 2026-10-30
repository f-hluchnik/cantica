"""Write a validated calendar build into the DB (the Django side of calendar_build)."""
from __future__ import annotations

import hashlib
import logging
from datetime import date
from pathlib import Path

from django.db import transaction

from liturgy.catalog import Catalog
from liturgy.days import BuildResult
from liturgy.models import CalendarBuild, CalendarDay, Category, Celebration, CelebrationAlias, Diocese, Occurrence

logger = logging.getLogger(__name__)


class BuildError(RuntimeError):
    pass


def source_digest(raw_dir: Path, catalog_file: Path) -> str:
    """Hash of every input file (paths + contents), to skip rebuilds when nothing changed."""
    digest = hashlib.sha256()
    files = sorted(raw_dir.glob('*/*.json')) + ([catalog_file] if catalog_file.exists() else [])
    for path in files:
        digest.update(str(path.relative_to(path.parents[1])).encode())
        digest.update(b'\0')
        digest.update(path.read_bytes())
        digest.update(b'\0')
    return digest.hexdigest()


def latest_build() -> CalendarBuild | None:
    return CalendarBuild.objects.order_by('-built_at', '-id').first()


def needs_rebuild(digest: str) -> bool:
    build = latest_build()
    return build is None or build.source_digest != digest


def coverage(result: BuildResult) -> tuple[date, date]:
    """(first date, last date covered by EVERY calendar)."""
    last_by_calendar: dict[str, date] = {}
    first = min(d.date for d in result.days)
    for day in result.days:
        if day.date > last_by_calendar.get(day.calendar, date.min):
            last_by_calendar[day.calendar] = day.date
    return first, min(last_by_calendar.values())


@transaction.atomic
def apply_build(result: BuildResult, catalog: Catalog, digest: str) -> CalendarBuild:
    if not result.ok:
        raise BuildError('refusing to apply a build with problems')
    if not result.days:
        raise BuildError('no calendar data found')

    dioceses = {d.calapi_calendar: d for d in Diocese.objects.all()}
    unknown_calendars = sorted({d.calendar for d in result.days} - set(dioceses))
    if unknown_calendars:
        raise BuildError(f'snapshots for calendars without a diocese: {unknown_calendars}')

    _sync_celebrations(catalog)

    Occurrence.objects.all().delete()
    CalendarDay.objects.all().delete()
    Celebration.objects.exclude(key__in=list(catalog.entries)).delete()  # PROTECT stops this if still referenced

    CalendarDay.objects.bulk_create(
        [
            CalendarDay(
                diocese=dioceses[d.calendar],
                date=d.date,
                season=d.season,
                season_week=d.season_week,
                sunday_cycle=d.sunday_cycle,
                ferial_cycle=d.ferial_cycle,
            )
            for d in result.days
        ],
        batch_size=1000,
    )
    day_ids = {
        (diocese_id, day): pk
        for pk, diocese_id, day in CalendarDay.objects.values_list('pk', 'diocese_id', 'date')
    }
    Occurrence.objects.bulk_create(
        [
            Occurrence(
                day_id=day_ids[(dioceses[d.calendar].code, d.date)],
                position=o.position,
                celebration_id=o.celebration_key,
                title=o.title,
                rank_label=o.rank_label,
                rank_num=o.rank_num,
                colour=o.colour,
            )
            for d in result.days
            for o in d.occurrences
        ],
        batch_size=2000,
    )

    first, last = coverage(result)
    build = CalendarBuild.objects.create(source_digest=digest, first_date=first, last_date=last, days=len(result.days))
    logger.info('calendar build applied: %s days, %s..%s', len(result.days), first, last)
    return build


def _sync_celebrations(catalog: Catalog) -> None:
    categories = {c.key: c for c in Category.objects.all()}
    missing = sorted({c for e in catalog.entries.values() for c in e.categories} - set(categories))
    if missing:
        raise BuildError(f'catalog uses categories missing in the DB: {missing}')

    existing = {c.key: c for c in Celebration.objects.all()}
    to_create, to_update = [], []
    for entry in catalog.entries.values():
        celebration = existing.get(entry.key)
        if celebration is None:
            to_create.append(Celebration(key=entry.key, name=entry.name, categories_reviewed=entry.categories_reviewed))
        elif (celebration.name, celebration.categories_reviewed) != (entry.name, entry.categories_reviewed):
            celebration.name = entry.name
            celebration.categories_reviewed = entry.categories_reviewed
            to_update.append(celebration)
    Celebration.objects.bulk_create(to_create, batch_size=500)
    Celebration.objects.bulk_update(to_update, ['name', 'categories_reviewed'], batch_size=500)

    through = Celebration.categories.through
    through.objects.all().delete()
    through.objects.bulk_create([
        through(celebration_id=entry.key, category_id=category)
        for entry in catalog.entries.values()
        for category in entry.categories
    ])

    CelebrationAlias.objects.all().delete()
    CelebrationAlias.objects.bulk_create([
        CelebrationAlias(celebration_id=entry.key, title=alias)
        for entry in catalog.entries.values()
        for alias in entry.aliases
    ])
