"""Rules as stored in data/curated/curation.yaml (and edited in the admin). Pure: no Django.

YAML shape (only non-default fields are written):

    - when: {celebration: sv-prokopa-opata}      # celebration / category / period / season,
                                                 # cycles: 'AC', day: sunday|weekday, min_rank, dioceses: [olm]
      parts: [entrance]
      kind: songs                                # songs (default) | neighbours | note | silence
      strength: recommended                      # prescribed | recommended (default) | alternative | avoid
      songs: 838/5                               # engine.refs syntax
      note: …                                    # shown to users
      internal: …                                # admin only
      page: 38                                   # Direktář page; omitted = doporučení autora
      position: 3810
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from engine.refs import RefError, parse_targets, unknown_references
from engine.vocab import DAY_KIND_KEYS, KIND_KEYS, MIN_RANK_KEYS, PART_KEYS, STRENGTH_KEYS
from liturgy.constants import CATEGORY_KEYS, DIOCESES, SEASON_KEYS

DIOCESE_CODES = frozenset(d.code for d in DIOCESES)
SCOPE_FIELDS = ('celebration', 'category', 'period', 'season')


@dataclass
class RuleRecord:
    parts: list[str] = field(default_factory=list)
    kind: str = 'songs'
    strength: str = 'recommended'
    songs: str = ''
    celebration: str = ''
    category: str = ''
    period: str = ''
    season: str = ''
    cycles: str = ''
    day: str = ''
    min_rank: str = ''
    dioceses: list[str] = field(default_factory=list)
    window_days: int = 7
    note: str = ''
    internal: str = ''
    page: int | None = None
    position: int = 0
    active: bool = True
    id: int | None = None  # DB id; never written to YAML

    def sort_key(self) -> tuple:
        return (self.position, self.celebration, self.category, self.period, self.season, self.songs)

    def to_dict(self) -> dict:  # noqa: C901
        names = (*SCOPE_FIELDS, 'cycles', 'day', 'min_rank')
        when = {name: getattr(self, name) for name in names if getattr(self, name)}
        if self.dioceses:
            when['dioceses'] = sorted(self.dioceses)
        data: dict = {}
        if when:
            data['when'] = when
        if self.parts:
            data['parts'] = list(self.parts)
        if self.kind != 'songs':
            data['kind'] = self.kind
        if self.kind in ('songs', 'neighbours') and self.strength != 'recommended':
            data['strength'] = self.strength
        if self.songs:
            data['songs'] = self.songs
        if self.kind == 'neighbours' and self.window_days != 7:
            data['window_days'] = self.window_days
        for name in ('note', 'internal'):
            if getattr(self, name):
                data[name] = getattr(self, name)
        if self.page is not None:
            data['page'] = self.page
        data['position'] = self.position
        if not self.active:
            data['active'] = False
        return data

    @classmethod
    def from_dict(cls, data: dict) -> RuleRecord:
        when = data.get('when') or {}
        if not isinstance(when, dict):
            raise TypeError('when must be a mapping')
        return cls(
            parts=[str(p) for p in data.get('parts') or []],
            kind=str(data.get('kind') or 'songs'),
            strength=str(data.get('strength') or 'recommended'),
            songs=str(data.get('songs') or ''),
            celebration=str(when.get('celebration') or ''),
            category=str(when.get('category') or ''),
            period=str(when.get('period') or ''),
            season=str(when.get('season') or ''),
            cycles=str(when.get('cycles') or ''),
            day=str(when.get('day') or ''),
            min_rank=str(when.get('min_rank') or ''),
            dioceses=[str(d) for d in when.get('dioceses') or []],
            window_days=int(data.get('window_days') or 7),
            note=str(data.get('note') or ''),
            internal=str(data.get('internal') or ''),
            page=int(data['page']) if data.get('page') is not None else None,
            position=int(data.get('position') or 0),
            active=bool(data.get('active', True)),
        )

    @property
    def label(self) -> str:
        scope = next((f'{n}={getattr(self, n)}' for n in SCOPE_FIELDS if getattr(self, n)), 'global')
        return f'rule {self.position} ({scope}, {",".join(self.parts) or "-"}: {self.songs or self.kind})'

    def problems(self, codes: Iterable[str], groups: dict[str, Iterable[str]]) -> list[str]:  # noqa: C901
        """Syntax and catalog references (celebrations and periods are checked by lint)."""
        where = self.label
        problems = []
        unknown_parts = [p for p in self.parts if p not in PART_KEYS]
        if unknown_parts:
            problems.append(f'{where}: unknown parts {unknown_parts}')
        if self.kind not in KIND_KEYS:
            problems.append(f'{where}: unknown kind {self.kind!r}')
        if self.strength not in STRENGTH_KEYS:
            problems.append(f'{where}: unknown strength {self.strength!r}')
        if self.kind in ('songs', 'neighbours', 'silence') and not self.parts:
            problems.append(f'{where}: parts are required')
        if self.kind == 'note' and not self.note:
            problems.append(f'{where}: a note rule needs a note')
        if self.kind == 'songs':
            if not self.songs:
                problems.append(f'{where}: songs are required')
            try:
                problems.extend(f'{where}: {p}' for p in unknown_references(parse_targets(self.songs), codes, groups))
            except RefError as exc:
                problems.append(f'{where}: {exc}')
        elif self.songs:
            problems.append(f'{where}: only kind=songs takes songs')
        if self.category and self.category not in CATEGORY_KEYS:
            problems.append(f'{where}: unknown category {self.category!r}')
        if self.season and self.season not in SEASON_KEYS:
            problems.append(f'{where}: unknown season {self.season!r}')
        if self.cycles and (set(self.cycles) - set('ABC') or len(set(self.cycles)) != len(self.cycles)):
            problems.append(f'{where}: cycles must be letters from ABC')
        if self.day not in DAY_KIND_KEYS:
            problems.append(f'{where}: day must be sunday or weekday')
        if self.min_rank not in MIN_RANK_KEYS:
            problems.append(f'{where}: unknown min_rank {self.min_rank!r}')
        unknown_dioceses = sorted(set(self.dioceses) - DIOCESE_CODES)
        if unknown_dioceses:
            problems.append(f'{where}: unknown dioceses {unknown_dioceses}')
        if self.window_days < 1:
            problems.append(f'{where}: window_days must be positive')
        return problems
