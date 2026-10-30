"""Named date ranges that rules can target (data/liturgy/periods.yaml). Pure module: must not import Django.

Kinds:
    fixed        {from: 'MM-DD', to: 'MM-DD'}      inclusive; may wrap the year end (12-25 .. 01-01)
    easter       {from: int, to: int}              days relative to Easter Sunday, inclusive
    season_week  {weeks: [int, ...]}               requires `season`
Every kind accepts an optional `season` that must also match.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

from liturgy import norms
from liturgy.constants import SEASON_KEYS

_KEY_RE = re.compile(r'^[a-z0-9]+(?:_[a-z0-9]+)*$')
_MMDD_RE = re.compile(r'^(\d{2})-(\d{2})$')
KINDS = ('fixed', 'easter', 'season_week')


class PeriodError(ValueError):
    pass


@dataclass(frozen=True)
class Period:
    key: str
    name: str
    kind: str
    start: object = None  # (month, day) for fixed, int for easter
    end: object = None
    weeks: tuple[int, ...] = ()
    season: str | None = None
    source_page: int | None = None
    description: str = ''

    def contains(self, day: date, season: str, season_week: int) -> bool:
        if self.season and season != self.season:
            return False
        if self.kind == 'fixed':
            md = (day.month, day.day)
            if self.start <= self.end:
                return self.start <= md <= self.end
            return md >= self.start or md <= self.end  # wraps the year end
        if self.kind == 'easter':
            offset = (day - norms.easter(day.year)).days
            return self.start <= offset <= self.end
        if self.kind == 'season_week':
            return season_week in self.weeks
        return False


@dataclass
class Periods:
    items: dict[str, Period] = field(default_factory=dict)

    def active(self, day: date, season: str, season_week: int) -> frozenset[str]:
        return frozenset(k for k, p in self.items.items() if p.contains(day, season, season_week))

    @classmethod
    def load(cls, path: Path) -> Periods:
        if not path.exists():
            return cls()
        return cls.loads(path.read_text(encoding='utf-8'), origin=str(path))

    @classmethod
    def loads(cls, text: str, origin: str = 'periods') -> Periods:
        data = yaml.safe_load(text) or []
        if not isinstance(data, list):
            raise PeriodError(f'{origin}: expected a list of periods')
        items: dict[str, Period] = {}
        for raw in data:
            period = _parse(raw, origin)
            if period.key in items:
                raise PeriodError(f'{origin}: duplicate period {period.key!r}')
            items[period.key] = period
        return cls(items)


def _mmdd(value: object, where: str) -> tuple[int, int]:
    match = _MMDD_RE.match(str(value))
    if not match:
        raise PeriodError(f'{where}: expected MM-DD, got {value!r}')
    month, day = int(match.group(1)), int(match.group(2))
    try:
        date(2000, month, day)  # leap year: 02-29 allowed
    except ValueError as exc:
        raise PeriodError(f'{where}: invalid date {value!r}') from exc
    return month, day


def _parse(raw: object, origin: str) -> Period:
    if not isinstance(raw, dict) or 'key' not in raw or 'kind' not in raw:
        raise PeriodError(f'{origin}: each period needs key and kind')
    key, kind = str(raw['key']), str(raw['kind'])
    where = f'{origin} {key}'
    if not _KEY_RE.match(key):
        raise PeriodError(f'{where}: key must be lowercase words joined by "_"')
    season = raw.get('season')
    if season is not None and season not in SEASON_KEYS:
        raise PeriodError(f'{where}: unknown season {season!r}')
    common = {
        'key': key,
        'name': str(raw.get('name') or key),
        'kind': kind,
        'season': season,
        'source_page': raw.get('source_page'),
        'description': str(raw.get('description') or ''),
    }
    if kind == 'fixed':
        return Period(start=_mmdd(raw.get('from'), where), end=_mmdd(raw.get('to'), where), **common)
    if kind == 'easter':
        try:
            start, end = int(raw['from']), int(raw['to'])
        except (KeyError, TypeError, ValueError) as exc:
            raise PeriodError(f'{where}: easter periods need integer from/to') from exc
        if start > end:
            raise PeriodError(f'{where}: from is after to')
        return Period(start=start, end=end, **common)
    if kind == 'season_week':
        weeks = raw.get('weeks')
        if not season or not isinstance(weeks, list) or not weeks:
            raise PeriodError(f'{where}: season_week periods need season and a list of weeks')
        return Period(weeks=tuple(int(w) for w in weeks), **common)
    raise PeriodError(f'{where}: unknown kind {kind!r} (expected one of {KINDS})')
