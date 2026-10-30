"""Domain constants shared by pure code, Django models and migrations.

Pure module: must not import Django.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DioceseDef:
    code: str
    name: str
    calapi_calendar: str


# Order = order in the diocese selector.
DIOCESES: tuple[DioceseDef, ...] = (
    DioceseDef('czech', 'Česká republika (obecný kalendář)', 'czech'),
    DioceseDef('cechy', 'Čechy (obecně)', 'czech-cechy'),
    DioceseDef('morava', 'Morava (obecně)', 'czech-morava'),
    DioceseDef('pha', 'Arcidiecéze pražská', 'czech-pha'),
    DioceseDef('ltm', 'Diecéze litoměřická', 'czech-ltm'),
    DioceseDef('hk', 'Diecéze královéhradecká', 'czech-hk'),
    DioceseDef('cb', 'Diecéze českobudějovická', 'czech-cb'),
    DioceseDef('plz', 'Diecéze plzeňská', 'czech-plz'),
    DioceseDef('olm', 'Arcidiecéze olomoucká', 'czech-olm'),
    DioceseDef('brn', 'Diecéze brněnská', 'czech-brn'),
    DioceseDef('oo', 'Diecéze ostravsko-opavská', 'czech-oo'),
)
DEFAULT_DIOCESE = 'czech'
CALAPI_CALENDARS: tuple[str, ...] = tuple(d.calapi_calendar for d in DIOCESES)

# Celebration categories (drive the ■ tier once rules exist).
CATEGORIES: tuple[tuple[str, str], ...] = (
    ('lord', 'Pán Ježíš'),
    ('virgin_mary', 'Panna Maria'),
    ('apostle_evangelist', 'apoštolové a evangelisté'),
    ('martyr', 'mučedníci'),
    ('pastor', 'duchovní pastýři'),
    ('doctor', 'učitelé církve'),
    ('virgin', 'panny'),
    ('religious', 'řeholníci a řeholnice'),
    ('saint', 'svatí a světice (obecně)'),
    ('czech_patron', 'čeští patroni'),
    ('angel', 'andělé'),
    ('dedication', 'posvěcení chrámu'),
    ('dead', 'za zemřelé'),
)
CATEGORY_KEYS = frozenset(key for key, _ in CATEGORIES)

SEASONS: tuple[tuple[str, str], ...] = (
    ('advent', 'doba adventní'),
    ('christmas', 'doba vánoční'),
    ('lent', 'doba postní'),
    ('easter', 'doba velikonoční'),
    ('ordinary', 'liturgické mezidobí'),
)
SEASON_KEYS = frozenset(key for key, _ in SEASONS)
SEASON_LABELS = dict(SEASONS)

# Rank labels exactly as calapi (cs) returns them.
RANK_TRIDUUM = 'Velikonoční triduum'
RANK_PRIMARY = 'Primární liturgické dny'
RANK_SOLEMNITY = 'slavnost'
RANK_FEAST = 'svátek'
RANK_SUNDAY = 'neděle'
RANK_FERIA = 'ferie'
RANK_MEMORIAL = 'památka'
RANK_OPTIONAL_MEMORIAL = 'nezávazná památka'
RANK_COMMEMORATION = 'připomínka'
RANK_LABELS = frozenset({
    RANK_TRIDUUM,
    RANK_PRIMARY,
    RANK_SOLEMNITY,
    RANK_FEAST,
    RANK_SUNDAY,
    RANK_FERIA,
    RANK_MEMORIAL,
    RANK_OPTIONAL_MEMORIAL,
    RANK_COMMEMORATION,
})

COLOURS: dict[str, str] = {
    'white': 'bílá',
    'red': 'červená',
    'green': 'zelená',
    'violet': 'fialová',
    'rose': 'růžová',
    'black': 'černá',
}
