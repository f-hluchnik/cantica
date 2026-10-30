"""Curated data file data/curated/curation.yaml: songs, song groups and rules.

The DB is the source of truth (edited in the admin); this file is its export, kept in git for
review, backup and tests. Pure module: must not import Django.

Only non-default song fields are written, so the file stays short and diffs stay readable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from catalog.codes import SECTION_KEYS, code_sort_key, is_valid_code, is_valid_verses, verse_numbers
from catalog.rulerecords import RuleRecord

_KEY_RE = re.compile(r'^[a-z0-9]+(?:_[a-z0-9]+)*$')

HEADER = (
    '# Curated data exported from the DB (source of truth: the admin).\n'
    '# Import into an empty DB: python manage.py curation_import --if-empty\n'
    '# Song verse fields: null = not verified, "-" = none, "*" = as dedicated in Kancionál, "4,5" = these verses.\n'
)


class CurationError(ValueError):
    pass


@dataclass
class SongRecord:
    code: str
    title: str
    section: str
    mass_song: bool | None = None
    communion_verses: str | None = None
    recessional_verses: str | None = None
    verse_count: int | None = None
    reviewed: bool = False
    note: str = ''

    def to_dict(self) -> dict:
        data: dict = {'code': self.code, 'title': self.title, 'section': self.section}
        for name in ('mass_song', 'communion_verses', 'recessional_verses', 'verse_count'):
            value = getattr(self, name)
            if value is not None:
                data[name] = value
        if self.reviewed:
            data['reviewed'] = True
        if self.note:
            data['note'] = self.note
        return data


@dataclass
class GroupRecord:
    key: str
    name: str
    members: list[str] = field(default_factory=list)
    description: str = ''
    source_page: int | None = None

    def to_dict(self) -> dict:
        data: dict = {'key': self.key, 'name': self.name}
        if self.description:
            data['description'] = self.description
        if self.source_page is not None:
            data['source_page'] = self.source_page
        data['members'] = list(self.members)
        return data


@dataclass
class Curation:
    version: int = 0
    songs: list[SongRecord] = field(default_factory=list)
    groups: list[GroupRecord] = field(default_factory=list)
    rules: list[RuleRecord] = field(default_factory=list)

    def problems(self) -> list[str]:
        codes = {s.code for s in self.songs}
        groups = {g.key: g.members for g in self.groups}
        rule_problems = [p for r in self.rules for p in r.problems(codes, groups)]
        return self._song_problems() + self._group_problems(codes) + rule_problems

    def _song_problems(self) -> list[str]:
        problems: list[str] = []
        codes: set[str] = set()
        for song in self.songs:
            where = f'song {song.code!r}'
            if not is_valid_code(song.code):
                problems.append(f'{where}: invalid code')
            if song.code in codes:
                problems.append(f'{where}: duplicate code')
            codes.add(song.code)
            if not song.title.strip():
                problems.append(f'{where}: empty title')
            if song.section not in SECTION_KEYS:
                problems.append(f'{where}: unknown section {song.section!r}')
            if song.verse_count is not None and song.verse_count < 1:
                problems.append(f'{where}: verse_count must be positive')
            for name in ('communion_verses', 'recessional_verses'):
                spec = getattr(song, name)
                if not is_valid_verses(spec):
                    problems.append(f'{where}: invalid {name} {spec!r}')
                elif song.verse_count is not None and any(v > song.verse_count for v in verse_numbers(spec)):
                    problems.append(f'{where}: {name} {spec!r} exceeds verse_count {song.verse_count}')
        return problems

    def _group_problems(self, codes: set[str]) -> list[str]:
        problems: list[str] = []
        keys: set[str] = set()
        for group in self.groups:
            where = f'group {group.key!r}'
            if not _KEY_RE.match(group.key):
                problems.append(f'{where}: key must be lowercase words joined by "_"')
            if group.key in keys:
                problems.append(f'{where}: duplicate key')
            keys.add(group.key)
            if not group.members:
                problems.append(f'{where}: no members')
            unknown = [m for m in group.members if m not in codes]
            if unknown:
                problems.append(f'{where}: unknown songs {unknown}')
            if len(set(group.members)) != len(group.members):
                problems.append(f'{where}: duplicate members')
        return problems

    def validate(self) -> None:
        problems = self.problems()
        if problems:
            raise CurationError('; '.join(problems))

    # --- YAML -----------------------------------------------------------------------------

    def dumps(self) -> str:
        data = {
            'version': self.version,
            'groups': [g.to_dict() for g in sorted(self.groups, key=lambda g: g.key)],
            'songs': [s.to_dict() for s in sorted(self.songs, key=lambda s: code_sort_key(s.code))],
            'rules': [r.to_dict() for r in sorted(self.rules, key=RuleRecord.sort_key)],
        }
        body = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000, default_flow_style=None)
        return HEADER + body

    def save(self, path: Path) -> bool:
        text = self.dumps()
        if path.exists() and path.read_text(encoding='utf-8') == text:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return True

    @classmethod
    def loads(cls, text: str, origin: str = 'curation') -> Curation:
        try:
            data = yaml.safe_load(text) or {}
        except yaml.YAMLError as exc:
            raise CurationError(f'{origin}: invalid YAML: {exc}') from exc
        if not isinstance(data, dict):
            raise CurationError(f'{origin}: expected a mapping with version, groups, songs')
        try:
            songs = [
                SongRecord(
                    code=str(s['code']),
                    title=str(s['title']),
                    section=str(s['section']),
                    mass_song=s.get('mass_song'),
                    communion_verses=_opt_str(s.get('communion_verses')),
                    recessional_verses=_opt_str(s.get('recessional_verses')),
                    verse_count=s.get('verse_count'),
                    reviewed=bool(s.get('reviewed', False)),
                    note=str(s.get('note') or ''),
                )
                for s in data.get('songs') or []
            ]
            groups = [
                GroupRecord(
                    key=str(g['key']),
                    name=str(g['name']),
                    members=[str(m) for m in g.get('members') or []],
                    description=str(g.get('description') or ''),
                    source_page=g.get('source_page'),
                )
                for g in data.get('groups') or []
            ]
            rules = [RuleRecord.from_dict(r) for r in data.get('rules') or []]
            version = int(data.get('version', 0))
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise CurationError(f'{origin}: malformed entry ({exc})') from exc
        return cls(version=version, songs=songs, groups=groups, rules=rules)

    @classmethod
    def load(cls, path: Path) -> Curation:
        if not path.exists():
            return cls()
        return cls.loads(path.read_text(encoding='utf-8'), origin=str(path))


def _opt_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
