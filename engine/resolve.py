"""Rule matching and per-part resolution (design §7.3, §7.4). Pure: no Django."""
from __future__ import annotations

from dataclasses import dataclass, field

from catalog.codes import SECTION_LABELS, number_of
from engine.model import DayCtx, NeighbourCtx, OccurrenceCtx, RuleInfo, Snapshot, SongInfo
from engine.refs import Target
from engine.vocab import (
    MIN_RANK_THRESHOLD,
    NEIGHBOUR_MAX_RANK,
    PART_INDEX,
    PART_LABELS,
    STRENGTH_RANK,
    WEEKDAY_ABBR,
    tier,
)
from liturgy.constants import RANK_FEAST, RANK_MEMORIAL, RANK_PRIMARY, RANK_SOLEMNITY
from liturgy.norms import is_all_souls, is_solemnity

# --- results -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Reason:
    source: str  # 'Direktář s. 38' | 'doporučení autora'
    note: str = ''
    neighbour: str = ''  # 'ze svátku sv. Cyrila a Metoděje (po 5. 7.)'

    def text(self) -> str:
        parts = [self.neighbour, self.source, self.note]
        return ' · '.join(p for p in parts if p)


@dataclass(frozen=True)
class SongRef:
    code: str
    title: str
    verses: str = ''  # '5' or '1,3'; '' = whole song / no hint
    url: str = ''

    @property
    def verses_label(self) -> str:
        if not self.verses:
            return ''
        numbers = self.verses.split(',')
        return (', '.join(numbers[:-1]) + ' a ' + numbers[-1] if len(numbers) > 1 else numbers[0]) + '. sl.'


@dataclass
class Entry:
    """One song proposed for one part by one rule (internal; merged per code)."""

    code: str
    verses: str
    strength: str
    specificity: int
    rule: RuleInfo
    target_index: int
    target: Target | None
    neighbour: str = ''
    reasons: list[Reason] = field(default_factory=list)

    @property
    def sort_key(self) -> tuple:
        return (-STRENGTH_RANK[self.strength], -self.specificity, self.rule.position, str(self.rule.id),
                self.target_index)

    @property
    def tier(self) -> str:
        return tier(self.specificity)


@dataclass
class Item:
    """Display unit: one song, or one group/section/range of songs, from one rule target."""

    part: str
    kind: str  # 'song' | 'group'
    label: str
    songs: list[SongRef]
    tier: str
    strength: str
    reasons: list[Reason]

    @property
    def part_label(self) -> str:
        return PART_LABELS[self.part]


@dataclass
class PartResult:
    part: str
    entries: list[Entry]  # ordered best first
    items: list[Item]
    notes: list[str]
    silenced: bool = False

    @property
    def label(self) -> str:
        return PART_LABELS[self.part]

    @property
    def coverage(self) -> str | None:
        return self.entries[0].tier if self.entries else None


# --- matching ------------------------------------------------------------------------------


def rule_applies(rule: RuleInfo, ctx: DayCtx, occ: OccurrenceCtx, periods: frozenset[str]) -> bool:
    if rule.occasion:  # occasion rules only feed the occasions page
        return False
    if rule.celebration and occ.celebration_key != rule.celebration:
        return False
    if rule.category and rule.category not in occ.categories:
        return False
    if rule.period and rule.period not in periods:
        return False
    if rule.season and ctx.season != rule.season:
        return False
    if rule.cycles and ctx.sunday_cycle not in rule.cycles:
        return False
    if rule.day_kind == 'sunday' and not ctx.is_sunday:
        return False
    if rule.day_kind == 'weekday' and ctx.is_sunday:
        return False
    if rule.min_rank and occ.rank_num > MIN_RANK_THRESHOLD[rule.min_rank]:
        return False
    return not (rule.dioceses and ctx.diocese not in rule.dioceses)


def matching_rules(snap: Snapshot, ctx: DayCtx, occ: OccurrenceCtx) -> list[RuleInfo]:
    periods = snap.periods.active(ctx.date, ctx.season, ctx.season_week)
    return [r for r in snap.rules if rule_applies(r, ctx, occ, periods)]


# --- resolution ----------------------------------------------------------------------------


def _neighbour_label(ctx: DayCtx, nb_title: str, nb_date: object) -> str:
    return f'ze svátku {nb_title} ({WEEKDAY_ABBR[nb_date.weekday()]} {nb_date.day}. {nb_date.month}.)'


def _song_ref(song: SongInfo, verses: str) -> SongRef:
    return SongRef(code=song.code, title=song.title, verses=verses, url=song.url)


def _avoided(part_rules: list[RuleInfo], snap: Snapshot) -> tuple[dict[str, int], list[str]]:
    """code -> highest specificity of an avoid rule hitting it; plus the notes of avoid rules that hit."""
    avoided: dict[str, int] = {}
    notes: list[str] = []
    for rule in part_rules:
        if rule.kind != 'songs' or rule.strength != 'avoid':
            continue
        codes = [code for target in rule.targets for code in snap.expand(target)]
        for code in codes:
            avoided[code] = max(avoided.get(code, 0), rule.specificity)
        if codes and rule.note:
            notes.append(rule.note)
    return avoided, notes


def _song_entries(rule: RuleInfo, part: str, snap: Snapshot) -> list[Entry]:
    return [
        Entry(code, target.verses, rule.strength, rule.specificity, rule, index, target,
              reasons=[Reason(rule.source_label, rule.note)])
        for index, target in enumerate(rule.targets)
        for code in snap.expand(target, part)
    ]


