from django.db import models
from django.utils.text import slugify


class CelebrationType(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Celebration(models.Model):
    slug = models.SlugField(unique=True, max_length=200)
    name = models.CharField(max_length=200)
    types = models.ManyToManyField(CelebrationType, related_name='celebrations')

    class Meta:
        ordering = ['name']  # Sort alphabetically by 'name'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({', '.join(t.name for t in self.types.all())})"
    
class LiturgicalCalendarEvent(models.Model):
    date = models.DateField(unique=True)
    season = models.CharField(max_length=50)
    celebrations = models.ManyToManyField(Celebration, related_name='liturgical_calendar_events')

    def __str__(self):
        return f"{self.date}, {self.season}, ({', '.join(c.slug for c in self.celebrations.all())})"
