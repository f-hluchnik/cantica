from django.contrib import admin
from .models import Feast, FeastType

@admin.register(FeastType)
class FeastTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Feast)
class FeastAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'degree')
    list_filter = ('degree', 'types')
