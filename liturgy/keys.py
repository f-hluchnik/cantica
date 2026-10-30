"""Slugs and similarity for celebration titles. Pure module: must not import Django."""
from __future__ import annotations

import re
import unicodedata

MAX_KEY_LENGTH = 100

_NON_ALNUM = re.compile(r'[^a-z0-9]+')
# Tokens that carry no identity when comparing two titles.
_STOP_TOKENS = frozenset({'sv', 'svate', 'svateho', 'svatych', 'svatou', 'bl', 'a', 'v', 'z', 'ze', 'de'})


def slugify_cs(text: str) -> str:
    """ASCII slug of a Czech title: lowercase, no diacritics, words joined by '-'.

    Case, punctuation and diacritics are ignored, so 'sv. Hilaria' and 'Sv. Hilaria'
    give the same slug.
    """
    decomposed = unicodedata.normalize('NFKD', text)
    ascii_only = ''.join(ch for ch in decomposed if not unicodedata.combining(ch))
    return _NON_ALNUM.sub('-', ascii_only.lower()).strip('-')


def key_from_title(title: str) -> str:
    """Celebration key proposed for a new title (cut at a word boundary if too long)."""
    slug = slugify_cs(title)
    if len(slug) <= MAX_KEY_LENGTH:
        return slug
    cut = slug[:MAX_KEY_LENGTH]
    return cut.rsplit('-', 1)[0] if '-' in cut else cut


def title_similarity(a: str, b: str) -> float:
    """Jaccard similarity of significant tokens (0..1). Used only for hints, never for decisions."""
    tokens_a = set(slugify_cs(a).split('-')) - _STOP_TOKENS
    tokens_b = set(slugify_cs(b).split('-')) - _STOP_TOKENS
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
