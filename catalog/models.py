"""Song catalog: songs, song groups and the curation version counter.

The DB is the source of truth for these (edited in the admin); data/curated/curation.yaml is
their export (catalog.dbsync). Every change bumps CurationState.version (catalog.signals).
"""
from __future__ import annotations

from collections.abc import Collection

from django.core.exceptions import ValidationError
from django.db import models

from catalog.codes import SECTIONS, code_sort_key, number_of, verse_numbers
from catalog.validators import validate_code, validate_verses

VERSES_HELP = 'prázdné = neověřeno, „-“ = nemá, „*“ = podle Kancionálu, „4,5“ = tyto sloky'


def song_position(code: str) -> int:
    """Integer sort key in Kancionál order (number, then Z appendix, then variant letter)."""
    number, appendix, letter = code_sort_key(code)
    return number * 100 + appendix * 50 + (ord(letter) - 64 if letter else 0)


class Song(models.Model):
    code = models.CharField(primary_key=True, max_length=8, validators=[validate_code], verbose_name='kód')
    number = models.CharField(max_length=8, db_index=True, editable=False, verbose_name='číslo')
    position = models.PositiveIntegerField(default=0, editable=False)
    title = models.CharField(max_length=200, verbose_name='název')
    section = models.CharField(max_length=32, choices=SECTIONS, verbose_name='oddíl')
    mass_song = models.BooleanField(null=True, blank=True, verbose_name='mešní píseň')
    communion_verses = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        validators=[validate_verses],
        verbose_name='k přijímání',
        help_text=VERSES_HELP,
    )
    recessional_verses = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        validators=[validate_verses],
        verbose_name='na závěr',
        help_text=VERSES_HELP,
    )
    verse_count = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='počet slok')
    reviewed = models.BooleanField(default=False, verbose_name='zkontrolováno')
    note = models.TextField(blank=True, verbose_name='poznámka')

    class Meta:
        ordering = ('position',)
        verbose_name = 'píseň'
        verbose_name_plural = 'písně'

    def __str__(self) -> str:
        return f'{self.code} - {self.title}'

    @property
    def kancional_url(self) -> str:
        return f'https://kancional.cz/{self.code}'

    def derive(self) -> None:
        """Fill fields computed from the code (also used before bulk operations)."""
        self.number = number_of(self.code)
        self.position = song_position(self.code)

    def save(self, *args, **kwargs) -> None:
        self.derive()
        super().save(*args, **kwargs)

    def clean_fields(self, exclude: Collection[str] | None = None) -> None:
        # number/position are derived from the code in save(); never validate them as user input.
        super().clean_fields(exclude={*(exclude or ()), 'number', 'position'})

    def clean(self) -> None:
        if self.verse_count:
            for name in ('communion_verses', 'recessional_verses'):
                try:
                    too_high = [v for v in verse_numbers(getattr(self, name)) if v > self.verse_count]
                except ValueError:
                    continue  # reported by the field validator
                if too_high:
                    raise ValidationError({name: f'Píseň má jen {self.verse_count} slok.'})


class SongGroup(models.Model):
    key = models.CharField(primary_key=True, max_length=48, verbose_name='klíč')
    name = models.CharField(max_length=200, verbose_name='název')
    description = models.TextField(blank=True, verbose_name='popis')
    source_page = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='strana Direktáře')
    songs = models.ManyToManyField(Song, through='SongGroupMember', related_name='groups', verbose_name='písně')

    class Meta:
        ordering = ('key',)
        verbose_name = 'skupina písní'
        verbose_name_plural = 'skupiny písní'

    def __str__(self) -> str:
        return self.name


class SongGroupMember(models.Model):
    group = models.ForeignKey(SongGroup, on_delete=models.CASCADE, related_name='memberships', verbose_name='skupina')
    song = models.ForeignKey(Song, on_delete=models.PROTECT, related_name='group_memberships', verbose_name='píseň')
    position = models.PositiveSmallIntegerField(default=0, verbose_name='pořadí')

    class Meta:
        ordering = ('group', 'position', 'id')
        verbose_name = 'píseň ve skupině'
        verbose_name_plural = 'písně ve skupině'
        constraints = (
            models.UniqueConstraint(fields=('group', 'song'), name='unique_song_in_group'),
        )

    def __str__(self) -> str:
        return f'{self.group_id}: {self.song_id}'


class CurationState(models.Model):
    """Single row. `version` grows with every change; `exported_version` = version of the last export."""

    version = models.PositiveIntegerField(default=0)
    exported_version = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = 'stav kurátorských dat'
        verbose_name_plural = 'stav kurátorských dat'

    def __str__(self) -> str:
        return f'verze {self.version} (exportováno {self.exported_version})'

    @property
    def has_unexported_changes(self) -> bool:
        return self.version != self.exported_version

    @classmethod
    def current(cls) -> CurationState:
        state, _ = cls.objects.get_or_create(pk=1)
        return state