def _is_celebration_for_neighbours(nb: NeighbourCtx) -> bool:
    """Direktář p. 27: "ze slavnosti, svátku či památky" - not Sundays, Holy Week or the Triduum."""
    if not nb.rank_label:  # synthetic contexts without labels: rank alone decides
        return True
    if nb.rank_label in (RANK_SOLEMNITY, RANK_FEAST, RANK_MEMORIAL):
        return not is_all_souls(nb.date, nb.rank_label, nb.title)
    return nb.rank_label == RANK_PRIMARY and is_solemnity(nb.date, nb.rank_label, nb.title)


def _is_neighbour(rule: RuleInfo, nb: NeighbourCtx, ctx: DayCtx, occ: OccurrenceCtx) -> bool:
    return (
        _is_celebration_for_neighbours(nb)
        and nb.date != ctx.date
        and abs((nb.date - ctx.date).days) <= rule.window_days
        and nb.rank_num <= NEIGHBOUR_MAX_RANK
        and nb.celebration_key != occ.celebration_key
        and (not nb.season or nb.season == ctx.season)  # no Holy Thursday songs at Easter
    )


def _neighbour_entries(rule: RuleInfo, ctx: DayCtx, occ: OccurrenceCtx, snap: Snapshot) -> list[Entry]:
    entries = []
    for nb in ctx.neighbours:
        if not _is_neighbour(rule, nb, ctx, occ):
            continue
        label = _neighbour_label(ctx, nb.title, nb.date)
        for code, verses in snap.celebration_mass_songs(nb.celebration_key):
            entries.append(Entry(code, verses, rule.strength, rule.specificity, rule, 0, None, label,
                                 reasons=[Reason(rule.source_label, rule.note, label)]))
    return entries


def _merge(entries: list[Entry]) -> list[Entry]:
    """One entry per song: the best one, collecting the reasons of the others."""
    merged: dict[str, Entry] = {}
    for entry in sorted(entries, key=lambda e: e.sort_key):
        best = merged.get(entry.code)
        if best is None:
            merged[entry.code] = entry
            continue
        for reason in entry.reasons:
            if reason not in best.reasons:
                best.reasons.append(reason)
    return sorted(merged.values(), key=lambda e: e.sort_key)


def resolve_part(part: str, rules: list[RuleInfo], snap: Snapshot, ctx: DayCtx, occ: OccurrenceCtx) -> PartResult:
    part_rules = [r for r in rules if part in r.parts]
    silence = [r for r in part_rules if r.kind == 'silence']
    silence_spec = max((r.specificity for r in silence), default=0)
    notes = [r.note for r in part_rules if r.kind in ('note', 'silence') and r.note]
    avoided, avoid_notes = _avoided(part_rules, snap)

    entries: list[Entry] = []
    for rule in part_rules:
        if rule.specificity <= silence_spec or rule.strength == 'avoid':
            continue
        if rule.kind == 'songs':
            entries.extend(_song_entries(rule, part, snap))
        elif rule.kind == 'neighbours':
            entries.extend(_neighbour_entries(rule, ctx, occ, snap))

    entries = [e for e in entries if avoided.get(e.code, 0) < e.specificity]
    if part == 'mass':
        entries = [e for e in entries if snap.songs[e.code].mass_song is not False]
    own = max((e.specificity for e in entries if not e.rule.fallback), default=0)
    entries = [e for e in entries if not e.rule.fallback or e.specificity >= own]
    ordered = _merge(entries)
    return PartResult(
        part=part,
        entries=ordered,
        items=_items(part, ordered, snap),
        notes=list(dict.fromkeys(notes + avoid_notes)),
        silenced=bool(silence),
    )


def _items(part: str, entries: list[Entry], snap: Snapshot) -> list[Item]:
    """Display units. Variants of one number (717A/B/C) are shown once, as the first variant."""
    items: list[Item] = []
    grouped: dict[tuple, Item] = {}
    shown: set[str] = set()
    for entry in entries:
        if number_of(entry.code) in shown:
            continue
        shown.add(number_of(entry.code))
        song = snap.songs[entry.code]
        target = entry.target
        if target is not None and target.kind in ('group', 'section', 'range'):
            key = (entry.rule.id, entry.target_index)
            item = grouped.get(key)
            if item is None:
                item = Item(part, 'group', _target_label(target, snap), [], entry.tier, entry.strength,
                            list(entry.reasons))
                grouped[key] = item
                items.append(item)
            item.songs.append(_song_ref(song, entry.verses))
        else:
            items.append(Item(part, 'song', song.title, [_song_ref(song, entry.verses)], entry.tier, entry.strength,
                              list(entry.reasons)))
    return items


def _target_label(target: Target, snap: Snapshot) -> str:
    if target.kind == 'group':
        group = snap.groups.get(target.ref)
        return group.name if group else target.ref
    if target.kind == 'section':
        return SECTION_LABELS.get(target.ref, target.ref)
    return f'{target.ref}–{target.ref_end}'


def resolve_mass(snap: Snapshot, ctx: DayCtx, occ: OccurrenceCtx) -> tuple[list[PartResult], list[str]]:
    """(parts with something to say, mass-level notes)."""
    rules = matching_rules(snap, ctx, occ)
    mass_notes = [r.note for r in rules if r.kind == 'note' and not r.parts and r.note]
    parts = []
    for part in sorted({p for r in rules for p in r.parts}, key=lambda p: PART_INDEX.get(p, 99)):
        if part not in PART_INDEX:
            continue
        result = resolve_part(part, rules, snap, ctx, occ)
        if result.entries or result.notes or result.silenced:
            parts.append(result)
    return parts, list(dict.fromkeys(mass_notes))
