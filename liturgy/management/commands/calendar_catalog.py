"""Check (or extend) data/liturgy/celebrations.yaml against the raw snapshots. No DB access."""
from __future__ import annotations

from argparse import ArgumentParser
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from liturgy.catalog import Catalog
from liturgy.categorize import suggest_categories
from liturgy.days import unknown_titles
from liturgy.snapshot import read_snapshots


class Command(BaseCommand):
    help = (
        'Check that every non-feria title in the raw snapshots maps to a celebration in the catalog. '
        'With --register-new, add unknown titles to the catalog and print possible duplicates for review.'
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('--register-new', action='store_true', help='add unknown titles to the catalog')
        parser.add_argument(
            '--suggest-categories',
            action='store_true',
            help='fill in guessed categories for unreviewed entries that have none (review them afterwards)',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        path = settings.CANTICA_CELEBRATIONS_FILE
        catalog = Catalog.load(path)
        if options['suggest_categories']:
            filled = 0
            for entry in catalog.entries.values():
                if not entry.categories_reviewed and not entry.categories:
                    entry.categories = suggest_categories(entry.name)
                    filled += bool(entry.categories)
            catalog.save(path)
            self.stdout.write(self.style.SUCCESS(f'Suggested categories for {filled} celebrations; please review.'))
            return
        snapshots = list(read_snapshots(settings.CANTICA_RAW_CALENDAR_DIR))
        unknown = unknown_titles(snapshots, catalog)

        if not unknown:
            self.stdout.write(self.style.SUCCESS(f'All titles are known ({len(catalog)} celebrations).'))
            return

        if not options['register_new']:
            for title, places in sorted(unknown.items()):
                more = ', …' if len(places) > 1 else ''
                self.stderr.write(f'  unknown: {title!r} ({places[0]}{more})')
            raise CommandError(f'{len(unknown)} unknown titles; run with --register-new and review the diff')

        added = [catalog.register(title) for title in sorted(unknown)]
        catalog.save(path)
        self.stdout.write(self.style.SUCCESS(f'Added {len(added)} celebrations to {path}'))
        for entry in added:
            self.stdout.write(f'  + {entry.key}')
            for hint in catalog.duplicate_hints(entry):
                self.stdout.write(f'      possible duplicate of {hint.existing_key} (similarity {hint.similarity})')
