"""Shared test helpers (no Django imports)."""
from __future__ import annotations

import json
from pathlib import Path

from liturgy.snapshot import MonthSnapshot

FIXTURES = Path(__file__).resolve().parent / 'fixtures'
CALAPI_FIXTURES = FIXTURES / 'calapi'


def api_payload(calendar: str, year: int, month: int) -> list:
    path = CALAPI_FIXTURES / calendar / f'{year:04d}-{month:02d}.json'
    return json.loads(path.read_text(encoding='utf-8'))


def fixture_snapshot(calendar: str, year: int, month: int) -> MonthSnapshot:
    return MonthSnapshot.from_api(calendar, year, month, api_payload(calendar, year, month))


def all_fixture_snapshots() -> list[MonthSnapshot]:
    result = []
    for path in sorted(CALAPI_FIXTURES.glob('*/*.json')):
        year, month = (int(x) for x in path.stem.split('-'))
        result.append(fixture_snapshot(path.parent.name, year, month))
    return result


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None
