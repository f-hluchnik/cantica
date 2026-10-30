"""Celebration catalog: data/liturgy/celebrations.yaml. Pure module: must not import Django.

The catalog is the source of truth for celebration identity. It lives in git, next to the
calendar snapshots it describes; the DB only mirrors it (see calendar_build).

Entry fields:
    key         permanent identifier used by rules; may be shortened by hand until a rule uses it
    name        display name (normally the calapi title)
    aliases     other calapi titles of the same celebration (other dioceses, renamed titles)
    categories  keys from liturgy.constants.CATEGORIES
    categories_reviewed   true once a human checked the categories

Titles are matched by slug, so case, punctuation and diacritics never matter.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from liturgy.constants import CATEGORY_KEYS
from liturgy.keys import key_from_title, slugify_cs, title_similarity

_KEY_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')

HEADER = (
    '# Celebration catalog (source of truth for celebration identity).\n'
    '# Keys are permanent once a rule refers to them. Titles are matched by slug.\n'
    '# To merge two entries for the same celebration, move one title into the aliases of the other.\n'
)


class CatalogError(ValueError):
    pass


@dataclass
class Entry:
    key: str
    name: str
    aliases: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    categories_reviewed: bool = False

    def titles(self) -> list[str]:
        return [self.name, *self.aliases]

    def to_dict(self) -> dict:
        return {
            'key': self.key,
            'name': self.name,
            'aliases': list(self.aliases),
            'categories': list(self.categories),
            'categories_reviewed': self.categories_reviewed,
        }


@dataclass
class DuplicateHint:
    new_key: str
    existing_key: str
    similarity: float


class Catalog:
    def __init__(self, entries: list[Entry] | None = None) -> None:
        self.entries: dict[str, Entry] = {}
        self._index: dict[str, str] = {}
        for entry in entries or []:
            self.add(entry)

    def __len__(self) -> int:
        return len(self.entries)

    def add(self, entry: Entry) -> None:
        problems = _entry_problems(entry)
        if entry.key in self.entries:
            problems.append(f'duplicate key {entry.key!r}')
        for title in entry.titles():
            slug = slugify_cs(title)
            owner = self._index.get(slug)
            if owner is not None and owner != entry.key:
                problems.append(f'title {title!r} already belongs to {owner!r}')
        if problems:
            raise CatalogError(f'{entry.key}: ' + '; '.join(problems))
        self.entries[entry.key] = entry
        for title in entry.titles():
            self._index[slugify_cs(title)] = entry.key

    def resolve(self, title: str) -> str | None:
        return self._index.get(slugify_cs(title))

    def register(self, title: str) -> Entry:
        """Create an entry for an unknown title (key derived from the title, made unique)."""
        if self.resolve(title):
            raise CatalogError(f'{title!r} is already known')
        base = key_from_title(title)
        key, n = base, 2
        while key in self.entries:
            key, n = f'{base}-{n}', n + 1
        entry = Entry(key=key, name=title)
        self.add(entry)
        return entry

    def duplicate_hints(self, entry: Entry, threshold: float = 0.6) -> list[DuplicateHint]:
        hints = []
        for other in self.entries.values():
            if other.key == entry.key:
                continue
            score = max(title_similarity(entry.name, t) for t in other.titles())
            if score >= threshold:
                hints.append(DuplicateHint(entry.key, other.key, round(score, 2)))
        return sorted(hints, key=lambda h: -h.similarity)

    def sorted_entries(self) -> list[Entry]:
        return sorted(self.entries.values(), key=lambda e: e.key)

    # --- YAML -----------------------------------------------------------------------------

    @classmethod
    def load(cls, path: Path) -> Catalog:
        if not path.exists():
            return cls()
        data = yaml.safe_load(path.read_text(encoding='utf-8')) or []
        if not isinstance(data, list):
            raise CatalogError(f'{path}: expected a list of entries')
        entries = []
        for i, item in enumerate(data):
            if not isinstance(item, dict) or 'key' not in item or 'name' not in item:
                raise CatalogError(f'{path}: entry #{i + 1} needs at least key and name')
            entries.append(Entry(
                key=str(item['key']),
                name=str(item['name']),
                aliases=[str(a) for a in item.get('aliases') or []],
                categories=[str(c) for c in item.get('categories') or []],
                categories_reviewed=bool(item.get('categories_reviewed', False)),
            ))
        return cls(entries)

    def dumps(self) -> str:
        body = yaml.safe_dump(
            [e.to_dict() for e in self.sorted_entries()],
            allow_unicode=True,
            sort_keys=False,
            width=1000,
            default_flow_style=False,
        )
        return HEADER + body

    def save(self, path: Path) -> bool:
        text = self.dumps()
        if path.exists() and path.read_text(encoding='utf-8') == text:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return True


def _entry_problems(entry: Entry) -> list[str]:
    problems = []
    if not _KEY_RE.match(entry.key):
        problems.append('key must be lowercase ascii words joined by "-"')
    if not entry.name.strip():
        problems.append('empty name')
    unknown = sorted(set(entry.categories) - CATEGORY_KEYS)
    if unknown:
        problems.append(f'unknown categories {unknown}')
    return problems
