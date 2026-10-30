"""Rule editing in the admin: checkbox lists for parts/dioceses/cycles, validation, and a date preview."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, ClassVar

from django import forms
from django.conf import settings
from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from catalog.models import Song, SongGroup, SongGroupMember
from engine.context import occurrence_ctx
from engine.load import rule_info
from engine.model import DayCtx
from engine.refs import RefError
from engine.resolve import rule_applies
from engine.vocab import PARTS
from liturgy.constants import DEFAULT_DIOCESE, DIOCESES
from liturgy.models import Celebration
from liturgy.periods import Periods
from rules.models import Rule
from rules.services import built_days, current_snapshot

PREVIEW_DAYS = 400
PREVIEW_LIMIT = 12


def _periods() -> Periods:
    return Periods.load(settings.CANTICA_PERIODS_FILE)


class RuleForm(forms.ModelForm):
    parts = forms.MultipleChoiceField(
        choices=PARTS, required=False, widget=forms.CheckboxSelectMultiple, label='části mše',
    )
    dioceses = forms.MultipleChoiceField(
        choices=[(d.code, d.name) for d in DIOCESES],
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='diecéze',
        help_text='nic nezaškrtnuto = všechny',
    )
    cycles = forms.MultipleChoiceField(
        choices=[('A', 'A'), ('B', 'B'), ('C', 'C')],
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='nedělní cykly',
        help_text='nic nezaškrtnuto = všechny',
    )
    celebration = forms.ChoiceField(required=False, label='slavení')
    period = forms.ChoiceField(required=False, label='období')

    class Meta:
        model = Rule
        fields = '__all__'  # the admin fieldsets decide the layout

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        celebrations = [(c.key, f'{c.name} ({c.key})') for c in Celebration.objects.order_by('name')]
        periods = [(p.key, f'{p.name} ({p.key})') for p in _periods().items.values()]
        self._known = {'celebration': {k for k, _ in celebrations}, 'period': {k for k, _ in periods}}
        self.fields['celebration'].choices = [('', '—'), *celebrations]
        self.fields['period'].choices = [('', '—'), *periods]
        # Keep a key that no longer exists visible (and rejected by clean_*), instead of silently showing "—".
        for name in ('celebration', 'period'):
            value = getattr(self.instance, name, '')
            if value and value not in self._known[name]:
                self.fields[name].choices = [*self.fields[name].choices, (value, f'{value} (neznámé)')]
        if self.instance and self.instance.pk:
            self.initial['parts'] = [p for p in self.instance.parts.split(',') if p]
            self.initial['dioceses'] = [d for d in self.instance.dioceses.split(',') if d]
            self.initial['cycles'] = list(self.instance.cycles)

    def _known_key(self, name: str) -> str:
        value = self.cleaned_data[name]
        if value and value not in self._known[name]:
            raise forms.ValidationError(f'Neznámý klíč {value!r}.')
        return value

    def clean_celebration(self) -> str:
        return self._known_key('celebration')

    def clean_period(self) -> str:
        return self._known_key('period')

    def clean_parts(self) -> str:
        return ','.join(self.cleaned_data['parts'])

    def clean_dioceses(self) -> str:
        return ','.join(self.cleaned_data['dioceses'])

    def clean_cycles(self) -> str:
        return ''.join(sorted(self.cleaned_data['cycles']))

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean()
        if cleaned.get('kind') not in ('songs', 'neighbours'):
            cleaned['strength'] = 'recommended'  # strength means nothing for notes and silence
        if self.errors:
            return cleaned
        rule = Rule(**{k: v for k, v in cleaned.items() if k in {f.name for f in Rule._meta.fields}})
        codes = set(Song.objects.values_list('code', flat=True))
        groups: dict[str, list[str]] = {key: [] for key in SongGroup.objects.values_list('key', flat=True)}
        for group_id, song_id in SongGroupMember.objects.values_list('group_id', 'song_id'):
            groups[group_id].append(song_id)
        record = rule.to_record()
        prefix = f'{record.label}: '
        problems = [p.removeprefix(prefix) for p in record.problems(codes, groups)]
        if problems:
            raise forms.ValidationError(problems)
        return cleaned


@admin.register(Rule)
class RuleAdmin(admin.ModelAdmin):
    form = RuleForm
    list_display = ('position', 'scope', 'parts_display', 'kind', 'strength', 'songs', 'source', 'active')
    list_display_links = ('position', 'scope')
    list_filter = ('kind', 'strength', 'season', 'category', 'occasion', 'active', ('page', admin.EmptyFieldListFilter))
    search_fields = ('songs', 'celebration', 'period', 'note', 'internal')
    list_per_page = 100
    readonly_fields = ('preview',)
    fieldsets: ClassVar = (
        ('Kdy', {
            'fields': ('celebration', 'category', 'period', 'season', 'cycles', 'day', 'min_rank', 'dioceses',
                       'occasion'),
            'description': 'Nejkonkrétnější vyplněné pole určuje úroveň (▲ slavení, ■ kategorie, ● období/doba); '
                           'všechna vyplněná pole musí platit současně.',
        }),
        ('Co', {'fields': ('parts', 'kind', 'strength', 'songs', 'fallback', 'window_days', 'note')}),
        ('Zdroj', {'fields': ('page', 'position', 'active', 'internal')}),
        ('Náhled', {'fields': ('preview',)}),
    )

    @admin.display(description='kdy')
    def scope(self, obj: Rule) -> str:
        if obj.occasion:
            return f'příležitost: {obj.get_occasion_display()}'
        for name, prefix in (('celebration', '▲ '), ('category', '■ '), ('period', '● '), ('season', '● ')):
            value = getattr(obj, name)
            if value:
                return prefix + (obj.get_category_display() if name == 'category' else
                                 obj.get_season_display() if name == 'season' else value)
        return '● vždy'

    @admin.display(description='části')
    def parts_display(self, obj: Rule) -> str:
        labels = dict(PARTS)
        return ', '.join(labels.get(p, p) for p in obj.parts.split(',') if p)

    @admin.display(description='zdroj')
    def source(self, obj: Rule) -> str:
        return f's. {obj.page}' if obj.page else 'autor'

    @admin.display(description='platí ve dnech')
    def preview(self, obj: Rule) -> str:
        if not obj or not obj.pk:
            return 'Náhled se zobrazí po uložení.'
        if obj.occasion:
            return format_html('Pravidlo pro příležitost – viz <a href="{}">stránku příležitosti</a>.',
                               reverse('occasion', kwargs={'key': obj.occasion}))
        try:
            info = rule_info(obj.to_record(), obj.pk)
        except RefError as exc:
            return str(exc)
        snap, categories = current_snapshot()
        today = timezone.localdate()
        diocese = next(iter(obj.dioceses.split(',')), '') or DEFAULT_DIOCESE
        hits = []
        for day, built in sorted(built_days(diocese, today, today + timedelta(days=PREVIEW_DAYS)).items()):
            ctx = DayCtx(day, diocese, built.season, built.season_week, built.sunday_cycle, built.ferial_cycle, ())
            periods = snap.periods.active(day, built.season, built.season_week)
            occurrences = [o for o in occurrence_ctx(built, categories) if o.is_mass_option]
            hit = next((o for o in occurrences if rule_applies(info, ctx, o, periods)), None)
            if hit is not None:
                hits.append((day, hit.title))
            if len(hits) >= PREVIEW_LIMIT:
                break
        if not hits:
            return f'V příštích {PREVIEW_DAYS} dnech (diecéze {diocese}) se pravidlo neuplatní.'
        return format_html(
            '<ul>{}</ul>',
            format_html_join(
                '',
                '<li><a href="{}?dieceze={}">{}</a> – {}</li>',
                ((reverse('day', kwargs={'day': d}), diocese, d.strftime('%d. %m. %Y'), t) for d, t in hits),
            ),
        )
