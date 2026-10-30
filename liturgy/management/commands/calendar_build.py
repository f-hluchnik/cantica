"""Rebuild the calendar tables from data/ (raw snapshots + celebration catalog)."""
from __future__ import annotations

from argparse import ArgumentParser
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from liturgy import days
from liturgy.catalog import Catalog, CatalogError
from liturgy.dbbuild import BuildError, apply_build, needs_rebuild, source_digest
from liturgy.snapshot import SnapshotError, read_snapshots

MAX_PROBLEMS_SHOWN = 50


class Command(BaseCommand):
    help = 'Validate data/ and rebuild the calendar tables. Nothing is written if any problem is found.'

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('--force', action='store_true', help='rebuild even if the inputs did not change')
        parser.add_argument('--check', action='store_true', help='validate only, do not touch the DB')

    def handle(self, *args: Any, **options: Any) -> None:
        raw_dir = settings.CANTICA_RAW_CALENDAR_DIR
        catalog_file = settings.CANTICA_CELEBRATIONS_FILE
        digest = source_digest(raw_dir, catalog_file)

        if not (options['force'] or options['check']) and not needs_rebuild(digest):
            self.stdout.write('Calendar inputs unchanged; nothing to do.')
            return

        try:
            catalog = Catalog.load(catalog_file)
            snapshots = list(read_snapshots(raw_dir))
        except (CatalogError, SnapshotError) as exc:
            raise CommandError(str(exc)) from exc

        result = days.build(snapshots, catalog)
        if not result.ok:
            for problem in result.problems[:MAX_PROBLEMS_SHOWN]:
                self.stderr.write(f'  {problem}')
            if len(result.problems) > MAX_PROBLEMS_SHOWN:
                self.stderr.write(f'  … and {len(result.problems) - MAX_PROBLEMS_SHOWN} more')
            hint = ' (run calendar_catalog --register-new)' if result.unknown_titles else ''
            raise CommandError(f'{len(result.problems)} problems in calendar data{hint}')

        if options['check']:
            self.stdout.write(self.style.SUCCESS(f'OK: {len(result.days)} days, {len(catalog)} celebrations.'))
            return

        try:
            build = apply_build(result, catalog, digest)
        except BuildError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f'Built {build.days} days, {build.first_date} .. {build.last_date} (all calendars).',
        ))
