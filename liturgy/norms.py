"""General liturgical norms computed from the calendar. Pure module: must not import Django.

Covers what is fixed by liturgical law rather than by the Direktář:
  * Easter, first Sunday of Advent, liturgical year, lectionary cycles,
  * whether Sláva na výsostech (Gloria) and Věřím (Credo) are sung,
  * Aleluja vs. Chvála tobě, Kriste before the gospel,
  * days without a Mass (Velký pátek, Bílá sobota).

Values are tri-state: True / False / None. None means "not applicable or not decided here",
and the UI shows nothing for it rather than guessing.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from liturgy.constants import (
    RANK_FEAST,
    RANK_FERIA,
    RANK_PRIMARY,
    RANK_SOLEMNITY,
    RANK_SUNDAY,
    RANK_TRIDUUM,
)
from liturgy.keys import slugify_cs

ACCLAMATION_ALLELUIA = 'aleluja'
ACCLAMATION_LENT = 'chvala'


def easter(year: int) -> date:
    """Gregorian Easter Sunday (anonymous Gregorian algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month, day = divmod(h + ell - 7 * m + 114, 31)
    return date(year, month, day + 1)


def first_advent_sunday(year: int) -> date:
    """First Sunday of Advent in the given civil year (between 27 Nov and 3 Dec)."""
    christmas = date(year, 12, 25)
    days_back = (christmas.weekday() - 6) % 7 or 7  # last Sunday strictly before Christmas
    return christmas - timedelta(days=days_back + 21)


def liturgical_year(day: date) -> int:
    """Civil year in which the liturgical year containing `day` ends."""
    return day.year + 1 if day >= first_advent_sunday(day.year) else day.year


def sunday_cycle(day: date) -> str:
    """Sunday lectionary cycle A/B/C."""
    return 'ABC'[(liturgical_year(day) - 1) % 3]


def ferial_cycle(day: date) -> int:
    """Weekday lectionary cycle for Ordinary Time: 1 (odd years) or 2 (even years)."""
    return 2 if liturgical_year(day) % 2 == 0 else 1


def _easter_offset(day: date) -> int:
    return (day - easter(day.year)).days


def is_sunday(day: date) -> bool:
    return day.weekday() == 6


def is_good_friday(day: date) -> bool:
    return _easter_offset(day) == -2


def is_holy_saturday(day: date) -> bool:
    return _easter_offset(day) == -1


def is_holy_thursday(day: date) -> bool:
    return _easter_offset(day) == -3


def is_easter_octave(day: date) -> bool:
    return 0 <= _easter_offset(day) <= 7


def is_christmas_octave(day: date) -> bool:
    return (day.month == 12 and day.day >= 25) or (day.month == 1 and day.day == 1)


def is_all_souls(day: date, rank_label: str, title: str) -> bool:
    """2 November is ranked as a solemnity by calapi but has neither Gloria nor the 'slavnost' label."""
    return (
        rank_label == RANK_SOLEMNITY
        and day.month == 11
        and day.day in (2, 3)
        and 'zemrel' in slugify_cs(title)
    )


def is_solemnity(day: date, rank_label: str, title: str) -> bool:
    if rank_label == RANK_SOLEMNITY:
        return not is_all_souls(day, rank_label, title)
    if rank_label == RANK_TRIDUUM:
        return _easter_offset(day) == 0  # Easter Sunday; Good Friday and Holy Saturday are not
    if rank_label == RANK_PRIMARY:
        offset = _easter_offset(day)
        # Primary days that are solemnities: Christmas, Epiphany, Ascension, Pentecost.
        # The rest (Sundays of Advent/Lent/Easter, Ash Wednesday, Holy Week, Easter octave) are not.
        return (day.month, day.day) in ((12, 25), (1, 6)) or offset in (39, 49)
    return False


@dataclass(frozen=True)
class MassNorms:
    gloria: bool | None
    credo: bool | None
    acclamation: str | None  # ACCLAMATION_ALLELUIA, ACCLAMATION_LENT or None
    note: str | None = None


NOTE_GOOD_FRIDAY = (
    'Mše se neslaví. Slaví se památka umučení Páně (bohoslužba slova, uctívání kříže, přijímání).'
)
NOTE_HOLY_SATURDAY = (
    'Během dne se mše neslaví. Velikonoční vigilie patří již k neděli Zmrtvýchvstání Páně.'
)
NOTE_HOLY_THURSDAY = 'Večer mše na památku Večeře Páně.'


def mass_norms(day: date, season: str, rank_label: str, title: str) -> MassNorms:
    """Norms for one mass option (one celebration on one day)."""
    if is_good_friday(day):
        return MassNorms(gloria=None, credo=None, acclamation=ACCLAMATION_LENT, note=NOTE_GOOD_FRIDAY)
    if is_holy_saturday(day):
        return MassNorms(gloria=None, credo=None, acclamation=None, note=NOTE_HOLY_SATURDAY)

    sunday = is_sunday(day)
    solemnity = is_solemnity(day, rank_label, title)
    acclamation = ACCLAMATION_LENT if season == 'lent' else ACCLAMATION_ALLELUIA

    if is_all_souls(day, rank_label, title):
        return MassNorms(gloria=False, credo=None if sunday else False, acclamation=acclamation)

    if is_holy_thursday(day):
        gloria = True
    elif is_easter_octave(day) or is_christmas_octave(day):
        gloria = True
    elif solemnity or rank_label == RANK_FEAST:
        gloria = True
    elif sunday:
        gloria = season not in ('advent', 'lent')
    else:
        gloria = False

    note = NOTE_HOLY_THURSDAY if is_holy_thursday(day) else None
    return MassNorms(gloria=gloria, credo=sunday or solemnity, acclamation=acclamation, note=note)


def rank_display(day: date, rank_label: str, title: str) -> str:
    """Human rank label for the UI ('' = show nothing)."""
    if rank_label == RANK_FERIA:
        return ''
    if rank_label == RANK_TRIDUUM:
        return RANK_TRIDUUM
    if rank_label == RANK_PRIMARY:
        if is_solemnity(day, rank_label, title):
            return RANK_SOLEMNITY
        return RANK_SUNDAY if is_sunday(day) else ''
    if is_all_souls(day, rank_label, title):
        return ''
    return rank_label


def rank_sort_key(rank_num: Decimal, position: int) -> tuple[Decimal, int]:
    """Lower rank_num = higher precedence (Table of Liturgical Days)."""
    return (rank_num, position)
