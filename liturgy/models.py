"""Calendar models. The DB is a mirror of data/ in git (snapshots + celebration catalog).

Nothing here is edited by hand: calendar_build rebuilds days and occurrences, and syncs
celebrations from data/liturgy/celebrations.yaml. The admin is therefore read-only.
"""
from __future__ import annotations

from django.db import models

from liturgy.constants import RANK_COMMEMORATION, SEASONS


class Diocese(models.Model):
    code = models.CharField(primary_key=True, max_length=16)
    name = models.CharField(max_length=100)
    calapi_calendar = models.CharField(max_length=32, unique=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ('position',)
        verbose_name = 'diecéze'
        verbose_name_plural = 'diecéze'

    def __str__(self) -> str:
        return self.name


class Category(models.Model):
    key = models.CharField(primary_key=True, max_length=32)
    name = models.CharField(max_length=100)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ('position',)
        verbose_name = 'kategorie slavení'
        verbose_name_plural = 'kategorie slavení'

    def __str__(self) -> str:
        return self.name


class Celebration(models.Model):
    key = models.CharField(primary_key=True, max_length=120)
    name = models.CharField(max_length=250)
    categories = models.ManyToManyField(Category, blank=True, related_name='celebrations')
    categories_reviewed = models.BooleanField(default=False)

    class Meta:
        ordering = ('name',)
        verbose_name = 'slavení'
        verbose_name_plural = 'slavení'

    def __str__(self) -> str:
        return self.name


class CelebrationAlias(models.Model):
    celebration = models.ForeignKey(Celebration, on_delete=models.CASCADE, related_name='aliases')
    title = models.CharField(max_length=250)

    class Meta:
        ordering = ('title',)
        verbose_name = 'jiný název'
        verbose_name_plural = 'jiné názvy'

    def __str__(self) -> str:
        return self.title


class CalendarDay(models.Model):
    diocese = models.ForeignKey(Diocese, on_delete=models.CASCADE, related_name='days')
    date = models.DateField()
    season = models.CharField(max_length=16, choices=SEASONS)
    season_week = models.PositiveSmallIntegerField()
    sunday_cycle = models.CharField(max_length=1)
    ferial_cycle = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ('date',)
        verbose_name = 'den'
        verbose_name_plural = 'dny'
        constraints = (
            models.UniqueConstraint(fields=('diocese', 'date'), name='unique_day_per_diocese'),
        )

    def __str__(self) -> str:
        return f'{self.date.isoformat()} ({self.diocese_id})'


class Occurrence(models.Model):
    day = models.ForeignKey(CalendarDay, on_delete=models.CASCADE, related_name='occurrences')
    position = models.PositiveSmallIntegerField()
    celebration = models.ForeignKey(
        Celebration,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='occurrences',
    )
    title = models.CharField(max_length=250)
    rank_label = models.CharField(max_length=40)
    rank_num = models.DecimalField(max_digits=4, decimal_places=2)
    colour = models.CharField(max_length=16)

    class Meta:
        ordering = ('day', 'position')
        verbose_name = 'slavení v kalendáři'
        verbose_name_plural = 'slavení v kalendáři'
        constraints = (
            models.UniqueConstraint(fields=('day', 'position'), name='unique_occurrence_position'),
        )

    def __str__(self) -> str:
        return self.title

    @property
    def is_mass_option(self) -> bool:
        return self.rank_label != RANK_COMMEMORATION


class CalendarBuild(models.Model):
    """One row per successful calendar_build; the latest one describes the data being served."""

    built_at = models.DateTimeField(auto_now_add=True)
    source_digest = models.CharField(max_length=64)
    first_date = models.DateField()
    last_date = models.DateField()
    days = models.PositiveIntegerField()

    class Meta:
        ordering = ('-built_at',)
        verbose_name = 'sestavení kalendáře'
        verbose_name_plural = 'sestavení kalendáře'

    def __str__(self) -> str:
        return f'{self.built_at:%Y-%m-%d %H:%M} ({self.first_date}..{self.last_date})'
