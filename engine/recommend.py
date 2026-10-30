"""Entry point: recommend(ctx, snap) -> DayResult. Pure: no Django, no I/O."""
from __future__ import annotations

from dataclasses import dataclass, replace

from engine.model import DayCtx, OccurrenceCtx, Snapshot
from engine.plan import PlanEntry, build_plan
from engine.resolve import Item, PartResult, resolve_mass
from engine.vocab import GAP_MAX_RANK, PART_LABELS, TIER_GENERAL
from liturgy import norms
from liturgy.constants import COLOURS, RANK_SUNDAY


@dataclass
class SummaryPart:
    """One line of the always-visible list: the items for one part ('mass' first, shown without a label)."""

    part: str
    items: list[Item]

    @property
    def label(self) -> str:
        return PART_LABELS[self.part]


@dataclass
class MassResult:
    occurrence: OccurrenceCtx
    rank_label: str
    norms: norms.MassNorms
    notes: list[str]  # from ▲/■ rules; ● notes are the day's (DayResult.notes)
    parts: list[PartResult]
    plan: list[PlanEntry]
    summary: list[SummaryPart]
    gap: bool  # a celebration (not a Sunday) of memorial rank or higher with nothing specific (▲/■)
    general_notes: list[str]

    @property
    def title(self) -> str:
        return self.occurrence.title

    @property
    def colour(self) -> str:
        return self.occurrence.colour

    @property
    def colour_label(self) -> str:
        return COLOURS.get(self.occurrence.colour, self.occurrence.colour)


@dataclass
class DayResult:
    ctx: DayCtx
    masses: list[MassResult]
    commemorations: list[str]
    version: object

    @property
    def notes(self) -> list[str]:
        """Notes of ● rules (season, period): about the day, shown once above the masses."""
        return list(dict.fromkeys(n for m in self.masses for n in m.general_notes))


def _shown(part: str, item: Item) -> bool:
    """Always visible: what is specific to the celebration (▲/■), what is prescribed, and - for the mass song -
    the season's label: the first group a general rule names (Adventní písně, mešní písně obecné; not the further
    'písně k Pánu Ježíši pro mši'). Single general songs (e.g. 121, 123 in early Advent) and the other groups
    only steer the detailní doporučení; 'možno též' items stay there too."""
    if item.tier != TIER_GENERAL or item.strength == 'prescribed':
        return True
    return part == 'mass' and item.kind == 'group' and item.primary and item.strength != 'alternative'


def _compact(items: list[Item]) -> list[Item]:
    """Songs named together by one rule are shown as one line: '▲ 106 · 107 · 108' (Direktář p. 46)."""
    result: list[Item] = []
    for item in items:
        last = result[-1] if result else None
        same_rule = last is not None and item.reasons[:1] == last.reasons[:1]
        if same_rule and item.kind == last.kind == 'song' and (item.tier, item.strength) == (last.tier, last.strength):
            result[-1] = replace(last, songs=[*last.songs, *item.songs])
        else:
            result.append(item)
    return result


def _summary(parts: list[PartResult]) -> list[SummaryPart]:
    lines = []
    for result in parts:
        items = _compact([item for item in result.items if _shown(result.part, item)])
        if items:
            lines.append(SummaryPart(result.part, items))
    return lines


def _is_sunday(ctx: DayCtx, occ: OccurrenceCtx) -> bool:
    return norms.rank_display(ctx.date, occ.rank_label, occ.title) == RANK_SUNDAY


def _masses(ctx: DayCtx, snap: Snapshot, skip: frozenset[str]) -> list[MassResult]:
    results = []
    options = sorted((o for o in ctx.occurrences if o.is_mass_option), key=lambda o: (o.rank_num, o.position))
    for occ in options:
        parts, notes, general = resolve_mass(snap, ctx, occ)
        by_part = {p.part: p for p in parts}
        has_specific = any(item.tier != TIER_GENERAL for p in parts for item in p.items)
        results.append(MassResult(
            occurrence=occ,
            rank_label=norms.rank_display(ctx.date, occ.rank_label, occ.title),
            norms=norms.mass_norms(ctx.date, ctx.season, occ.rank_label, occ.title),
            notes=notes,
            parts=parts,
            plan=build_plan(by_part, snap, ctx, occ, skip),
            summary=_summary(parts),
            gap=(occ.celebration_key is not None and occ.rank_num <= GAP_MAX_RANK and not has_specific
                 and not _is_sunday(ctx, occ)),
            general_notes=list(dict.fromkeys([*general, *(n for p in parts for n in p.general_notes)])),
        ))
    return results


def recommend(ctx: DayCtx, snap: Snapshot) -> DayResult:
    skip: frozenset[str] = frozenset()
    if ctx.previous_week is not None:
        previous = _masses(ctx.previous_week, snap, frozenset())
        if previous:
            skip = frozenset(s.code for e in previous[0].plan if e.part == 'mass' and e.kind == 'songs'
                             for s in e.songs)
    return DayResult(
        ctx=ctx,
        masses=_masses(ctx, snap, skip),
        commemorations=[o.title for o in ctx.occurrences if not o.is_mass_option],
        version=snap.version,
    )
