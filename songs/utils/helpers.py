from datetime import date, timedelta
from enum import Enum

from dateutil import easter

from songs.utils.liturgical_season import LiturgicalSeasonEnum


def get_easter_date(year: int) -> date:
    return easter.easter(year)


def get_pentecost_date(year: int) -> date:
    easter_date = get_easter_date(year)
    return easter_date + timedelta(days=49)


def get_ascension_date(year: int) -> date:
    easter_date = get_easter_date(year)
    return easter_date + timedelta(days=39)


def season_match(season_to_check: str, current_season: str) -> bool:
    """ Check if liturgical season matches the current one."""
    return season_to_check in {current_season, 'saints', 'jesus christ', 'virgin mary'}


def is_late_advent(date_to_check: date) -> bool:
    late_advent_start = (12, 17)
    late_advent_end = (12, 24)
    date_to_check_yearless = (date_to_check.month, date_to_check.day)
    if late_advent_start <= date_to_check_yearless <= late_advent_end:
        return True
    return False


def is_christmas_octave(date_to_check: date) -> bool:
    christmas_octave_start = (12, 25)
    christmas_octave_end = (12, 31)
    date_to_check_yearless = (date_to_check.month, date_to_check.day)
    if christmas_octave_start <= date_to_check_yearless <= christmas_octave_end:
        return True
    return False


def is_week_of_prayer_for_christian_unity(date_to_check: date) -> bool:
    week_start = (1, 18)
    week_end = (1, 25)
    date_to_check_yearless = (date_to_check.month, date_to_check.day)
    if week_start <= date_to_check_yearless <= week_end:
        return True
    return False


def is_late_lent(date_to_check: date) -> bool:
    easter_date = get_easter_date(date_to_check.year)
    days_before_easter = (easter_date - date_to_check).days
    if 0 < days_before_easter <= 14:
        return True
    return False


def is_good_friday(date_to_check: date) -> bool:
    easter_date = get_easter_date(date_to_check.year)
    return date_to_check == (easter_date - timedelta(days=2))


def is_easter_triduum(date_to_check: date) -> bool:
    easter_date = get_easter_date(date_to_check.year)
    days_before_easter = (easter_date - date_to_check).days
    if 1 <= days_before_easter <= 3:
        return True
    return False


def is_easter_octave(date_to_check: date) -> bool:
    easter_date = get_easter_date(date_to_check.year)
    days_after_easter = (date_to_check - easter_date).days
    if 0 <= days_after_easter <= 7:
        return True
    return False


def is_pentecost_novena(date_to_check: date) -> bool:
    pentecost_date = get_pentecost_date(date_to_check.year)
    days_until_pentecost = (pentecost_date - date_to_check).days
    if 0 < days_until_pentecost <= 9:
        return True
    return False


class SongSection(Enum):
    ADVENT = '100'
    CHRISTMAS = '200'
    LENT = '300'
    EASTER = '400'
    ORDINARY = '500'
    JESUS_CHRIST = '700'
    VIRGIN_MARY = '800'
    SAINTS = '800'
    OCCASIONAL = '900'


def get_song_section_for_liturgical_season(liturgical_season: LiturgicalSeasonEnum) -> str:
    """
    Map the given liturgical season to its corresponding song section.
    """
    mapping = {
        LiturgicalSeasonEnum.ADVENT: SongSection.ADVENT.value,
        LiturgicalSeasonEnum.CHRISTMAS: SongSection.CHRISTMAS.value,
        LiturgicalSeasonEnum.LENT: SongSection.LENT.value,
        LiturgicalSeasonEnum.EASTER: SongSection.EASTER.value,
        LiturgicalSeasonEnum.ORDINARY: SongSection.ORDINARY.value,
        LiturgicalSeasonEnum.JESUS_CHRIST: SongSection.JESUS_CHRIST.value,
        LiturgicalSeasonEnum.VIRGIN_MARY: SongSection.VIRGIN_MARY.value,
        LiturgicalSeasonEnum.SAINTS: SongSection.SAINTS.value,
        LiturgicalSeasonEnum.OCCASIONAL: SongSection.OCCASIONAL.value,
    }

    return mapping.get(liturgical_season, '')
