"""Bump CurationState.version on every change to curated data (suspended during imports)."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from django.db.models import F
from django.db.models.signals import post_delete, post_save

_suspended: ContextVar[bool] = ContextVar('curation_bump_suspended', default=False)


@contextmanager
def bumps_suspended() -> Iterator[None]:
    token = _suspended.set(True)
    try:
        yield
    finally:
        _suspended.reset(token)


def bump_version(**kwargs: object) -> None:
    if _suspended.get() or kwargs.get('raw'):
        return
    from catalog.models import CurationState

    CurationState.current()
    CurationState.objects.filter(pk=1).update(version=F('version') + 1)


def connect() -> None:
    from catalog.models import Song, SongGroup, SongGroupMember

    for model in (Song, SongGroup, SongGroupMember):
        post_save.connect(bump_version, sender=model, dispatch_uid=f'curation_bump_save_{model.__name__}')
        post_delete.connect(bump_version, sender=model, dispatch_uid=f'curation_bump_delete_{model.__name__}')
