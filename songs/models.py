from django.db import models
from celebrations.models import Celebration, CelebrationType

class Song(models.Model):
    title = models.CharField(max_length=200)
    number = models.PositiveIntegerField()
    celebration = models.ManyToManyField(Celebration, related_name='songs', blank=True)
    celebration_types = models.ManyToManyField(CelebrationType, related_name='songs', blank=True)
    liturgical_season = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.title} ({self.number})"
