"""Import data/curated/curation.yaml into the DB (songs, groups, rules)."""
from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import ProtectedError

from catalog.curation import Curation, CurationError
from catalog.dbsync import ImportRefusedError, import_curation, is_empty


class Command(BaseCommand):
    help = (
        'Replace the curated tables with the YAML file. Refuses if the DB has unexported changes '
        '(use --force to discard them). With --if-empty, only imports into an empty DB.'
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('--path', type=Path, help='input file (default: data/curated/curation.yaml)')
        parser.add_argument('--if-empty', action='store_true', help='do nothing unless the DB has no songs')
        parser.add_argument('--force', action='store_true', help='discard unexported changes in the DB')

    def handle(self, *args: Any, **options: Any) -> None:
        if options['if_empty'] and not is_empty():
            self.stdout.write('Curated data already present; nothing to do.')
            return
        path = options['path'] or settings.CANTICA_CURATION_FILE
        if not path.exists():
            raise CommandError(f'{path} does not exist')
        try:
            curation = Curation.load(path)
            result = import_curation(curation, force=options['force'])
        except (CurationError, ImportRefusedError) as exc:
            raise CommandError(str(exc)) from exc
        except ProtectedError as exc:
            raise CommandError(f'cannot delete songs still in use: {exc.protected_objects}') from exc
        self.stdout.write(self.style.SUCCESS(
            f'{path}: {result} ({len(curation.songs)} songs, {len(curation.groups)} groups, '
            f'{len(curation.rules)} rules)',
        ))
