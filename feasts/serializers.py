from rest_framework import serializers
from .models import Feast, FeastType

class FeastTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeastType
        fields = ['id', 'name']

class FeastSerializer(serializers.ModelSerializer):
    types = FeastTypeSerializer(many=True)

    class Meta:
        model = Feast
        fields = ['id', 'name', 'types']
