"""Client for calapi.inadiutorium.cz (Church Calendar API). Pure module: must not import Django.

Used only by the sync command, never while serving pages. The service is volunteer-run and
HTTP only (the HTTPS endpoint returns an empty body), so every call has a short timeout and retries.
"""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

BASE_URL = 'http://calapi.inadiutorium.cz/api/v0/cs/calendars'
USER_AGENT = 'directus-cantica-calendar-sync (+https://directuscantica.cz)'


class CalapiError(RuntimeError):
    """The API could not be reached or returned something unusable."""


class CalapiClient:
    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: float = 10.0,
        retries: int = 3,
        backoff: float = 2.0,
        opener: Callable[..., Any] = urlopen,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self._opener = opener
        self._sleep = sleep

    def month_url(self, calendar: str, year: int, month: int) -> str:
        return f'{self.base_url}/{calendar}/{year}/{month}'

    def month(self, calendar: str, year: int, month: int) -> Any:
        return self._get_json(self.month_url(calendar, year, month))

    def year_info(self, calendar: str, year: int) -> Any:
        """{lectionary, ferial_lectionary} of the liturgical year that BEGINS in Advent of `year`."""
        return self._get_json(f'{self.base_url}/{calendar}/{year}')

    def _get_json(self, url: str) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                request = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})  # noqa: S310
                with self._opener(request, timeout=self.timeout) as response:
                    body = response.read()
                if not body:
                    raise CalapiError(f'{url}: empty response')
                return json.loads(body.decode('utf-8'))
            except HTTPError as exc:
                if 400 <= exc.code < 500 and exc.code != 429:
                    raise CalapiError(f'{url}: HTTP {exc.code}') from exc
                last_error = exc
            except (URLError, TimeoutError, OSError, ValueError, CalapiError) as exc:
                last_error = exc
            if attempt < self.retries:
                delay = self.backoff ** (attempt - 1)
                logger.warning('calapi attempt %s/%s failed for %s (%s); retrying in %.1fs',
                               attempt, self.retries, url, last_error, delay)
                self._sleep(delay)
        raise CalapiError(f'{url}: giving up after {self.retries} attempts ({last_error})')
