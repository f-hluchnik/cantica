from django.contrib import admin

from .models import Celebration, CelebrationType, LiturgicalCalendarEvent


@admin.register(LiturgicalCalendarEvent)
class LiturgicalCalendarEventAdmin(admin.ModelAdmin):
    list_display = ('date',)


@admin.register(CelebrationType)
class CelebrationTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(Celebration)
class CelebrationAdmin(admin.ModelAdmin):
    list_display = ('name',)
    list_filter = ('types',)
