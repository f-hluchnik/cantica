from typing import ClassVar

from rest_framework import serializers

from .models import Celebration, CelebrationType


class CelebrationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CelebrationType
        fields: ClassVar = ['id', 'name']


class CelebrationSerializer(serializers.ModelSerializer):
    types = CelebrationTypeSerializer(many=True)

    class Meta:
        model = Celebration
        fields: ClassVar = ['id', 'name', 'types']
