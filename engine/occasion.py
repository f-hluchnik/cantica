"""Recommendations for occasions (Direktář pp. 47-48): křest, biřmování, pohřeb, … Pure: no Django.

Occasion rules don't depend on a date, so there is no plan here: the page lists, per part, what the
Direktář recommends, plus the notes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from engine.model import DayCtx, OccurrenceCtx, Snapshot
from engine.resolve import PartResult, resolve_part
from engine.vocab import OCCASION_LABELS, PART_INDEX


@dataclass
class OccasionResult:
    key: str
    label: str
    notes: list[str]
    parts: list[PartResult]


_NO_DAY = DayCtx(date(2000, 1, 1), '', '', 0, '', 0, ())
_NO_OCCURRENCE = OccurrenceCtx('', '', Decimal('9'), '')


def occasion_result(snap: Snapshot, key: str) -> OccasionResult:
    rules = [r for r in snap.rules if r.occasion == key]
    notes = [r.note for r in rules if r.kind == 'note' and not r.parts and r.note]
    parts = []
    for part in sorted({p for r in rules for p in r.parts}, key=lambda p: PART_INDEX.get(p, 99)):
        result = resolve_part(part, rules, snap, _NO_DAY, _NO_OCCURRENCE)
        if result.entries or result.notes:
            parts.append(result)
    return OccasionResult(key=key, label=OCCASION_LABELS.get(key, key), notes=list(dict.fromkeys(notes)), parts=parts)
