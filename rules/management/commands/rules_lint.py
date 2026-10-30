"""Lint the rules (from the DB, or from the YAML with --file) against the calendar data in data/."""
from __future__ import annotations

from argparse import ArgumentParser
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from catalog.curation import Curation
from catalog.dbsync import db_to_curation
from engine.lint import lint
from liturgy.catalog import Catalog
from liturgy.constants import DIOCESES
from liturgy.days import build
from liturgy.periods import Periods
from liturgy.snapshot import read_snapshots


class Command(BaseCommand):
    help = 'Check the ruleset: references, contradictions, rules that never apply; --coverage lists the gaps.'

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('--file', action='store_true', help='lint data/curated/curation.yaml instead of the DB')
        parser.add_argument('--coverage', action='store_true', help='list celebrations without ▲/■ mass songs')

    def handle(self, *args: Any, **options: Any) -> None:
        curation = Curation.load(settings.CANTICA_CURATION_FILE) if options['file'] else db_to_curation()
        celebrations = Catalog.load(settings.CANTICA_CELEBRATIONS_FILE)
        snapshots = list(read_snapshots(settings.CANTICA_RAW_CALENDAR_DIR))
        built = build(snapshots, celebrations)
        if not built.ok:
            raise CommandError('calendar data has problems; run calendar_build --check')
        by_calendar: dict[str, list] = {}
        for day in built.days:
            by_calendar.setdefault(day.calendar, []).append(day)
        days = {d.code: by_calendar[d.calapi_calendar] for d in DIOCESES if d.calapi_calendar in by_calendar}
        categories = {key: frozenset(e.categories) for key, e in celebrations.entries.items()}

        report = lint(curation, celebrations, Periods.load(settings.CANTICA_PERIODS_FILE), days, categories)

        for line in report.warnings:
            self.stdout.write(self.style.WARNING(f'warning: {line}'))
        for line in report.overrides:
            self.stdout.write(f'override (author rule over Direktář): {line}')
        if options['coverage']:
            self.stdout.write(f'\nCelebrations (memorial or higher) without a ▲/■ mass song: {len(report.gaps)}')
            for gap in report.gaps:
                self.stdout.write(f'  {gap.first_date}  {gap.title}  ({gap.celebration_key}, {gap.count}×)')
        for line in report.errors:
            self.stderr.write(f'error: {line}')
        if report.errors:
            raise CommandError(f'{len(report.errors)} errors')
        self.stdout.write(self.style.SUCCESS(
            f'OK: {len(curation.rules)} rules, {report.days_checked} days checked, {len(report.warnings)} warnings.',
        ))
