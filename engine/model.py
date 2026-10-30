"""Engine input data: the snapshot of curated data and the context of one day. Pure: no Django."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from catalog.codes import code_sort_key, has_verse
from engine.refs import Target, expand_target
from engine.vocab import SPECIFICITY, STRENGTH_RANK
from liturgy.constants import RANK_COMMEMORATION
from liturgy.periods import Periods

# --- curated data --------------------------------------------------------------------------


@dataclass(frozen=True)
class SongInfo:
    code: str
    title: str
    section: str
    mass_song: bool | None = None
    communion_verses: str | None = None
    recessional_verses: str | None = None

    @property
    def url(self) -> str:
        return f'https://kancional.cz/{self.code}'


@dataclass(frozen=True)
class GroupInfo:
    key: str
    name: str
    members: tuple[str, ...]


@dataclass(frozen=True)
class RuleInfo:
    id: int | str
    parts: tuple[str, ...]
    strength: str = 'recommended'
    kind: str = 'songs'
    targets: tuple[Target, ...] = ()
    celebration: str = ''
    category: str = ''
    period: str = ''
    season: str = ''
    occasion: str = ''
    cycles: frozenset[str] = frozenset()
    day_kind: str = ''
    min_rank: str = ''
    dioceses: frozenset[str] = frozenset()
    window_days: int = 7
    fallback: bool = False  # dropped when a more specific rule gives the part a song (p. 9: "pokud … neznáme")
    note: str = ''
    page: int | None = None
    position: int = 0

    @property
    def scope(self) -> str:
        for name in ('occasion', 'celebration', 'category', 'period', 'season'):
            if getattr(self, name):
                return name
        return 'global'

    @property
    def specificity(self) -> int:
        return SPECIFICITY[self.scope]

    @property
    def strength_rank(self) -> int:
        return STRENGTH_RANK.get(self.strength, 0)

    @property
    def source_label(self) -> str:
        return f'Direktář s. {self.page}' if self.page else 'doporučení autora'


# Which songs of a #section suit a part (explicit songs, ranges and groups are never filtered).
def section_filter(part: str, song: SongInfo) -> bool:
    if part == 'mass':
        return song.mass_song is True
    if part == 'communion':
        return has_verse(song.communion_verses)
    if part == 'recessional':
        return has_verse(song.recessional_verses)
    return True


class Snapshot:
    """Immutable view of the curated data plus derived indexes; build once per version."""

    def __init__(
        self,
        songs: Iterable[SongInfo],
        groups: Iterable[GroupInfo],
        rules: Iterable[RuleInfo],
        periods: Periods,
        version: object = None,
    ) -> None:
        self.version = version
        self.songs: dict[str, SongInfo] = {s.code: s for s in sorted(songs, key=lambda s: code_sort_key(s.code))}
        self.groups: dict[str, GroupInfo] = {g.key: g for g in groups}
        self.rules: tuple[RuleInfo, ...] = tuple(sorted(rules, key=lambda r: (r.position, str(r.id))))
        self.periods = periods
        self.codes: tuple[str, ...] = tuple(self.songs)
        self.sections: dict[str, tuple[str, ...]] = {}
        for song in self.songs.values():
            self.sections.setdefault(song.section, ())
            self.sections[song.section] += (song.code,)
        self._group_members = {k: g.members for k, g in self.groups.items()}
        self._celebration_mass_songs: dict[str, tuple[tuple[str, str], ...]] = {}

    def expand(self, target: Target, part: str | None = None) -> list[str]:
        codes = expand_target(target, self.codes, self._group_members, self.sections)
        codes = [c for c in codes if c in self.songs]
        if target.kind == 'section' and part is not None:
            codes = [c for c in codes if section_filter(part, self.songs[c])]
        return codes

    def celebration_mass_songs(self, celebration: str) -> tuple[tuple[str, str], ...]:
        """(code, verses) of the celebration's own songs, for neighbour rules (Direktář p. 27: "píseň ze slavnosti,
        svátku či památky … pro kterou je v Kancionálu píseň").

        Taken from the celebration's ▲ rules for the závěr first, then for the mešní píseň. Only songs named
        for it count: not groups or sections, and not general mass songs (512 for the archangels is not
        "their" song)."""
        if celebration not in self._celebration_mass_songs:
            result: list[tuple[str, str]] = []
            for part in ('recessional', 'mass'):
                for rule in self.rules:
                    if not (
                        rule.celebration == celebration
                        and rule.kind == 'songs'
                        and rule.strength in ('prescribed', 'recommended')
                        and part in rule.parts
                    ):
                        continue
                    for target in (t for t in rule.targets if t.kind in ('song', 'range')):
                        for code in self.expand(target, part):
                            if self.songs[code].section != 'mass_general' and all(code != c for c, _ in result):
                                result.append((code, target.verses if part == 'mass' else ''))
            self._celebration_mass_songs[celebration] = tuple(result)
        return self._celebration_mass_songs[celebration]


# --- day context ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OccurrenceCtx:
    title: str
    rank_label: str
    rank_num: Decimal
    colour: str
    celebration_key: str | None = None
    categories: frozenset[str] = frozenset()
    position: int = 0

    @property
    def is_mass_option(self) -> bool:
        return self.rank_label != RANK_COMMEMORATION


@dataclass(frozen=True)
class NeighbourCtx:
    date: date
    title: str
    celebration_key: str
    rank_num: Decimal
    season: str = ''
    rank_label: str = ''


@dataclass(frozen=True)
class DayCtx:
    date: date
    diocese: str
    season: str
    season_week: int
    sunday_cycle: str
    ferial_cycle: int
    occurrences: tuple[OccurrenceCtx, ...]
    neighbours: tuple[NeighbourCtx, ...] = ()
    previous_week: DayCtx | None = field(default=None, compare=False)

    @property
    def is_sunday(self) -> bool:
        return self.date.weekday() == 6
