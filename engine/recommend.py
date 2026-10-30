"""Entry point: recommend(ctx, snap) -> DayResult. Pure: no Django, no I/O."""
from __future__ import annotations

from dataclasses import dataclass

from engine.model import DayCtx, OccurrenceCtx, Snapshot
from engine.plan import PlanEntry, build_plan
from engine.resolve import Item, PartResult, resolve_mass
from engine.vocab import GAP_MAX_RANK, TIER_GENERAL
from liturgy import norms
from liturgy.constants import COLOURS


@dataclass
class MassResult:
    occurrence: OccurrenceCtx
    rank_label: str
    norms: norms.MassNorms
    notes: list[str]
    parts: list[PartResult]
    plan: list[PlanEntry]
    summary: list[Item]
    gap: bool  # a celebration or Sunday (memorial or higher) for which nothing specific (▲/■) is known

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


def _summary(parts: list[PartResult]) -> list[Item]:
    """Always-visible list: everything specific (▲/■) or prescribed, plus the general mass-song options
    when the day has no specific mass song (without the 'možno též' ones, which stay in the details)."""
    items = []
    for result in parts:
        has_specific = any(item.tier != TIER_GENERAL for item in result.items)
        for item in result.items:
            specific = item.tier != TIER_GENERAL or item.strength == 'prescribed'
            general_mass_song = result.part == 'mass' and item.strength != 'alternative' and not has_specific
            if specific or general_mass_song:
                items.append(item)
    return items


def _masses(ctx: DayCtx, snap: Snapshot, skip: frozenset[str]) -> list[MassResult]:
    results = []
    options = sorted((o for o in ctx.occurrences if o.is_mass_option), key=lambda o: (o.rank_num, o.position))
    for occ in options:
        parts, notes = resolve_mass(snap, ctx, occ)
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
            gap=occ.celebration_key is not None and occ.rank_num <= GAP_MAX_RANK and not has_specific,
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
