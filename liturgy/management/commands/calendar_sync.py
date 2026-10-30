"""Fetch calendar months from calapi into data/calendar/raw/ (files only, no DB access)."""
from __future__ import annotations

import re
from argparse import ArgumentParser, ArgumentTypeError
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from liturgy.calapi import CalapiClient
from liturgy.constants import CALAPI_CALENDARS
from liturgy.sync import add_months, month_range, sync

_MONTH_RE = re.compile(r'^(\d{4})-(\d{2})$')


def _month(value: str) -> tuple[int, int]:
    match = _MONTH_RE.match(value)
    if not match or not 1 <= int(match.group(2)) <= 12:
        raise ArgumentTypeError(f'expected YYYY-MM, got {value!r}')
    return int(match.group(1)), int(match.group(2))


class Command(BaseCommand):
    help = 'Fetch calendar months from calapi into raw snapshot files. Writes only files that changed.'

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('--start', type=_month, help='first month YYYY-MM (default: last month)')
        parser.add_argument('--end', type=_month, help='last month YYYY-MM (default: 24 months ahead)')
        parser.add_argument(
            '--calendar',
            action='append',
            choices=CALAPI_CALENDARS,
            help='calendar to fetch (repeatable; default: all)',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        today = timezone.localdate()
        start = options['start'] or add_months(today.year, today.month, -1)
        end = options['end'] or add_months(today.year, today.month, 24)
        if start > end:
            raise CommandError('--start is after --end')
        calendars = options['calendar'] or list(CALAPI_CALENDARS)
        months = list(month_range(start, end))
        self.stdout.write(f'Fetching {len(calendars)} calendars x {len(months)} months '
                          f'({start[0]}-{start[1]:02d} .. {end[0]}-{end[1]:02d})')

        report = sync(CalapiClient(), settings.CANTICA_RAW_CALENDAR_DIR, calendars, months)

        self.stdout.write(f'changed: {len(report.changed)}, unchanged: {len(report.unchanged)}, '
                          f'errors: {len(report.errors)}')
        for label in report.changed:
            self.stdout.write(f'  changed {label}')
        if report.errors:
            for error in report.errors:
                self.stderr.write(f'  error {error}')
            raise CommandError(f'{len(report.errors)} months could not be fetched (other files were written)')
