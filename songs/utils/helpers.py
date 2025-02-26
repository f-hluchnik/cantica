from datetime import date, timedelta

from dateutil import easter


def get_easter_date(year: int) -> date:
    return easter.easter(year)


def get_pentecost_date(year: int) -> date:
    easter_date = get_easter_date(year)
    return easter_date + timedelta(days=49)


def get_ascension_date(year: int) -> date:
    easter_date = get_easter_date(year)
    return easter_date + timedelta(days=39)
