"""Read-only admin: calendar data is rebuilt from data/ in git, so edits here would be lost."""
from __future__ import annotations

from typing import ClassVar

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from liturgy.models import CalendarBuild, CalendarDay, Category, Celebration, CelebrationAlias, Diocese, Occurrence


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False


class ReadOnlyInline(admin.TabularInline):
    extra = 0
    can_delete = False

    def has_add_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False


@admin.register(Diocese)
class DioceseAdmin(ReadOnlyAdmin):
    list_display = ('name', 'code', 'calapi_calendar')


@admin.register(Category)
class CategoryAdmin(ReadOnlyAdmin):
    list_display = ('name', 'key')


class AliasInline(ReadOnlyInline):
    model = CelebrationAlias
    fields = ('title',)


@admin.register(Celebration)
class CelebrationAdmin(ReadOnlyAdmin):
    list_display = ('name', 'key', 'categories_reviewed')
    list_filter = ('categories_reviewed', 'categories')
    search_fields = ('name', 'key', 'aliases__title')
    inlines: ClassVar = [AliasInline]


class OccurrenceInline(ReadOnlyInline):
    model = Occurrence
    fields = ('position', 'title', 'rank_label', 'rank_num', 'colour', 'celebration')


@admin.register(CalendarDay)
class CalendarDayAdmin(ReadOnlyAdmin):
    list_display = ('date', 'diocese', 'season', 'season_week', 'sunday_cycle', 'ferial_cycle')
    list_filter = ('diocese', 'season')
    date_hierarchy = 'date'
    inlines: ClassVar = [OccurrenceInline]

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).select_related('diocese')


@admin.register(CalendarBuild)
class CalendarBuildAdmin(ReadOnlyAdmin):
    list_display = ('built_at', 'first_date', 'last_date', 'days', 'source_digest')
