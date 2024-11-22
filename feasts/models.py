from django.db import models

class FeastType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Feast(models.Model):
    name = models.CharField(max_length=200)
    types = models.ManyToManyField(FeastType, related_name='feasts')
    degree = models.CharField(max_length=50, choices=[
        ('mandatory', 'Mandatory'),
        ('optional', 'Optional'),
        ('recommended', 'Recommended')
    ])
    date = models.DateField()

    def __str__(self):
        return f"{self.name} ({', '.join(t.name for t in self.types.all())})"
