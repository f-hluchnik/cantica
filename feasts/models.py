from django.db import models
from django.utils.text import slugify


class FeastType(models.Model):
    name = models.CharField(max_length=500, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Feast(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=500)
    types = models.ManyToManyField(FeastType, related_name='feasts')

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)  # Generate slug from name if not provided
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({', '.join(t.name for t in self.types.all())})"
    
class LiturgicalCalendar(models.Model):
    date = models.DateField(unique=True)
    season = models.CharField(max_length=500)
    celebrations = models.ManyToManyField(Feast, related_name='calendar_dates')

    def __str__(self):
        return f"{self.date} ({', '.join(c.slug for c in self.celebrations.all())})"
