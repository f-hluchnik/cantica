from rest_framework.generics import ListAPIView
from .models import Song
from .serializers import SongSerializer


class SongListView(ListAPIView):
    queryset = Song.objects.all()
    serializer_class = SongSerializer
