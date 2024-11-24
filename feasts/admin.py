from django.contrib import admin
from .models import Feast, FeastType, LiturgicalCalendar

@admin.register(LiturgicalCalendar)
class LiturgicalCalendarAdmin(admin.ModelAdmin):
    list_display = ('date',)

@admin.register(FeastType)
class FeastTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Feast)
class FeastAdmin(admin.ModelAdmin):
    list_display = ('name',)
    list_filter = ('types',)
