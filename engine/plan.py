"""Detailní doporučení: one valid combination of songs per mass (design §8.3). Pure: no Django."""
from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field

from catalog.codes import has_verse, number_of, verse_numbers
from engine.model import DayCtx, OccurrenceCtx, Snapshot
from engine.resolve import Entry, Item, PartResult, Reason, SongRef
from engine.vocab import (
    COVERED_BY_MASS_SONG,
    PART_INDEX,
    PART_LABELS,
    SPECIFICITY,
)
from liturgy.norms import liturgical_year

GAP_NOTE = 'Direktář pro tuto část nic neuvádí.'
MASS_VERSE_REASON = Reason('sloka mešní písně')


@dataclass
class PlanEntry:
    part: str
    kind: str  # 'songs' | 'mass_verse' | 'gap' | 'silence'
    songs: list[SongRef] = field(default_factory=list)
    tier: str | None = None
    reasons: list[Reason] = field(default_factory=list)
    alternatives: list[Item] = field(default_factory=list)
    note: str = ''
    covers: tuple[str, ...] = ()
    notes: list[str] = field(default_factory=list)  # the part's notes from rules (shown with the entry)

    @property
    def label(self) -> str:
        return PART_LABELS[self.part]

    @property
    def covers_label(self) -> str:
        return ', '.join(PART_LABELS[p] for p in self.covers)


def variety_seed(ctx: DayCtx, occ: OccurrenceCtx, part: str) -> int:
    """Stable across processes and reloads; changes from week to week."""
    raw = '|'.join((
        str(liturgical_year(ctx.date)), ctx.season, str(ctx.season_week), str(ctx.date.weekday()),
        occ.title, ctx.diocese, part,
    ))
    return int.from_bytes(hashlib.sha256(raw.encode()).digest()[:8], 'big')


def _best_class(entries: list[Entry]) -> list[Entry]:
    first = entries[0]
    return [e for e in entries if (e.strength, e.specificity) == (first.strength, first.specificity)]


def _choose(
    entries: list[Entry],
    seed: int,
    prefer: Callable[[Entry], bool] | None = None,
    avoid: frozenset[str] = frozenset(),
) -> list[Entry]:
    best = _best_class(entries)
    if best[0].strength == 'prescribed':
        # all prescribed songs, but one variant per number (422A, 422B, 422C -> 422A)
        seen: set[str] = set()
        result = []
        for entry in best:
            if number_of(entry.code) not in seen:
                seen.add(number_of(entry.code))
                result.append(entry)
        return result
    distinct: list[Entry] = []  # one variant per number: variety between songs, not between 704A/704B
    for entry in best:
        if all(number_of(entry.code) != number_of(e.code) for e in distinct):
            distinct.append(entry)
    pool = [e for e in distinct if prefer(e)] if prefer else distinct
    pool = pool or distinct
    pool = [e for e in pool if e.code not in avoid] or pool
    return [pool[seed % len(pool)]]


def _ref(snap: Snapshot, entry: Entry) -> SongRef:
    song = snap.songs[entry.code]
    return SongRef(code=song.code, title=song.title, verses=entry.verses, url=song.url)


def _alternatives(result: PartResult | None, chosen: set[str]) -> list[Item]:
    if result is None:
        return []
    items = []
    for item in result.items:
        songs = [s for s in item.songs if s.code not in chosen]
        if songs:
            items.append(Item(item.part, item.kind, item.label, songs, item.tier, item.strength, item.reasons))
    return items


def _songs_entry(part: str, chosen: list[Entry], result: PartResult | None, snap: Snapshot) -> PlanEntry:
    reasons: list[Reason] = []
    for entry in chosen:
        for reason in entry.reasons:
            if reason not in reasons:
                reasons.append(reason)
    return PlanEntry(
        part=part,
        kind='songs',
        songs=[_ref(snap, e) for e in chosen],
        tier=chosen[0].tier,
        reasons=reasons,
        alternatives=_alternatives(result, {e.code for e in chosen}),
    )


def _mass_verse_entry(part: str, mass: Entry, spec: str | None, result: PartResult | None, snap: Snapshot) -> PlanEntry:
    song = snap.songs[mass.code]
    verses = ','.join(str(n) for n in verse_numbers(spec))  # only specific numbers are shown
    return PlanEntry(
        part=part,
        kind='mass_verse',
        songs=[SongRef(code=song.code, title=song.title, verses=verses, url=song.url)],
        tier=mass.tier,
        reasons=[MASS_VERSE_REASON],
        alternatives=_alternatives(result, set()),
    )


