from typing import ClassVar

from rest_framework import serializers

from .models import Song


class SongSerializer(serializers.ModelSerializer):
    class Meta:
        model = Song
        fields: ClassVar = ['id', 'title', 'number', 'section', 'celebration_types']
