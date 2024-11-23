from django.db import models
from django.utils.text import slugify


class FeastType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Feast(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=200)
    types = models.ManyToManyField(FeastType, related_name='feasts')
    degree = models.CharField(max_length=50, choices=[
        ('mandatory', 'Mandatory'),
        ('optional', 'Optional'),
        ('recommended', 'Recommended')
    ])
    date = models.DateField()

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)  # Generate slug from name if not provided
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({', '.join(t.name for t in self.types.all())})"
