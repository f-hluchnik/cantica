"""JSON API (design §9.4): the day's recommendations as plain JSON. Unstable until v2.1."""
from __future__ import annotations

from datetime import date

from django.http import HttpRequest, JsonResponse

from engine.plan import PlanEntry
from engine.recommend import DayResult, MassResult
from engine.resolve import Item, Reason, SongRef
from liturgy.constants import DEFAULT_DIOCESE, SEASON_LABELS
from liturgy.models import Diocese
from rules.services import day_result

API_VERSION = 'v1'


def _reason(reason: Reason) -> dict:
    return {'source': reason.source, 'note': reason.note, 'neighbour': reason.neighbour}


def _song(song: SongRef) -> dict:
    return {'code': song.code, 'title': song.title, 'verses': song.verses, 'url': song.url}


def _item(item: Item) -> dict:
    return {
        'kind': item.kind,
        'label': item.label,
        'tier': item.tier,
        'strength': item.strength,
        'songs': [_song(s) for s in item.songs],
        'reasons': [_reason(r) for r in item.reasons],
    }


def _plan_entry(entry: PlanEntry) -> dict:
    return {
        'part': entry.part,
        'label': entry.label,
        'kind': entry.kind,
        'tier': entry.tier,
        'songs': [_song(s) for s in entry.songs],
        'note': entry.note,
        'notes': entry.notes,
        'reasons': [_reason(r) for r in entry.reasons],
    }


def _mass(mass: MassResult) -> dict:
    return {
        'title': mass.title,
        'rank': mass.rank_label,
        'colour': mass.colour,
        'gloria': mass.norms.gloria,
        'credo': mass.norms.credo,
        'notes': [*([mass.norms.note] if mass.norms.note else []), *mass.notes],
        'summary': [
            {'part': line.part, 'label': line.label, 'items': [_item(i) for i in line.items]}
            for line in mass.summary
        ],
        'parts': [
            {'part': p.part, 'label': p.label, 'silenced': p.silenced, 'notes': p.notes,
             'items': [_item(i) for i in p.items]}
            for p in mass.parts
        ],
        'plan': [_plan_entry(e) for e in mass.plan],
        'gap': mass.gap,
    }


def serialize_day(result: DayResult, diocese: str) -> dict:
    ctx = result.ctx
    return {
        'api': API_VERSION,
        'date': ctx.date.isoformat(),
        'diocese': diocese,
        'season': ctx.season,
        'season_label': SEASON_LABELS.get(ctx.season, ''),
        'season_week': ctx.season_week,
        'sunday_cycle': ctx.sunday_cycle,
        'ferial_cycle': ctx.ferial_cycle,
        'notes': result.notes,
        'masses': [_mass(m) for m in result.masses],
        'commemorations': result.commemorations,
    }


def day_json(request: HttpRequest, day: date) -> JsonResponse:
    codes = set(Diocese.objects.values_list('code', flat=True))
    diocese = request.GET.get('dieceze') or request.GET.get('diocese') or DEFAULT_DIOCESE
    if diocese not in codes:
        return JsonResponse({'error': f'unknown diocese {diocese!r}', 'dioceses': sorted(codes)}, status=400)
    result = day_result(diocese, day)
    if result is None:
        return JsonResponse({'error': 'no calendar data for this day', 'date': day.isoformat()}, status=404)
    response = JsonResponse(serialize_day(result, diocese), json_dumps_params={'ensure_ascii': False})
    response['Cache-Control'] = 'public, max-age=300'
    response['Access-Control-Allow-Origin'] = '*'
    return response
