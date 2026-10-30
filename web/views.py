from __future__ import annotations

import hashlib
import os
import time
from datetime import date, timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseNotModified, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import patch_vary_headers

from engine.vocab import OCCASION_LABELS, OCCASIONS
from liturgy.constants import DEFAULT_DIOCESE, SEASON_LABELS
from liturgy.dbbuild import latest_build
from liturgy.models import Diocese
from liturgy.services import health
from rules.services import cache_key, day_result, occasion_page

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


def _evening(day: date, diocese: str) -> tuple[str, object] | None:
    """Saturday and 24 December: the evening mass is already of the next day (Sunday / Christmas vigil)."""
    if day.weekday() == 5:
        label = 'Večerní mše z neděle'
    elif (day.month, day.day) == (12, 24):
        label = 'Večerní mše z vigilie Narození Páně'
    else:
        return None
    following = day_result(diocese, day + timedelta(days=1))
    return (label, following) if following and following.masses else None


# Changes with every deploy (new process): cached pages never outlive the templates and the hashed CSS they use.
CODE_VERSION = os.environ.get('FLY_IMAGE_REF') or str(time.time())


def _etag(request: HttpRequest, day: date) -> str:
    diocese = request.GET.get('dieceze') or request.COOKIES.get(settings.CANTICA_DIOCESE_COOKIE, '')
    raw = '|'.join(str(p) for p in (
        day, diocese, request.GET.get('fragment', ''), timezone.localdate(), *cache_key(), CODE_VERSION,
    ))
    return '"' + hashlib.sha256(raw.encode()).hexdigest()[:20] + '"'


def _day_context(request: HttpRequest, day: date, diocese: Diocese, dioceses: dict[str, Diocese]) -> dict:
    today = timezone.localdate()
    build = latest_build()
    result = day_result(diocese.code, day)
    evening = _evening(day, diocese.code) if result else None
    return {
        'day': day,
        'today': today,
        'is_today': day == today,
        'previous_day': day - timedelta(days=1),
        'next_day': day + timedelta(days=1),
        'diocese': diocese,
        'dioceses': list(dioceses.values()),
        'result': result,
        'evening_label': evening[0] if evening else '',
        'evening': evening[1] if evening else None,
        'season_label': SEASON_LABELS.get(result.ctx.season, '') if result else '',
        'data_first': build.first_date if build else None,
        'data_last': build.last_date if build else None,
    }


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

    day = day or timezone.localdate()
    dioceses = {d.code: d for d in Diocese.objects.all()}
    if not dioceses:
        return HttpResponse('Aplikace se připravuje.', status=503, content_type='text/plain; charset=utf-8')
    diocese, store_cookie = _requested_diocese(request, dioceses)

    # Always revalidate (cheap 304); in development never cache, so template and CSS edits show at once.
    etag = None if settings.DEBUG else _etag(request, day)
    if etag and not store_cookie and etag in request.headers.get('If-None-Match', ''):
        response = HttpResponseNotModified()
    else:
        context = _day_context(request, day, diocese, dioceses)
        template = 'web/_day.html' if request.GET.get('fragment') else 'web/day.html'
        response = render(request, template, context)
    if etag:
        response['ETag'] = etag
        response['Cache-Control'] = 'private, no-cache'
    else:
        response['Cache-Control'] = 'no-store'
    patch_vary_headers(response, ('Cookie',))
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


def robots_txt(request: HttpRequest) -> HttpResponse:
    if settings.CANTICA_NOINDEX:
        body = 'User-agent: *\nDisallow: /\n'
    else:
        body = 'User-agent: *\nDisallow: /admin/\nDisallow: /api/\nDisallow: /*?fragment=1\n'
    return HttpResponse(body, content_type='text/plain; charset=utf-8')


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
