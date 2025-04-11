from typing import ClassVar, List

from django.contrib import admin, messages
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.db import models
from django.db.models import QuerySet
from django.forms import ModelForm
from django.http import HttpRequest
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
    list_filter = ('song', 'condition_type', 'mass_part', 'priority', 'exclusive', 'can_be_main')
    search_fields = ('song__title', 'condition_type__name')

    def get_queryset(self, request: HttpRequest) -> QuerySet[models.Model]:
        return super().get_queryset(request).select_related('song', 'condition_type', 'mass_part', 'content_type')

    def save_model(
        self,
        request: HttpRequest,
        obj: SongRule,
        form: ModelForm,
        change: bool,
    ) -> None:
        if SongRule.objects.filter(
            song=obj.song,
            condition_type=obj.condition_type,
            content_type=obj.content_type,
            object_id=obj.object_id,
            mass_part=obj.mass_part,
            priority=obj.priority,
            exclusive=obj.exclusive,
            can_be_main=obj.can_be_main,
        ).exists():
            messages.error(request, 'This rule already exists.')
            return  # Prevent saving and stay on the same page
        super().save_model(request, obj, form, change)
        messages.success(request, 'The rule was successfully added.')
