"""Build a Snapshot from curated records (from the YAML file or the DB export). Pure: no Django."""
from __future__ import annotations

from catalog.curation import Curation
from catalog.rulerecords import RuleRecord
from engine.model import GroupInfo, RuleInfo, Snapshot, SongInfo
from engine.refs import RefError, parse_targets
from liturgy.periods import Periods


def rule_info(record: RuleRecord, rule_id: int | str) -> RuleInfo:
    return RuleInfo(
        id=rule_id,
        parts=tuple(record.parts),
        strength=record.strength,
        kind=record.kind,
        targets=parse_targets(record.songs) if record.kind == 'songs' else (),
        celebration=record.celebration,
        category=record.category,
        period=record.period,
        season=record.season,
        cycles=frozenset(record.cycles),
        day_kind=record.day,
        min_rank=record.min_rank,
        dioceses=frozenset(record.dioceses),
        window_days=record.window_days,
        note=record.note,
        page=record.page,
        position=record.position,
    )


def _valid_rules(curation: Curation) -> list[RuleInfo]:
    """Active rules; a rule with an unparsable song list is skipped (never crash the site; lint reports it)."""
    result = []
    for index, record in enumerate(curation.rules):
        if not record.active:
            continue
        try:
            result.append(rule_info(record, record.id if record.id is not None else index))
        except RefError:
            continue
    return result


def snapshot_from_curation(curation: Curation, periods: Periods, version: object = None) -> Snapshot:
    return Snapshot(
        songs=[
            SongInfo(s.code, s.title, s.section, s.mass_song, s.communion_verses, s.recessional_verses)
            for s in curation.songs
        ],
        groups=[GroupInfo(g.key, g.name, tuple(g.members)) for g in curation.groups],
        rules=_valid_rules(curation),
        periods=periods,
        version=curation.version if version is None else version,
    )
