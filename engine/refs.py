"""Song references in rules: a compact text syntax. Pure module: must not import Django.

Items are separated by commas:
    523          a song number (all its letter variants: 813 -> 813A, 813B; never the Z appendix)
    813B, Z781   an exact code
    838/5        a song with verses: '838/5', '838/1+3', '838/2-4'
    691-695      a range of numbers (plain numbers only)
    @mesni_obecne  a song group
    #advent      a Kancionál section; filtered per part (mass -> mešní píseň, communion/recessional ->
                 songs with a verified verse for that part)
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from catalog.codes import CODE_RE, SECTION_KEYS, code_sort_key
from catalog.codes import expand as expand_reference

_GROUP_RE = re.compile(r'^@([a-z0-9]+(?:_[a-z0-9]+)*)$')
_SECTION_RE = re.compile(r'^#([a-z_]+)$')
_RANGE_RE = re.compile(r'^(\d{3})-(\d{3})$')
_SONG_RE = re.compile(r'^(Z?\d{3}[A-Z]?)(?:/([0-9+\-]+))?$')
_VERSE_PART_RE = re.compile(r'^(\d+)(?:-(\d+))?$')


class RefError(ValueError):
    pass


@dataclass(frozen=True)
class Target:
    kind: str  # 'song' | 'range' | 'group' | 'section'
    ref: str
    ref_end: str = ''  # range end
    verses: str = ''  # normalized '1,3' ('' = whole song)

    def __str__(self) -> str:
        if self.kind == 'group':
            return f'@{self.ref}'
        if self.kind == 'section':
            return f'#{self.ref}'
        if self.kind == 'range':
            return f'{self.ref}-{self.ref_end}'
        if self.verses:
            return f'{self.ref}/' + '+'.join(self.verses.split(','))
        return self.ref


def _verses(spec: str, item: str) -> str:
    numbers: list[int] = []
    for part in spec.split('+'):
        match = _VERSE_PART_RE.match(part)
        if not match:
            raise RefError(f'{item!r}: invalid verses {spec!r}')
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if start < 1 or end < start:
            raise RefError(f'{item!r}: invalid verses {spec!r}')
        numbers.extend(range(start, end + 1))
    return ','.join(str(n) for n in sorted(set(numbers)))


def parse_targets(text: str) -> tuple[Target, ...]:
    targets: list[Target] = []
    for raw in text.split(','):
        item = raw.strip()
        if not item:
            continue
        if match := _GROUP_RE.match(item):
            targets.append(Target('group', match.group(1)))
        elif match := _SECTION_RE.match(item):
            if match.group(1) not in SECTION_KEYS:
                raise RefError(f'{item!r}: unknown section')
            targets.append(Target('section', match.group(1)))
        elif match := _RANGE_RE.match(item):
            if int(match.group(1)) >= int(match.group(2)):
                raise RefError(f'{item!r}: range must go up')
            targets.append(Target('range', match.group(1), match.group(2)))
        elif match := _SONG_RE.match(item):
            if not CODE_RE.match(match.group(1)):
                raise RefError(f'{item!r}: invalid song code')
            verses = _verses(match.group(2), item) if match.group(2) else ''
            targets.append(Target('song', match.group(1), verses=verses))
        else:
            raise RefError(f'{item!r}: not a song, range, @group or #section')
    return tuple(targets)


def format_targets(targets: Iterable[Target]) -> str:
    return ', '.join(str(t) for t in targets)


def expand_target(
    target: Target,
    codes: Iterable[str],
    groups: Mapping[str, Iterable[str]],
    sections: Mapping[str, Iterable[str]],
) -> list[str]:
    """Codes a target refers to (no per-part filtering). Unknown references give []."""
    if target.kind == 'group':
        return list(groups.get(target.ref, ()))
    if target.kind == 'section':
        return list(sections.get(target.ref, ()))
    codes = list(codes)
    if target.kind == 'range':
        result: list[str] = []
        for number in range(int(target.ref), int(target.ref_end) + 1):
            result.extend(expand_reference(f'{number:03d}', codes))
        return result
    return expand_reference(target.ref, codes)


def unknown_references(
    targets: Iterable[Target],
    codes: Iterable[str],
    groups: Mapping[str, Iterable[str]],
) -> list[str]:
    """Targets that resolve to nothing (for validation and lint)."""
    codes = sorted(codes, key=code_sort_key)
    problems = []
    for target in targets:
        if target.kind == 'group' and target.ref not in groups:
            problems.append(f'unknown group {target}')
        elif target.kind in ('song', 'range') and not expand_target(target, codes, groups, {}):
            problems.append(f'unknown song {target}')
    return problems
