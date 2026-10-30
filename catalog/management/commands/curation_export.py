"""Export curated data (songs, groups) from the DB to data/curated/curation.yaml."""
from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from catalog.dbsync import export_curation, mark_exported


class Command(BaseCommand):
    help = 'Export curated data from the DB to YAML and mark the DB as exported.'

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('--path', type=Path, help='output file (default: data/curated/curation.yaml)')
        # Not '--stdout': its dest would collide with BaseCommand's own `stdout` option (the output stream).
        parser.add_argument(
            '--print',
            action='store_true',
            dest='print_yaml',
            help='print the YAML instead of writing a file',
        )
        parser.add_argument(
            '--no-mark',
            action='store_true',
            help='do not mark the DB as exported (the caller marks it later with --mark-exported)',
        )
        parser.add_argument(
            '--mark-exported',
            type=int,
            metavar='VERSION',
            help='only record that VERSION reached git (no export)',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options['mark_exported'] is not None:
            try:
                state = mark_exported(options['mark_exported'])
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
            self.stdout.write(f'exported_version = {state.exported_version} (DB version {state.version})')
            return

        curation = export_curation(mark=not options['no_mark'])
        if options['print_yaml']:
            self.stdout.write(curation.dumps(), ending='')
            return
        path = options['path'] or settings.CANTICA_CURATION_FILE
        changed = curation.save(path)
        state = 'written' if changed else 'unchanged'
        self.stdout.write(self.style.SUCCESS(
            f'{path}: {state} (version {curation.version}, {len(curation.songs)} songs, {len(curation.groups)} groups)',
        ))
