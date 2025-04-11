from typing import Any, ClassVar, Dict, List

from dal import autocomplete
from django import forms
from django.contrib.contenttypes.models import ContentType

from .models import ConditionType, LiturgicalSeason, SongRule


class SongRuleForm(forms.ModelForm):
    # This field will be rendered with an autocomplete widget.
    condition_value_field = forms.ModelChoiceField(
        queryset=LiturgicalSeason.objects.all(),  # The queryset will be provided by the autocomplete view.
        widget=autocomplete.ListSelect2(
            url='condition-value-autocomplete',
            forward=['condition_type'],  # Forward the selected condition_type to the view.
        ),
        label='Condition Value',
        required=True,
    )

    class Meta:
        model = SongRule
        # Note: We do not include content_type or object_id in the form.
        fields: ClassVar[List] = [
            'song',
            'condition_type',
            'condition_value_field',
            'mass_part',
            'priority',
            'exclusive',
            'can_be_main',
        ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # If editing an instance, initialize the autocomplete field with the current condition value.
        if self.instance and self.instance.pk:
            self.fields['condition_value_field'].initial = self.instance.condition_value
        if 'condition_type' in self.data:
            try:
                condition_type_id = self.data.get('condition_type')
                cond_type = ConditionType.objects.get(pk=condition_type_id)
                model_class = cond_type.content_type.model_class()
                self.fields['condition_value_field'].queryset = model_class.objects.all()
            except (ConditionType.DoesNotExist, ValueError):
                self.fields['condition_value_field'].queryset = LiturgicalSeason.objects.none()
        # If editing an existing instance, update queryset based on the condition_value of the instance
        elif self.instance and self.instance.pk:
            condition_obj = self.instance.condition_value
            if condition_obj:
                self.fields['condition_value_field'].queryset = type(condition_obj).objects.all()

    def clean(self) -> Dict[str, Any]:
        cleaned_data = super().clean()
        condition_obj = cleaned_data.get('condition_value_field')
        if condition_obj:
            ct = ContentType.objects.get_for_model(condition_obj)
            cleaned_data['content_type'] = ct
            cleaned_data['object_id'] = condition_obj.pk
        return cleaned_data

    def save(self, commit: bool = True) -> SongRule:

        instance = super().save(commit=False)
        # Set the generic relation fields from the cleaned_data.
        instance.content_type = self.cleaned_data.get('content_type')
        instance.object_id = self.cleaned_data.get('object_id')
        if commit:
            instance.save()
        return instance
