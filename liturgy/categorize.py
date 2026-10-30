"""First-guess celebration categories from titles. Pure module: must not import Django.

Only a starting point for human review (entries stay `categories_reviewed: false`). The ■ tier
depends on categories, so a wrong guess shows up as a wrong ■ recommendation, never silently.
"""
from __future__ import annotations

from liturgy.keys import slugify_cs

# Feasts of the Lord in the sense of the Direktář p. 8 ("701 ad."). Deliberately NOT the temporale
# solemnities of the strong seasons (Christmas, Epiphany, Easter, Ascension …): there the season's
# own songs apply, and a ■ category would outrank them.
LORD_KEYS = (
    'promeneni-pane',
    'povyseni-svateho-krize',
    'tela-a-krve-pane',
    'nejsvetejsiho-srdce-jezisova',
    'jezise-krista-krale',
    'jezise-krista-nejvyssiho-a-vecneho-kneze',
    'nejsvetejsiho-jmena-jezis',
    'uvedeni-pane-do-chramu',
)

# Czech patrons (Direktář p. 8: "českých patronů … příslušnou sloku písně 838").
CZECH_PATRON_TOKENS = (
    ('vaclava',), ('ludmily',), ('vojtecha',), ('prokopa',), ('nepomuckeho',), ('anezky', 'ceske'),
    ('zdislavy',), ('cyrila', 'metodeje'), ('sarkandra',), ('hofbauera',), ('hroznaty',), ('norberta',),
    ('vita',), ('neumanna',), ('gorazda',), ('ivana',), ('radima',), ('klementa', 'i'), ('hedviky',),
)

_MARTYR = ('mucednika', 'mucednice', 'mucedniku', 'mucednic', 'prvomucednika', 'prvomucedniku')
_APOSTLE = ('apostola', 'apostolu', 'evangelisty', 'evangelistu')
_PASTOR = ('biskupa', 'biskupu', 'papeze', 'papezu', 'kneze', 'knezi')
_DOCTOR = ('ucitele', 'ucitelky', 'ucitelu')
_RELIGIOUS = ('reholnika', 'reholnice', 'reholniku', 'mnicha', 'mnichu', 'poustevnika', 'opata', 'abatyse')
_ANGEL = ('andelu', 'archandelu')


def suggest_categories(title: str) -> list[str]:  # noqa: C901
    slug = slugify_cs(title)
    tokens = slug.split('-')
    token_set = set(tokens)
    found: list[str] = []

    def add(category: str) -> None:
        if category not in found:
            found.append(category)

    if any(slug.startswith(k) for k in LORD_KEYS):
        add('lord')
    if 'posveceni' in token_set:
        add('dedication')
    if any(t.startswith('zemrel') for t in tokens):
        add('dead')
    if slug.startswith('svate-rodiny'):
        return found  # Holy Family: a feast in the Christmas octave, not a saint's day
    is_saint_title = (
        'lord' not in found
        and 'katedraly' not in token_set
        and not token_set & {'tydne', 'oktavu'}  # "Čtvrtek Svatého týdne" is not a saint's day
        and (
            tokens[0] in ('sv', 'svatych', 'svate', 'bl')
            or 'sv' in tokens[:2]
            or bool(token_set & {'svateho', 'svatych'})
        )
    )
    if tokens[0] != 'sv' and 'panny-marie' in slug:
        add('virgin_mary')
    if token_set & set(_ANGEL):
        add('angel')
        return found
    if not is_saint_title:
        return found

    if token_set & set(_APOSTLE):
        add('apostle_evangelist')
        apostle = True
    else:
        apostle = False
    if token_set & set(_MARTYR) or tokens[0] == 'umuceni':
        add('martyr')
    if token_set & set(_PASTOR):
        add('pastor')
    if token_set & set(_DOCTOR):
        add('doctor')
    if 'panny' in token_set and 'panny-marie' not in slug:
        add('virgin')
    if token_set & set(_RELIGIOUS):
        add('religious')
    if any(all(t in token_set for t in names) for names in CZECH_PATRON_TOKENS):
        add('czech_patron')
    if not apostle:  # the Direktář treats apostles and evangelists separately (p. 8: 827)
        add('saint')
    return found
