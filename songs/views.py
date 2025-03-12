from typing import Optional

from dal import autocomplete
from django.contrib.admin.views.decorators import staff_member_required
from django.db import models
from django.db.models import QuerySet
from django.utils.decorators import method_decorator
from rest_framework.generics import ListAPIView

from .models import ConditionType, LiturgicalSeason, Song
from .serializers import SongSerializer


class SongListView(ListAPIView):
    queryset = Song.objects.all()
    serializer_class = SongSerializer


@method_decorator(staff_member_required, name='dispatch')
class ConditionValueAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self) -> QuerySet[models.Model]:
        # Get the forwarded condition_type value from the request.
        condition_type_id: Optional[int] = self.forwarded.get('condition_type')

        if condition_type_id is None:
            return ConditionType.objects.none()

        cond_type = ConditionType.objects.filter(pk=condition_type_id).first()
        if not cond_type:
            return ConditionType.objects.none()

        # Get the associated model class via the stored ContentType.
        model_class = cond_type.content_type.model_class()

        if not model_class:
            return LiturgicalSeason.objects.none()

        qs = model_class.objects.all()
        if self.q:
            # Assumes the target model has a 'name' field; adjust as needed.
            qs = qs.filter(name__icontains=self.q)
        return qs
