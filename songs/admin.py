from django.contrib import admin
from .models import Song, LiturgicalSeason, Occasion, Keyword

@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    list_display = ('title', 'number',)
    list_filter = ('celebration_types', 'liturgical_season', 'occasions', 'keywords')

@admin.register(LiturgicalSeason)
class LiturgicalSeasonAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Occasion)
class OccasionAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    list_display = ('word',)
