"""Rules: one clause of the Direktář (or an author's convention) each. Edited in the admin.

Scope and filters are plain values (celebration key, category, period key, season, …), not FKs:
celebrations and periods live in git (data/liturgy/), and dangling references are caught by
validation in the admin and by lint in CI.
"""
from __future__ import annotations

from django.db import models

from catalog.rulerecords import RuleRecord
from engine.vocab import DAY_KINDS, KINDS, MIN_RANKS, STRENGTHS
from liturgy.constants import CATEGORIES, SEASONS

MIN_RANK_CHOICES = [(key, label) for key, label, _ in MIN_RANKS]
SONGS_HELP = (
    'Čárkou oddělené: 523 · 813B · Z781 · 838/5 (sloka) · 838/1+3 · 691-695 (rozsah) · '
    '@mesni_obecne (skupina) · #advent (oddíl Kancionálu)'
)


def _split(value: str) -> list[str]:
    return [v.strip() for v in value.split(',') if v.strip()]


class Rule(models.Model):
    # scope (the most specific one set decides the tier ▲ ■ ●); every set field must also match
    celebration = models.CharField(max_length=120, blank=True, verbose_name='slavení')
    category = models.CharField(max_length=32, blank=True, choices=CATEGORIES, verbose_name='kategorie slavení')
    period = models.CharField(max_length=48, blank=True, verbose_name='období')
    season = models.CharField(max_length=16, blank=True, choices=SEASONS, verbose_name='liturgická doba')
    # filters
    cycles = models.CharField(max_length=3, blank=True, verbose_name='nedělní cykly')
    day = models.CharField(max_length=8, blank=True, choices=DAY_KINDS, verbose_name='den')
    min_rank = models.CharField(max_length=24, blank=True, choices=MIN_RANK_CHOICES, verbose_name='nejnižší stupeň')
    dioceses = models.CharField(max_length=100, blank=True, verbose_name='diecéze')
    # what
    parts = models.CharField(max_length=300, blank=True, verbose_name='části mše')
    kind = models.CharField(max_length=12, choices=KINDS, default='songs', verbose_name='druh')
    strength = models.CharField(max_length=12, choices=STRENGTHS, default='recommended', verbose_name='síla')
    songs = models.CharField(max_length=500, blank=True, verbose_name='písně', help_text=SONGS_HELP)
    window_days = models.PositiveSmallIntegerField(default=7, verbose_name='okno (dny)')
    note = models.TextField(blank=True, verbose_name='poznámka pro uživatele')
    internal = models.TextField(blank=True, verbose_name='interní poznámka')
    # source
    page = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='strana Direktáře',
        help_text='prázdné = doporučení autora',
    )
    position = models.PositiveIntegerField(default=0, verbose_name='pořadí')
    active = models.BooleanField(default=True, verbose_name='aktivní')

    class Meta:
        ordering = ('position', 'id')
        verbose_name = 'pravidlo'
        verbose_name_plural = 'pravidla'

    def __str__(self) -> str:
        return self.to_record().label

    def to_record(self) -> RuleRecord:
        return RuleRecord(
            parts=_split(self.parts),
            kind=self.kind,
            strength=self.strength,
            songs=self.songs,
            celebration=self.celebration,
            category=self.category,
            period=self.period,
            season=self.season,
            cycles=self.cycles,
            day=self.day,
            min_rank=self.min_rank,
            dioceses=_split(self.dioceses),
            window_days=self.window_days,
            note=self.note,
            internal=self.internal,
            page=self.page,
            position=self.position,
            active=self.active,
            id=self.pk,
        )

    @classmethod
    def from_record(cls, record: RuleRecord) -> Rule:
        return cls(
            celebration=record.celebration,
            category=record.category,
            period=record.period,
            season=record.season,
            cycles=record.cycles,
            day=record.day,
            min_rank=record.min_rank,
            dioceses=','.join(record.dioceses),
            parts=','.join(record.parts),
            kind=record.kind,
            strength=record.strength,
            songs=record.songs,
            window_days=record.window_days,
            note=record.note,
            internal=record.internal,
            page=record.page,
            position=record.position,
            active=record.active,
        )
