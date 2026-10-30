"""Fetch calapi months into raw snapshot files. Pure module: must not import Django."""
from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from liturgy.calapi import CalapiClient, CalapiError
from liturgy.snapshot import MonthSnapshot, SnapshotError, write_snapshot

logger = logging.getLogger(__name__)


@dataclass
class SyncReport:
    changed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def month_range(start: tuple[int, int], end: tuple[int, int]) -> Iterator[tuple[int, int]]:
    """Inclusive range of (year, month)."""
    year, month = start
    while (year, month) <= end:
        yield year, month
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def sync(
    client: CalapiClient,
    raw_dir: Path,
    calendars: Iterable[str],
    months: Iterable[tuple[int, int]],
) -> SyncReport:
    """Fetch every (calendar, month); write only files whose content changed. Never deletes files."""
    report = SyncReport()
    months = list(months)
    for calendar in calendars:
        for year, month in months:
            label = f'{calendar} {year:04d}-{month:02d}'
            try:
                payload = client.month(calendar, year, month)
                snapshot = MonthSnapshot.from_api(calendar, year, month, payload)
            except (CalapiError, SnapshotError) as exc:
                logger.error('sync failed for %s: %s', label, exc)
                report.errors.append(f'{label}: {exc}')
                continue
            if write_snapshot(raw_dir, snapshot):
                report.changed.append(label)
            else:
                report.unchanged.append(label)
    return report
