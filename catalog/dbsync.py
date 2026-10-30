"""DB <-> data/curated/curation.yaml.

Export is always allowed. Import replaces the curated tables with the file, but refuses when the
DB has changes that were never exported (they would be lost), unless forced.
"""
from __future__ import annotations

from django.db import transaction

from catalog.curation import Curation, GroupRecord, SongRecord
from catalog.models import CurationState, Song, SongGroup, SongGroupMember
from catalog.signals import bumps_suspended

SONG_FIELDS = (
    'title', 'section', 'mass_song', 'communion_verses', 'recessional_verses', 'verse_count', 'reviewed', 'note',
)


class ImportRefusedError(RuntimeError):
    pass


def db_to_curation() -> Curation:
    state = CurationState.current()
    songs = [
        SongRecord(
            code=s.code,
            title=s.title,
            section=s.section,
            mass_song=s.mass_song,
            communion_verses=s.communion_verses,
            recessional_verses=s.recessional_verses,
            verse_count=s.verse_count,
            reviewed=s.reviewed,
            note=s.note,
        )
        for s in Song.objects.all()
    ]
    members: dict[str, list[str]] = {}
    for m in SongGroupMember.objects.order_by('group_id', 'position', 'id'):
        members.setdefault(m.group_id, []).append(m.song_id)
    groups = [
        GroupRecord(
            key=g.key,
            name=g.name,
            members=members.get(g.key, []),
            description=g.description,
            source_page=g.source_page,
        )
        for g in SongGroup.objects.all()
    ]
    return Curation(version=state.version, songs=songs, groups=groups)


def export_curation(mark: bool = True) -> Curation:
    """Snapshot the DB; with mark=True also record it as exported."""
    with transaction.atomic():
        curation = db_to_curation()
        if mark:
            mark_exported(curation.version)
    return curation


def mark_exported(version: int) -> CurationState:
    """Record that `version` reached git. Later edits (version > exported) stay unexported."""
    state = CurationState.current()
    if version > state.version:
        raise ValueError(f'version {version} is newer than the DB (version {state.version})')
    CurationState.objects.filter(pk=1).update(exported_version=version)
    state.refresh_from_db()
    return state


def _content(curation: Curation) -> str:
    return Curation(version=0, songs=curation.songs, groups=curation.groups).dumps()


def is_empty() -> bool:
    return not Song.objects.exists() and not SongGroup.objects.exists()


@transaction.atomic
def import_curation(curation: Curation, force: bool = False) -> str:
    """Replace curated tables with `curation`. Returns 'imported' or 'unchanged'."""
    curation.validate()
    state = CurationState.current()
    empty = is_empty()

    if not empty and _content(db_to_curation()) == _content(curation):
        return 'unchanged'
    if not empty and state.has_unexported_changes and not force:
        raise ImportRefusedError(
            f'the DB has changes that were never exported (version {state.version}, '
            f'last export {state.exported_version}); run curation_export first or use --force',
        )

    with bumps_suspended():
        SongGroupMember.objects.all().delete()

        songs = []
        for record in curation.songs:
            song = Song(code=record.code, **{name: getattr(record, name) for name in SONG_FIELDS})
            song.derive()
            songs.append(song)
        Song.objects.bulk_create(
            songs,
            update_conflicts=True,
            unique_fields=['code'],
            update_fields=['number', 'position', *SONG_FIELDS],
            batch_size=500,
        )
        Song.objects.exclude(code__in=[s.code for s in songs]).delete()  # PROTECT stops this if still referenced

        groups = [
            SongGroup(key=g.key, name=g.name, description=g.description, source_page=g.source_page)
            for g in curation.groups
        ]
        SongGroup.objects.bulk_create(
            groups,
            update_conflicts=True,
            unique_fields=['key'],
            update_fields=['name', 'description', 'source_page'],
        )
        SongGroup.objects.exclude(key__in=[g.key for g in groups]).delete()
        SongGroupMember.objects.bulk_create([
            SongGroupMember(group_id=g.key, song_id=code, position=position)
            for g in curation.groups
            for position, code in enumerate(g.members, start=1)
        ])

    new_version = max(state.version + 1, curation.version)
    CurationState.objects.filter(pk=1).update(version=new_version, exported_version=new_version)
    return 'imported'