class _Planner:
    """Builds the plan part by part; `used` keeps a song from appearing twice."""

    def __init__(self, parts: dict[str, PartResult], snap: Snapshot, ctx: DayCtx, occ: OccurrenceCtx) -> None:
        self.parts, self.snap, self.ctx, self.occ = parts, snap, ctx, occ
        self.plan: list[PlanEntry] = []
        self.used: set[str] = set()
        self.mass: Entry | None = None

    # helpers --------------------------------------------------------------------------------

    def seed(self, part: str) -> int:
        return variety_seed(self.ctx, self.occ, part)

    def candidates(self, part: str) -> list[Entry]:
        result = self.parts.get(part)
        return [e for e in result.entries if e.code not in self.used] if result else []

    def silenced(self, part: str) -> bool:
        result = self.parts.get(part)
        if result and result.silenced and not result.entries:
            self.add(PlanEntry(part=part, kind='silence', note=' '.join(result.notes) or 'Nic se nezpívá.'))
            return True
        return False

    def add(self, entry: PlanEntry) -> None:
        self.plan.append(entry)
        if entry.kind == 'songs':
            self.used.update(s.code for s in entry.songs)

    def add_songs(self, part: str, chosen: list[Entry]) -> PlanEntry:
        entry = _songs_entry(part, chosen, self.parts.get(part), self.snap)
        self.add(entry)
        return entry

    def add_gap(self, part: str) -> None:
        self.add(PlanEntry(part=part, kind='gap', note=GAP_NOTE))

    @property
    def mass_spec(self) -> int:
        return self.mass.specificity if self.mass else 0

    def mass_verse(self, field_name: str) -> str | None:
        """The mass song's verified verse spec for a part, or None if it has none / is not verified."""
        if self.mass is None:
            return None
        spec = getattr(self.snap.songs[self.mass.code], field_name)
        return spec if has_verse(spec) else None

    def add_mass_verse(self, part: str, spec: str) -> None:
        self.add(_mass_verse_entry(part, self.mass, spec, self.parts.get(part), self.snap))

    # steps ----------------------------------------------------------------------------------

    def _overrides(self, part: str, spec: int) -> bool:
        """Does `part` have its own song that replaces a mass song of specificity `spec`?"""
        cands = self.candidates(part)
        return bool(cands) and (cands[0].strength == 'prescribed' or cands[0].specificity >= spec)

    def mass_song(self, skip: frozenset[str]) -> None:
        """Either one mešní píseň (with single parts replaced where a rule says so), or - when every part the
        mass song would cover has its own song (e.g. the rorate songs of late Advent) - one song per part."""
        if self.silenced('mass'):
            return
        cands = self.candidates('mass')
        if not cands:
            if not all(self.candidates(p) for p in COVERED_BY_MASS_SONG):
                self.add_gap('mass')
            return
        chosen = _choose(cands, self.seed('mass'), prefer=lambda e: self.snap.songs[e.code].mass_song is True,
                         avoid=skip)
        if all(self._overrides(p, chosen[0].specificity) for p in COVERED_BY_MASS_SONG):
            return  # one song per part instead of a mass song
        self.mass = chosen[0]
        self.add_songs('mass', chosen).covers = COVERED_BY_MASS_SONG

    def covered_parts(self) -> None:
        """Parts the mass song covers, unless a rule for that very part is at least as specific (Direktář p. 8:
        "ke vstupu příslušnou sloku 838 a od sloky před evangeliem pokračovat mešní písní") or prescribed."""
        for part in COVERED_BY_MASS_SONG:
            if self.silenced(part):
                continue
            own_song = bool(self.candidates(part)) if self.mass is None else self._overrides(part, self.mass_spec)
            if own_song:
                self.add_songs(part, _choose(self.candidates(part), self.seed(part)))

    def communion(self) -> None:
        if self.silenced('communion'):
            return
        cands = self.candidates('communion')
        verse = self.mass_verse('communion_verses')
        specific = bool(cands) and (cands[0].strength == 'prescribed' or cands[0].specificity > self.mass_spec)
        if cands and (specific or verse is None or self.seed('communion/verse') % 2):
            self.add_songs('communion', _choose(cands, self.seed('communion')))
        elif verse is not None:
            self.add_mass_verse('communion', verse)
        else:
            self.add_gap('communion')

    def recessional(self) -> None:
        """Prescribed or period-level (and more specific) songs first; then songs from nearby celebrations
        (Direktář p. 27), which beat the general seasonal list; then the general list or the mass song's verse."""
        if self.silenced('recessional'):
            return
        cands = self.candidates('recessional')
        strong = [e for e in cands if e.strength == 'prescribed' or e.specificity >= SPECIFICITY['period']]
        neighbours = [e for e in cands if e.neighbour]
        verse = self.mass_verse('recessional_verses')
        for group in (strong, neighbours):
            if group:
                self.add_songs('recessional', _choose(group, self.seed('recessional')))
                return
        if cands and (verse is None or self.seed('recessional/verse') % 2 == 0):
            self.add_songs('recessional', _choose(cands, self.seed('recessional')))
        elif verse is not None:
            self.add_mass_verse('recessional', verse)
        else:
            self.add_gap('recessional')

    def special_parts(self) -> None:
        """Other parts appear only when something is said about them."""
        handled = {'mass', 'communion', 'recessional', *COVERED_BY_MASS_SONG}
        for part in self.parts:
            if part in handled or self.silenced(part):
                continue
            cands = self.candidates(part)
            if cands:
                self.add_songs(part, _choose(cands, self.seed(part)))

    def result(self) -> list[PlanEntry]:
        own = {e.part for e in self.plan}
        for entry in self.plan:
            if entry.covers:
                entry.covers = tuple(p for p in entry.covers if p not in own)
            if entry.kind != 'silence' and entry.part in self.parts:
                entry.notes = list(self.parts[entry.part].notes)
        return sorted(self.plan, key=lambda e: PART_INDEX[e.part])


def build_plan(
    parts: dict[str, PartResult],
    snap: Snapshot,
    ctx: DayCtx,
    occ: OccurrenceCtx,
    skip_mass_songs: frozenset[str] = frozenset(),
) -> list[PlanEntry]:
    planner = _Planner(parts, snap, ctx, occ)
    planner.mass_song(skip_mass_songs)
    planner.covered_parts()
    planner.communion()
    planner.recessional()
    planner.special_parts()
    return planner.result()
