from django.shortcuts import render
from rest_framework.generics import ListAPIView
from .models import Feast
from .serializers import FeastSerializer

class FeastListView(ListAPIView):
    queryset = Feast.objects.all()
    serializer_class = FeastSerializer
