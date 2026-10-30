from __future__ import annotations

from datetime import date, timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from engine.vocab import OCCASION_LABELS, OCCASIONS
from liturgy.constants import DEFAULT_DIOCESE, SEASON_LABELS
from liturgy.dbbuild import latest_build
from liturgy.models import Diocese
from liturgy.services import health
from rules.services import day_result, occasion_page

COOKIE_MAX_AGE = 365 * 24 * 3600


def _requested_diocese(request: HttpRequest, dioceses: dict[str, Diocese]) -> tuple[Diocese, bool]:
    """(diocese to show, whether to store it in the cookie). Unknown codes fall back silently."""
    from_query = request.GET.get('dieceze')
    if from_query in dioceses:
        return dioceses[from_query], request.COOKIES.get(settings.CANTICA_DIOCESE_COOKIE) != from_query
    from_cookie = request.COOKIES.get(settings.CANTICA_DIOCESE_COOKIE)
    if from_cookie in dioceses:
        return dioceses[from_cookie], False
    return dioceses.get(DEFAULT_DIOCESE) or next(iter(dioceses.values())), False


def day_page(request: HttpRequest, day: date | None = None) -> HttpResponse:
    # Date picker (and v1 links ?date=...) -> clean URL /YYYY-MM-DD/
    picked = request.GET.get('datum') or request.GET.get('date')
    if picked:
        try:
            target = date.fromisoformat(picked)
        except ValueError:
            return redirect('today')
        url = reverse('day', kwargs={'day': target})
        if 'dieceze' in request.GET:
            url += '?' + urlencode({'dieceze': request.GET['dieceze']})
        return redirect(url)

    today = timezone.localdate()
    day = day or today
    dioceses = {d.code: d for d in Diocese.objects.all()}
    if not dioceses:
        return HttpResponse('Aplikace se připravuje.', status=503, content_type='text/plain; charset=utf-8')
    diocese, store_cookie = _requested_diocese(request, dioceses)

    build = latest_build()
    result = day_result(diocese.code, day)
    context = {
        'day': day,
        'today': today,
        'is_today': day == today,
        'previous_day': day - timedelta(days=1),
        'next_day': day + timedelta(days=1),
        'is_saturday': day.weekday() == 5,
        'diocese': diocese,
        'dioceses': list(dioceses.values()),
        'result': result,
        'season_label': SEASON_LABELS.get(result.ctx.season, '') if result else '',
        'data_first': build.first_date if build else None,
        'data_last': build.last_date if build else None,
    }
    response = render(request, 'web/day.html', context)
    if store_cookie:
        response.set_cookie(
            settings.CANTICA_DIOCESE_COOKIE,
            diocese.code,
            max_age=COOKIE_MAX_AGE,
            samesite='Lax',
            httponly=True,
            secure=request.is_secure(),
        )
    return response


def occasions_page(request: HttpRequest, key: str | None = None) -> HttpResponse:
    if key is not None and key not in OCCASION_LABELS:
        raise Http404('Neznámá příležitost')
    context = {
        'occasions': OCCASIONS,
        'selected': key,
        'result': occasion_page(key) if key else None,
    }
    return render(request, 'web/occasions.html', context)


def about_page(request: HttpRequest) -> HttpResponse:
    return render(request, 'web/about.html')


def health_check(request: HttpRequest) -> JsonResponse:
    """Data freshness for monitoring: 'ok', 'warn' (< CANTICA_HEALTH_MIN_DAYS_AHEAD days left) or 'error'."""
    result = health(settings.CANTICA_HEALTH_MIN_DAYS_AHEAD)
    payload = {
        'status': result.status,
        'calendar_last_date': result.last_date.isoformat() if result.last_date else None,
        'calendar_days_ahead': result.days_ahead,
        'calendar_built_at': result.built_at,
    }
    return JsonResponse(payload, status=503 if result.status == 'error' else 200)
