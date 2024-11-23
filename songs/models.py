from django.db import models
from feasts.models import Feast, FeastType

class Song(models.Model):
    title = models.CharField(max_length=200)
    number = models.PositiveIntegerField()
    feast_types = models.ManyToManyField('feasts.FeastType', blank=True)
    feast = models.ForeignKey(Feast, on_delete=models.CASCADE, null=True, blank=True)
    feast_types = models.ManyToManyField(FeastType, blank=True)  # Link to feast types
    liturgical_season = models.CharField(max_length=50, blank=True, null=True)  # E.g., "advent", "lent", etc.
    
    @property
    def section(self):
        return self.number // 100

    def __str__(self):
        return f"{self.title} (Section {self.section})"
