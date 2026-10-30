"""Raw calendar snapshots: one JSON file per calendar and month, committed to git.

The file keeps the calapi payload as received (validated, re-serialized with stable formatting),
so git diffs show real changes only. Pure module: must not import Django.

File layout: data/calendar/raw/<calendar>/<yyyy-mm>.json
"""
from __future__ import annotations

import calendar as _calendar
import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

WEEKDAYS = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')


class SnapshotError(ValueError):
    """The payload or file does not have the expected shape."""


@dataclass(frozen=True)
class RawOccurrence:
    title: str
    colour: str
    rank_label: str
    rank_num: Decimal


@dataclass(frozen=True)
class RawDay:
    date: date
    season: str
    season_week: int
    weekday: str
    occurrences: tuple[RawOccurrence, ...]


@dataclass(frozen=True)
class MonthSnapshot:
    calendar: str
    year: int
    month: int
    payload: tuple[dict[str, Any], ...]  # days exactly as received from calapi

    @property
    def label(self) -> str:
        return f'{self.year:04d}-{self.month:02d}'

    @classmethod
    def from_api(cls, calendar: str, year: int, month: int, payload: Any) -> MonthSnapshot:
        snapshot = cls(calendar=calendar, year=year, month=month, payload=_check_payload(year, month, payload))
        snapshot.days()  # full validation of every day
        return snapshot

    def days(self) -> list[RawDay]:
        return [_parse_day(item, f'{self.calendar} {self.label}') for item in self.payload]

    def dumps(self) -> str:
        """Stable serialization: one day per line, sorted keys, UTF-8."""
        lines = [
            '{',
            f'  "calendar": {json.dumps(self.calendar)},',
            f'  "month": {json.dumps(self.label)},',
            '  "days": [',
        ]
        day_lines = [
            '    ' + json.dumps(day, ensure_ascii=False, sort_keys=True, separators=(', ', ': '))
            for day in self.payload
        ]
        lines.append(',\n'.join(day_lines))
        lines.extend(['  ]', '}', ''])
        return '\n'.join(lines)

    @classmethod
    def loads(cls, text: str, origin: str = '') -> MonthSnapshot:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SnapshotError(f'{origin}: invalid JSON: {exc}') from exc
        try:
            calendar = data['calendar']
            year_str, month_str = data['month'].split('-')
            days = data['days']
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise SnapshotError(f'{origin}: missing calendar/month/days') from exc
        return cls.from_api(calendar, int(year_str), int(month_str), days)


def snapshot_path(raw_dir: Path, calendar: str, year: int, month: int) -> Path:
    return raw_dir / calendar / f'{year:04d}-{month:02d}.json'


def write_snapshot(raw_dir: Path, snapshot: MonthSnapshot) -> bool:
    """Write the snapshot; return True if the file was created or changed."""
    path = snapshot_path(raw_dir, snapshot.calendar, snapshot.year, snapshot.month)
    text = snapshot.dumps()
    if path.exists() and path.read_text(encoding='utf-8') == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return True


def read_snapshots(raw_dir: Path) -> Iterator[MonthSnapshot]:
    """All snapshots under raw_dir, ordered by calendar and month."""
    for path in sorted(raw_dir.glob('*/*.json')):
        snapshot = MonthSnapshot.loads(path.read_text(encoding='utf-8'), origin=str(path))
        if path.parent.name != snapshot.calendar or path.stem != snapshot.label:
            raise SnapshotError(f'{path}: content is {snapshot.calendar} {snapshot.label}')
        yield snapshot


def _check_payload(year: int, month: int, payload: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(payload, list):
        raise SnapshotError(f'{year:04d}-{month:02d}: expected a list of days')
    expected = [date(year, month, d).isoformat() for d in range(1, _calendar.monthrange(year, month)[1] + 1)]
    got = [item.get('date') if isinstance(item, dict) else None for item in payload]
    if got != expected:
        missing = sorted(set(expected) - {g for g in got if g})
        extra = sorted({g for g in got if g} - set(expected))
        raise SnapshotError(
            f'{year:04d}-{month:02d}: days do not match the month (missing {missing}, unexpected {extra})',
        )
    return tuple(payload)


def _parse_day(item: dict[str, Any], origin: str) -> RawDay:
    item_date = item.get('date')
    where = f'{origin} {item_date}'
    try:
        day = date.fromisoformat(item['date'])
        season = item['season']
        season_week = int(item['season_week'])
        weekday = item['weekday']
        celebrations = item['celebrations']
    except (KeyError, TypeError, ValueError) as exc:
        raise SnapshotError(f'{where}: malformed day ({exc})') from exc
    if not isinstance(season, str) or not isinstance(weekday, str):
        raise SnapshotError(f'{where}: season/weekday must be strings')
    if weekday != WEEKDAYS[day.weekday()]:
        raise SnapshotError(f'{where}: weekday {weekday!r} does not match the date')
    if not isinstance(celebrations, list) or not celebrations:
        raise SnapshotError(f'{where}: no celebrations')
    occurrences = []
    for celebration in celebrations:
        try:
            occurrences.append(RawOccurrence(
                title=str(celebration['title']).strip(),
                colour=str(celebration['colour']),
                rank_label=str(celebration['rank']),
                rank_num=Decimal(str(celebration['rank_num'])),
            ))
        except (KeyError, TypeError, ArithmeticError) as exc:
            raise SnapshotError(f'{where}: malformed celebration ({exc})') from exc
    return RawDay(date=day, season=season, season_week=season_week, weekday=weekday, occurrences=tuple(occurrences))
