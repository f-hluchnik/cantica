from django.db import models

class Song(models.Model):
    title = models.CharField(max_length=200)
    number = models.PositiveIntegerField()
    section = models.CharField(max_length=255, blank=True, editable=False)  # Computed
    feast_types = models.ManyToManyField('feasts.FeastType', blank=True)

    @property
    def section(self):
        return self.number // 100
    
    def save(self, *args, **kwargs):
        self.section = self.number
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} (Section {self.section})"
