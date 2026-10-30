"""Curation UI: songs (verse suitability) and song groups. Every save bumps the curation version."""
from __future__ import annotations

from typing import ClassVar

from django.contrib import admin
from django.db.models import Count, Q, QuerySet
from django.forms import BaseInlineFormSet, ModelForm
from django.http import HttpRequest
from django.utils.html import format_html

from catalog.codes import VERSES_DEDICATED, VERSES_NONE
from catalog.models import CurationState, Song, SongGroup, SongGroupMember


class VerseStatusFilter(admin.SimpleListFilter):
    field_name = ''
    options: ClassVar = (
        ('unknown', 'neověřeno'),
        ('none', 'nemá (-)'),
        ('dedicated', 'podle Kancionálu (*)'),
        ('specific', 'konkrétní sloky'),
    )

    def lookups(self, request: HttpRequest, model_admin: admin.ModelAdmin) -> tuple:
        return self.options

    def queryset(self, request: HttpRequest, queryset: QuerySet) -> QuerySet:
        f = self.field_name
        value = self.value()
        if value == 'unknown':
            return queryset.filter(**{f'{f}__isnull': True})
        if value == 'none':
            return queryset.filter(**{f: VERSES_NONE})
        if value == 'dedicated':
            return queryset.filter(**{f: VERSES_DEDICATED})
        if value == 'specific':
            return queryset.exclude(Q(**{f'{f}__isnull': True}) | Q(**{f'{f}__in': (VERSES_NONE, VERSES_DEDICATED)}))
        return queryset


class CommunionFilter(VerseStatusFilter):
    title = 'k přijímání'
    parameter_name = 'prijimani'
    field_name = 'communion_verses'


class RecessionalFilter(VerseStatusFilter):
    title = 'na závěr'
    parameter_name = 'zaver'
    field_name = 'recessional_verses'


@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    list_display = (
        'code', 'title', 'section', 'mass_song', 'communion_verses', 'recessional_verses',
        'verse_count', 'reviewed', 'kancional_link',
    )
    list_display_links = ('code', 'title')
    list_editable = ('mass_song', 'communion_verses', 'recessional_verses', 'verse_count', 'reviewed')
    list_filter = ('section', 'reviewed', 'mass_song', CommunionFilter, RecessionalFilter)
    search_fields = ('code', 'title')
    list_per_page = 100
    fields = (
        'code', 'number', 'title', 'section', 'mass_song', 'communion_verses', 'recessional_verses',
        'verse_count', 'reviewed', 'note',
    )

    def get_readonly_fields(self, request: HttpRequest, obj: Song | None = None) -> tuple[str, ...]:
        # The code is the primary key: changing it would create a new song.
        return ('code', 'number') if obj else ('number',)

    @admin.display(description='kancional.cz')
    def kancional_link(self, obj: Song) -> str:
        return format_html('<a href="{}" target="_blank" rel="noopener">otevřít</a>', obj.kancional_url)


class SongGroupMemberInline(admin.TabularInline):
    model = SongGroupMember
    extra = 1
    autocomplete_fields = ('song',)
    fields = ('song', 'position')
    ordering = ('position', 'id')


@admin.register(SongGroup)
class SongGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'key', 'source_page', 'member_count')
    search_fields = ('name', 'key', 'description')
    inlines: ClassVar = [SongGroupMemberInline]

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).annotate(_member_count=Count('memberships'))

    def get_readonly_fields(self, request: HttpRequest, obj: SongGroup | None = None) -> tuple[str, ...]:
        return ('key',) if obj else ()

    def save_formset(self, request: HttpRequest, form: ModelForm, formset: BaseInlineFormSet, change: bool) -> None:
        """New rows without an explicit position go to the end of the group."""
        members = formset.save(commit=False)
        last = max(
            (m.position for m in SongGroupMember.objects.filter(group=form.instance)),
            default=0,
        )
        for member in members:
            if not member.position:
                last += 1
                member.position = last
            member.save()
        for deleted in formset.deleted_objects:
            deleted.delete()
        formset.save_m2m()

    @admin.display(description='počet písní', ordering='_member_count')
    def member_count(self, obj: SongGroup) -> int:
        return obj._member_count


@admin.register(CurationState)
class CurationStateAdmin(admin.ModelAdmin):
    list_display = ('version', 'exported_version', 'unexported')

    def has_add_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False

    @admin.display(description='neexportované změny', boolean=True)
    def unexported(self, obj: CurationState) -> bool:
        return obj.has_unexported_changes
