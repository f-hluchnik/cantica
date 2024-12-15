from django.db import models
from celebrations.models import Celebration, CelebrationType

class LiturgicalSeason(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name
    
class Occasion(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name
    
class Keyword(models.Model):
    word = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.word


class Song(models.Model):
    title = models.CharField(max_length=200)
    number = models.PositiveIntegerField()
    celebration = models.ManyToManyField(Celebration, related_name='songs', blank=True)
    celebration_types = models.ManyToManyField(CelebrationType, related_name='songs', blank=True, db_index=True)
    liturgical_season = models.ForeignKey(
        LiturgicalSeason,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='songs',
        db_index=True
    )
    occasions = models.ManyToManyField(Occasion, blank=True, related_name="songs", db_index=True)
    keywords = models.ManyToManyField(Keyword, blank=True, related_name="songs")
    

    def __str__(self):
        return f"{self.title} ({self.number})"
