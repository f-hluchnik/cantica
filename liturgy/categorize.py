"""First-guess celebration categories from titles. Pure module: must not import Django.

Only a starting point for human review (entries stay `categories_reviewed: false`). The ■ tier
depends on categories, so a wrong guess shows up as a wrong ■ recommendation, never silently.
"""
from __future__ import annotations

from collections.abc import Iterable

from liturgy.constants import CATEGORIES
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
# Women: a feminine descriptor, or a first name in -y/-ie without a masculine one ("Sv. Moniky", "Sv. Marty").
_FEMININE = ('panny', 'mucednice', 'mucednic', 'reholnice', 'ucitelky', 'patronky', 'vdovy', 'abatyse')
_MASCULINE = ('mucednika', 'mucedniku', 'biskupa', 'kneze', 'papeze', 'ucitele', 'opata', 'reholnika', 'reholniku',
              'mnicha', 'jahna', 'patrona', 'apostola', 'apostolu', 'evangelisty')
_MALE_NAMES_IN_Y = ('judy', 'kosmy', 'bedy', 'bonaventury', 'hroznaty', 'jachyma')


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
        and 'ducha' not in token_set  # "Seslání Ducha svatého"
        and (
            tokens[0] in ('sv', 'svatych', 'svate', 'bl')
            or 'sv' in tokens[:2]
            or bool(token_set & {'svateho', 'svatych'})
        )
    )
    if tokens[0] != 'sv' and 'panny-marie' in slug:
        add('virgin_mary')
    if token_set & set(_ANGEL):
        if 'virgin_mary' not in found:  # "Panny Marie Královny andělů" is a Marian feast
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
    plain = set(slug.replace('panny-marie', '').split('-'))  # "Snoubence Panny Marie" is not about a woman
    if 'panny' in plain:
        add('virgin')
    name = tokens[1] if tokens[0] in ('sv', 'bl') and len(tokens) > 1 else ''
    feminine_name = name.endswith(('y', 'ie')) and name not in _MALE_NAMES_IN_Y and not plain & set(_MASCULINE)
    if plain & set(_FEMININE) or feminine_name:
        add('woman')
    if token_set & set(_RELIGIOUS):
        add('religious')
    if any(all(t in token_set for t in names) for names in CZECH_PATRON_TOKENS):
        add('czech_patron')
    if not apostle:  # the Direktář treats apostles and evangelists separately (p. 8: 827)
        add('saint')
    return found



def review_listing(entries: Iterable[tuple[str, str, list[str], bool]]) -> str:
    """Markdown listing for reviewing categories: (key, name, categories, reviewed).

    Grouped by the exact combination of categories, so every celebration appears once and unusual
    combinations stand out; "bez kategorie" makes a missing category as visible as a wrong one.
    """
    labels = dict(CATEGORIES)
    groups: dict[tuple[str, ...], list[str]] = {}
    for key, name, categories, reviewed in sorted(entries, key=lambda e: slugify_cs(e[1])):
        groups.setdefault(tuple(categories), []).append(f'- [{"x" if reviewed else " "}] {name} (`{key}`)')
    out = ['# Kategorie slavení', '', '[x] = zkontrolováno (categories_reviewed: true)', '']
    for combo, lines in sorted(groups.items(), key=lambda g: (not g[0], -len(g[1]), g[0])):
        title = ' + '.join(labels.get(c, c) for c in combo) or 'bez kategorie'
        out += [f'## {title} ({len(lines)})', '', *lines, '']
    return '\n'.join(out)
