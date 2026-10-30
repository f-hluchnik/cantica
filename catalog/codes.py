"""Kancionál song codes, sections and verse specifications. Pure module: must not import Django.

Codes follow kancional.cz: '523', '101A' (letter = variant), 'Z781' (Z = diocesan appendix).
A song's *number* is its code without the variant letter: '101A' -> '101', 'Z781' -> 'Z781'.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

CODE_RE = re.compile(r'^Z?\d{3}[A-Z]?$')
_VARIANT_RE = re.compile(r'^(Z?\d{3})([A-Z]?)$')

# Section keys in Kancionál order, with the headings used on kancional.cz/ciselny-seznam.
SECTIONS: tuple[tuple[str, str], ...] = (
    ('prayers', 'Hlavní společné modlitby'),
    ('personal_prayer', 'Osobní modlitba'),
    ('devotions', 'K pobožnostem'),
    ('hours', 'Denní modlitba církve'),
    ('advent', 'Adventní písně'),
    ('christmas', 'Vánoční písně'),
    ('lent', 'Postní písně'),
    ('easter', 'Velikonoční písně'),
    ('ordinaries', 'Zpěvy ke mši a ordinária'),
    ('mass_general', 'Obecné mešní písně'),
    ('psalm_responses', 'Odpovědi k žalmům'),
    ('jesus', 'Písně k Pánu Ježíši'),
    ('mary_saints', 'Písně o Panně Marii, andělech a svatých'),
    ('occasional', 'Písně příležitostné'),
)
SECTION_KEYS = frozenset(key for key, _ in SECTIONS)
SECTION_LABELS = dict(SECTIONS)

# Verse specification for communion_verses / recessional_verses (see design §6.1):
#   None   not verified (never shown to users; the plan stays conservative)
#   '-'    the song has no suitable verse
#   '*'    yes, the verse dedicated in Kancionál
#   '4,5'  these specific verses (shown to users as a hint)
VERSES_NONE = '-'
VERSES_DEDICATED = '*'
VERSES_RE = re.compile(r'^(\*|-|[1-9]\d*(,[1-9]\d*)*)$')


def is_valid_code(code: str) -> bool:
    return bool(CODE_RE.match(code))


def number_of(code: str) -> str:
    match = _VARIANT_RE.match(code)
    if not match:
        raise ValueError(f'invalid song code {code!r}')
    return match.group(1)


def code_sort_key(code: str) -> tuple[int, int, str]:
    """Kancionál order: by number, the Z appendix song right after the plain one, then variants."""
    match = _VARIANT_RE.match(code)
    if not match:
        return (10_000, 0, code)
    number = match.group(1)
    return (int(number.lstrip('Z')), 1 if number.startswith('Z') else 0, match.group(2))


def is_valid_verses(spec: str | None) -> bool:
    return spec is None or bool(VERSES_RE.match(spec))


def verse_numbers(spec: str | None) -> tuple[int, ...]:
    """Specific verse numbers, or () for None / '-' / '*'."""
    if spec is None or spec in (VERSES_NONE, VERSES_DEDICATED):
        return ()
    if not VERSES_RE.match(spec):
        raise ValueError(f'invalid verse specification {spec!r}')
    return tuple(int(v) for v in spec.split(','))


def has_verse(spec: str | None) -> bool:
    """True only when verified: '*' or specific verses. None (unknown) and '-' are False."""
    return spec == VERSES_DEDICATED or bool(verse_numbers(spec))


def expand(reference: str, codes: Iterable[str]) -> list[str]:
    """Resolve a rule's song reference against the catalog.

    An exact code with a variant letter ('813B', '101A') means only that song. Otherwise the
    reference is a number and matches all its variants: '813' -> ['813A', '813B'], '523' -> ['523'].
    The Z appendix is never implied: '781' does not match 'Z781'.
    """
    codes = list(codes)
    if reference in codes and _VARIANT_RE.match(reference).group(2):
        return [reference]
    return sorted((c for c in codes if number_of(c) == reference), key=code_sort_key)
