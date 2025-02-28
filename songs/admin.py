from typing import ClassVar

from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.db import models

from .models import Keyword, LiturgicalSeason, Occasion, Song


@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    list_display = ('title', 'number')
    list_filter = (
        'celebration_types',
        'liturgical_season',
        'occasions',
        'keywords',
    )
    formfield_overrides: ClassVar = {
        models.ManyToManyField: {
            'widget': FilteredSelectMultiple(
                'Related Models',
                is_stacked=False,
            ),
        },
    }


@admin.register(LiturgicalSeason)
class LiturgicalSeasonAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(Occasion)
class OccasionAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    list_display = ('word',)
