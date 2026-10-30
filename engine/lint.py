"""Ruleset lint and coverage report (design §7.6). Pure: no Django.

Runs the real matching over calendar days, so it catches what a schema check cannot:
rules that never fire, recommend/avoid contradictions, and celebrations we know nothing about.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date

from catalog.codes import verse_numbers
from catalog.curation import Curation
from catalog.rulerecords import RuleRecord
from engine.context import occurrence_ctx
from engine.load import snapshot_from_curation
from engine.model import DayCtx, RuleInfo, Snapshot
from engine.refs import expand_target, parse_targets
from engine.resolve import matching_rules
from engine.vocab import GAP_MAX_RANK, SPECIFICITY
from liturgy.catalog import Catalog
from liturgy.days import BuiltDay
from liturgy.periods import Periods


@dataclass
class CoverageGap:
    celebration_key: str
    title: str
    first_date: date
    count: int


@dataclass
class LintReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    overrides: list[str] = field(default_factory=list)  # author rules deliberately overriding the Direktář
    gaps: list[CoverageGap] = field(default_factory=list)
    days_checked: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors


def lint(  # noqa: C901
    curation: Curation,
    celebrations: Catalog,
    periods: Periods,
    days: Mapping[str, Iterable[BuiltDay]],  # diocese code -> days
    categories: Mapping[str, frozenset[str]],
) -> LintReport:
    report = LintReport()
    report.errors.extend(curation.problems())
    records = {(r.id if r.id is not None else i): r for i, r in enumerate(curation.rules)}

    for record in curation.rules:
        if record.celebration and record.celebration not in celebrations.entries:
            report.errors.append(f'{record.label}: unknown celebration {record.celebration!r}')
        if record.period and record.period not in periods.items:
            report.errors.append(f'{record.label}: unknown period {record.period!r}')
    if report.errors:
        return report  # matching needs a valid ruleset

    for record in curation.rules:
        if record.kind == 'songs':
            _check_targets(record, curation, report)

    snap = snapshot_from_curation(curation, periods)
    fired: set[object] = set()
    contradictions: set[str] = set()
    overrides: set[str] = set()
    gaps: dict[str, CoverageGap] = {}
    seen: set[frozenset] = set()
    for diocese, diocese_days in days.items():
        for built in diocese_days:
            report.days_checked += 1
            ctx = DayCtx(built.date, diocese, built.season, built.season_week, built.sunday_cycle,
                         built.ferial_cycle, occurrence_ctx(built, categories))
            for occ in ctx.occurrences:
                if not occ.is_mass_option:
                    continue
                rules = matching_rules(snap, ctx, occ)
                fired.update(r.id for r in rules)
                key = frozenset(r.id for r in rules)
                if key not in seen:
                    seen.add(key)
                    errors, intended = _contradictions(rules, snap, records)
                    contradictions.update(errors)
                    overrides.update(intended)
                if occ.celebration_key and occ.rank_num <= GAP_MAX_RANK and not _has_specific_mass_song(rules):
                    _add_gap(gaps, occ.celebration_key, occ.title, built.date)

    report.errors.extend(sorted(contradictions))
    report.overrides.extend(sorted(overrides))
    for rule in snap.rules:
        if rule.id not in fired:
            report.warnings.append(f'{records[rule.id].label}: never applies in the checked days')
    report.gaps = sorted(gaps.values(), key=lambda g: g.first_date)
    return report


def _has_specific_mass_song(rules: list[RuleInfo]) -> bool:
    return any(
        r.specificity >= SPECIFICITY['category'] and 'mass' in r.parts and r.kind == 'songs' and r.strength != 'avoid'
        for r in rules
    )


def _add_gap(gaps: dict[str, CoverageGap], key: str, title: str, day: date) -> None:
    gap = gaps.get(key)
    if gap is None:
        gaps[key] = CoverageGap(key, title, day, 1)
    else:
        gap.count += 1
        gap.first_date = min(gap.first_date, day)


def _check_targets(record: RuleRecord, curation: Curation, report: LintReport) -> None:
    songs = {s.code: s for s in curation.songs}
    groups = {g.key: g.members for g in curation.groups}
    for target in parse_targets(record.songs):
        if target.kind == 'section':
            continue
        for code in expand_target(target, songs, groups, {}):
            song = songs[code]
            if 'mass' in record.parts and record.strength != 'avoid' and song.mass_song is False:
                report.errors.append(f'{record.label}: {code} is marked as not a mass song')
            if target.verses and song.verse_count and max(verse_numbers(target.verses)) > song.verse_count:
                report.warnings.append(f'{record.label}: {code} has only {song.verse_count} verses')


def _contradictions(  # noqa: C901
    rules: list[RuleInfo], snap: Snapshot, records: Mapping[object, RuleRecord],
) -> tuple[set[str], set[str]]:
    """A song recommended and avoided at the same specificity for the same part.

    Between two rules of the same source (both Direktář or both author) that is an error. An author
    rule avoiding what the Direktář recommends is a deliberate, documented override.
    """
    errors, overrides = set(), set()
    by_part: dict[str, dict[str, list[RuleInfo]]] = {}
    for rule in rules:
        if rule.kind != 'songs':
            continue
        for part in rule.parts:
            for target in rule.targets:
                for code in snap.expand(target, None if rule.strength == 'avoid' else part):
                    by_part.setdefault(part, {}).setdefault(code, []).append(rule)
    for part, codes in by_part.items():
        for code, hits in codes.items():
            for spec in sorted({r.specificity for r in hits}):
                positive = [r for r in hits if r.specificity == spec and r.strength != 'avoid']
                negative = [r for r in hits if r.specificity == spec and r.strength == 'avoid']
                for pos in positive:
                    for neg in negative:
                        message = (f'song {code} for {part}: {records[pos.id].label} vs. avoid {records[neg.id].label}')
                        if pos.page and not neg.page:
                            overrides.add(message)
                        else:
                            errors.add(f'both recommended and avoided: {message}')
    return errors, overrides
