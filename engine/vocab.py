"""Engine vocabulary: mass parts, strengths, rule kinds, tiers. Pure module: must not import Django."""
from __future__ import annotations

from decimal import Decimal

# Mass parts in display order (design §3).
PARTS: tuple[tuple[str, str], ...] = (
    ('before_mass', 'před mší'),
    ('rite', 'při obřadu'),
    ('mass', 'mešní píseň'),
    ('entrance', 'ke vstupu'),
    ('procession', 'průvod'),
    ('asperges', 'kropení'),
    ('ashes', 'udílení popelce'),
    ('psalm', 'žalm'),
    ('sequence', 'sekvence'),
    ('gospel', 'před evangeliem'),
    ('offertory', 'k obětnímu průvodu'),
    ('veneration', 'uctívání kříže'),
    ('baptismal_water', 'kropení křestní vodou'),
    ('litany', 'litanie'),
    ('chrismation', 'při mazání křižmem'),
    ('laying_on_hands', 'při vkládání rukou'),
    ('communion', 'k přijímání'),
    ('thanksgiving', 'díkůvzdání po přijímání'),
    ('transfer', 'přenášení eucharistie'),
    ('adoration', 'adorace'),
    ('recessional', 'na závěr'),
    ('after_mass', 'po mši'),
)
PART_KEYS = tuple(key for key, _ in PARTS)
PART_LABELS = dict(PARTS)
PART_INDEX = {key: i for i, key in enumerate(PART_KEYS)}

# Parts the mass song normally covers (Kancionál prints dedicated verses for them).
COVERED_BY_MASS_SONG = ('entrance', 'gospel', 'offertory')
# Parts for which a missing recommendation is shown as a gap.
CORE_PARTS = ('mass', 'communion', 'recessional')

STRENGTHS: tuple[tuple[str, str], ...] = (
    ('prescribed', 'předepsáno'),
    ('recommended', 'doporučeno'),
    ('alternative', 'možno též'),
    ('avoid', 'nevhodné'),
)
STRENGTH_KEYS = tuple(key for key, _ in STRENGTHS)
STRENGTH_LABELS = dict(STRENGTHS)
STRENGTH_RANK = {'prescribed': 3, 'recommended': 2, 'alternative': 1, 'avoid': 0}

KINDS: tuple[tuple[str, str], ...] = (
    ('songs', 'písně'),
    ('neighbours', 'písně ze svátků okolních dnů'),
    ('note', 'poznámka'),
    ('silence', 'nic se nezpívá'),
)
KIND_KEYS = tuple(key for key, _ in KINDS)

DAY_KINDS: tuple[tuple[str, str], ...] = (
    ('', 'kterýkoli den'),
    ('sunday', 'neděle'),
    ('weekday', 'všední den'),
)
DAY_KIND_KEYS = tuple(key for key, _ in DAY_KINDS)

# min_rank filter: the occurrence's rank_num must be <= the threshold (Table of Liturgical Days).
MIN_RANKS: tuple[tuple[str, str, Decimal], ...] = (
    ('solemnity', 'slavnost a vyšší', Decimal('1.4')),
    ('feast', 'svátek, neděle a vyšší', Decimal('2.8')),
    ('memorial', 'památka a vyšší', Decimal('3.11')),
    ('optional_memorial', 'nezávazná památka a vyšší', Decimal('3.12')),
)
MIN_RANK_KEYS = ('', *(key for key, _, _ in MIN_RANKS))
MIN_RANK_THRESHOLD = {key: threshold for key, _, threshold in MIN_RANKS}

# Celebrations whose songs feed neighbour rules: "slavnosti, svátku či památky" (Direktář p. 27).
NEIGHBOUR_MAX_RANK = Decimal('3.11')
# Gap message when a celebration of at least this rank has no specific (▲/■) recommendation.
GAP_MAX_RANK = Decimal('3.11')

SPECIFICITY = {'occasion': 5, 'celebration': 5, 'category': 4, 'period': 3, 'season': 2, 'global': 1}

# Occasions (Direktář pp. 47-48): rules with an occasion never apply to calendar days; they feed /prilezitosti/.
OCCASIONS: tuple[tuple[str, str], ...] = (
    ('krest', 'Křest'),
    ('birmovani', 'Biřmování'),
    ('pomazani', 'Pomazání nemocných'),
    ('svatba', 'Svatba'),
    ('pohreb', 'Pohřeb'),
    ('bohosluzba_slova', 'Bohoslužba slova'),
)
OCCASION_KEYS = tuple(key for key, _ in OCCASIONS)
OCCASION_LABELS = dict(OCCASIONS)

TIER_CELEBRATION, TIER_CATEGORY, TIER_GENERAL = '▲', '■', '●'


def tier(specificity: int) -> str:
    if specificity >= SPECIFICITY['celebration']:
        return TIER_CELEBRATION
    if specificity >= SPECIFICITY['category']:
        return TIER_CATEGORY
    return TIER_GENERAL


WEEKDAY_ABBR = ('po', 'út', 'st', 'čt', 'pá', 'so', 'ne')
