from typing import ClassVar, List

from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.db import models
from django.urls import reverse
from django.utils.html import format_html

from songs.forms import SongRuleForm

from .models import ConditionType, Keyword, LiturgicalSeason, LiturgicalSubSeason, MassPart, Song, SongRule


class SongRuleInline(admin.TabularInline):
    model = SongRule
    form = SongRuleForm
    extra = 0
    can_delete = False  # Optional: disallow deletion in the inline
    readonly_fields = ('display_rule',)

    def display_rule(self, obj: SongRule) -> str:
        if obj.pk:
            url = reverse('admin:songs_songrule_change', args=[obj.pk])
            return format_html('<a href="{}">Edit Rule</a>', url)
        return ''
    display_rule.short_description = 'Song Rule'


@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    list_display = ('title', 'number')
    list_filter = (
        'keywords',
    )
    search_fields = ('title', 'number')
    inlines: ClassVar[List] = [SongRuleInline]
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


@admin.register(LiturgicalSubSeason)
class LiturgicalSubSeasonAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(MassPart)
class MassPartAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    list_display = ('word',)


@admin.register(ConditionType)
class ConditionTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(SongRule)
class SongRuleAdmin(admin.ModelAdmin):
    form = SongRuleForm
    autocomplete_fields: ClassVar[List] = ['song']
    list_display = ('song', 'condition_type', 'condition_value', 'mass_part', 'priority', 'exclusive', 'can_be_main')
