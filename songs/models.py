from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class LiturgicalSeason(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self) -> str:
        return self.name


class LiturgicalSubSeason(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self) -> str:
        return self.name


class MassPart(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self) -> str:
        return self.name


class Keyword(models.Model):
    word = models.CharField(max_length=50, unique=True)

    def __str__(self) -> str:
        return self.word


class Song(models.Model):
    title = models.CharField(max_length=200)
    number = models.PositiveIntegerField()
    has_communion_verse = models.BooleanField(default=False)
    has_recessional_verse = models.BooleanField(default=False)
    keywords = models.ManyToManyField(Keyword, blank=True, related_name='songs')

    def __str__(self) -> str:
        return f'{self.title} ({self.number})'


class ConditionType(models.Model):
    name = models.CharField(max_length=100)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,       # Allow nulls temporarily
        blank=True,
        default=1,
        help_text='Select the ContentType corresponding to this condition.',
    )

    def __str__(self) -> str:
        return self.name


class SongRule(models.Model):
    song = models.ForeignKey('Song', on_delete=models.CASCADE)
    condition_type = models.ForeignKey('ConditionType', on_delete=models.CASCADE)

    # The following two fields (used in the GenericForeignKey) will be managed automatically.
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to={'model__in': ['liturgicalseason', 'liturgicalsubseason', 'celebration', 'celebrationtype']},
    )
    object_id = models.PositiveIntegerField()
    condition_value = GenericForeignKey('content_type', 'object_id')

    mass_part = models.ForeignKey('MassPart', on_delete=models.CASCADE)
    priority = models.IntegerField(
        default=0,
        choices=[
            (0, 'default'),
            (1, 'preferred'),
            (2, 'strongly preferred'),
            (3, 'mandatory'),
        ],
    )
    exclusive = models.BooleanField(
        default=False,
        help_text='if a song with exclusive=True is selected, no other song is allowed in that mass part.',
    )
    can_be_main = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f'{self.song} - {self.condition_type} - {self.condition_value}'
