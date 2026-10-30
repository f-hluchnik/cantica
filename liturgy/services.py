"""Read-side helpers for the web layer (recommendations: rules.services)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.utils import timezone

from liturgy.dbbuild import latest_build


@dataclass(frozen=True)
class Health:
    status: str  # 'ok' | 'warn' | 'error'
    last_date: date | None
    days_ahead: int | None
    built_at: str | None


def health(min_days_ahead: int) -> Health:
    build = latest_build()
    if build is None:
        return Health(status='error', last_date=None, days_ahead=None, built_at=None)
    days_ahead = (build.last_date - timezone.localdate()).days
    return Health(
        status='ok' if days_ahead >= min_days_ahead else 'warn',
        last_date=build.last_date,
        days_ahead=days_ahead,
        built_at=build.built_at.isoformat(),
    )
