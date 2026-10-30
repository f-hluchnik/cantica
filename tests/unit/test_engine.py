"""Engine unit tests on a small synthetic snapshot."""
import unittest
from datetime import date, timedelta
from decimal import Decimal

from engine.model import DayCtx, GroupInfo, NeighbourCtx, OccurrenceCtx, RuleInfo, Snapshot, SongInfo
from engine.plan import build_plan
from engine.recommend import recommend
from engine.refs import RefError, Target, format_targets, parse_targets
from engine.resolve import matching_rules, resolve_mass
from liturgy.periods import Periods

PERIODS = Periods.loads("""
- {key: may, kind: fixed, from: 05-01, to: 05-31}
""")

SONGS = [
    SongInfo('523', 'Ty jsi, Pane', 'mass_general', mass_song=True, communion_verses='4', recessional_verses='*'),
    SongInfo('512', 'Bože, před tvou velebností', 'mass_general', mass_song=True),
    SongInfo('510A', 'Pokrop mě yzopem', 'mass_general', mass_song=False),
    SongInfo('712', 'Klaním se ti vroucně', 'jesus', communion_verses='*'),
    SongInfo('714', 'Ó pokrme pocestných', 'jesus'),
    SongInfo('805', 'Maria, Maria', 'mary_saints', mass_song=True),
    SongInfo('813A', 'Velebí má duše Hospodina', 'mary_saints'),
    SongInfo('813B', 'Velebí má duše s jásotem', 'mary_saints'),
    SongInfo('827', 'Vyvolil si apoštoly', 'mary_saints', mass_song=True),
    SongInfo('828', 'Bože, cos ráčil', 'mary_saints', mass_song=True),
    SongInfo('829', 'Ejhle, oltář', 'mary_saints', mass_song=True),
    SongInfo('838', 'Svatým bratřím chvály znějí', 'mary_saints'),
    SongInfo('910', 'Jeden Pán', 'occasional', recessional_verses='*'),
    SongInfo('930A', 'Hospodine, pomiluj ny', 'occasional', recessional_verses='*'),
]
GROUPS = [GroupInfo('mesni', 'mešní písně obecné', ('512', '523', '510A'))]

ORDINARY_RULES = [
    RuleInfo(1, ('mass',), targets=parse_targets('@mesni'), season='ordinary', page=25, position=10),
    RuleInfo(2, ('communion',), targets=parse_targets('#jesus'), season='ordinary', page=9, position=11),
    RuleInfo(3, ('recessional',), kind='neighbours', season='ordinary', page=27, position=12),
    RuleInfo(4, ('recessional',), targets=parse_targets('930'), season='ordinary', page=27, position=13),
]


def occ(title: str = 'Středa 3. týdne v mezidobí', key: str | None = None, rank: str = '3.13',
        label: str = 'ferie', categories: frozenset = frozenset()) -> OccurrenceCtx:
    return OccurrenceCtx(title, label, Decimal(rank), 'green', key, categories)


def ctx(day: date = date(2027, 1, 27), *occurrences: OccurrenceCtx, season: str = 'ordinary', week: int = 3,
        neighbours: tuple = (), cycle: str = 'B', diocese: str = 'czech') -> DayCtx:
    return DayCtx(day, diocese, season, week, cycle, 1, occurrences or (occ(),), neighbours)


def snap(*rules: RuleInfo) -> Snapshot:
    return Snapshot(SONGS, GROUPS, rules or ORDINARY_RULES, PERIODS, version=1)


def codes(result: object) -> list[str]:
    return [e.code for e in result.entries]


class RefsTests(unittest.TestCase):
    def test_parse(self) -> None:
        targets = parse_targets('828, 838/1+3, 691-695, @mesni_obecne, #advent, Z781, 813B, 838/2-4')
        self.assertEqual([t.kind for t in targets], ['song', 'song', 'range', 'group', 'section', 'song', 'song',
                                                     'song'])
        self.assertEqual(targets[1].verses, '1,3')
        self.assertEqual(targets[7].verses, '2,3,4')
        self.assertEqual(format_targets(targets), '828, 838/1+3, 691-695, @mesni_obecne, #advent, Z781, 813B, 838/2+3+4')
        self.assertEqual(parse_targets(''), ())

    def test_errors(self) -> None:
        for text in ('82', '838/x', '700-600', '#nowhere', '@Bad', '838/0', 'abc'):
            with self.subTest(text=text), self.assertRaises(RefError):
                parse_targets(text)

    def test_expand(self) -> None:
        s = snap()
        self.assertEqual(s.expand(Target('song', '813')), ['813A', '813B'])
        self.assertEqual(s.expand(Target('range', '827', '829')), ['827', '828', '829'])
        self.assertEqual(s.expand(Target('group', 'mesni')), ['512', '523', '510A'])
        self.assertEqual(s.expand(Target('section', 'jesus'), 'communion'), ['712'])  # verified verse only
        self.assertEqual(s.expand(Target('section', 'mass_general'), 'mass'), ['512', '523'])
        self.assertEqual(s.expand(Target('song', '999')), [])


class MatchingTests(unittest.TestCase):
    def test_filters(self) -> None:
        sunday = date(2027, 1, 24)
        rules = [
            RuleInfo('cel', ('mass',), celebration='x'),
            RuleInfo('cat', ('mass',), category='apostle_evangelist'),
            RuleInfo('season', ('mass',), season='ordinary'),
            RuleInfo('advent', ('mass',), season='advent'),
            RuleInfo('cycle', ('mass',), cycles=frozenset('C')),
            RuleInfo('sunday', ('mass',), day_kind='sunday'),
            RuleInfo('weekday', ('mass',), day_kind='weekday'),
            RuleInfo('rank', ('mass',), min_rank='memorial'),
            RuleInfo('olm', ('mass',), dioceses=frozenset({'olm'})),
            RuleInfo('may', ('mass',), period='may'),
        ]
        o = occ('X', 'x', '3.1', 'památka', frozenset({'apostle_evangelist'}))
        matched = {r.id for r in matching_rules(snap(*rules), ctx(sunday, o, cycle='B'), o)}
        self.assertEqual(matched, {'cel', 'cat', 'season', 'sunday', 'rank'})

    def test_specificity(self) -> None:
        self.assertEqual(RuleInfo(1, ('mass',), celebration='x', season='advent').specificity, 5)
        self.assertEqual(RuleInfo(1, ('mass',), category='martyr', season='easter').specificity, 4)
        self.assertEqual(RuleInfo(1, ('mass',)).specificity, 1)


class ResolutionTests(unittest.TestCase):
    def test_general_day(self) -> None:
        parts, _ = resolve_mass(snap(), ctx(), occ())
        by = {p.part: p for p in parts}
        self.assertEqual(codes(by['mass']), ['512', '523'])  # 510A has mass_song = False
        self.assertEqual(codes(by['communion']), ['712'])
        self.assertEqual(by['mass'].coverage, '●')
        self.assertEqual(by['mass'].items[0].kind, 'group')

    def test_avoid_gives_way_to_more_specific(self) -> None:
        rules = [
            RuleInfo('may', ('mass',), strength='avoid', targets=parse_targets('805'), period='may',
                     note='Mariánské písně po mši.'),
            RuleInfo('season', ('mass',), targets=parse_targets('805, 523'), season='easter'),
            RuleInfo('mary', ('mass',), targets=parse_targets('805'), category='virgin_mary'),
        ]
        day = date(2027, 5, 12)
        feria = occ('Středa', None, '3.13')
        parts, _ = resolve_mass(snap(*rules), ctx(day, feria, season='easter'), feria)
        self.assertEqual(codes(parts[0]), ['523'])  # 805 avoided in May
        self.assertIn('Mariánské písně po mši.', parts[0].notes)
        marian = occ('Panny Marie Fatimské', 'pm', '3.12', 'nezávazná památka', frozenset({'virgin_mary'}))
        parts, _ = resolve_mass(snap(*rules), ctx(day, marian, season='easter'), marian)
        self.assertEqual(codes(parts[0]), ['805', '523'])  # ■ rule outranks the period avoid
        self.assertEqual(parts[0].entries[0].tier, '■')

    def test_ordering_strength_then_specificity(self) -> None:
        rules = [
            RuleInfo('alt', ('mass',), strength='alternative', targets=parse_targets('828'), celebration='c'),
            RuleInfo('rec', ('mass',), targets=parse_targets('523'), season='ordinary'),
            RuleInfo('pres', ('mass',), strength='prescribed', targets=parse_targets('512'), season='ordinary'),
        ]
        o = occ('C', 'c', '3.1', 'památka')
        parts, _ = resolve_mass(snap(*rules), ctx(date(2027, 1, 27), o), o)
        self.assertEqual(codes(parts[0]), ['512', '523', '828'])

    def test_merge_keeps_best_and_collects_reasons(self) -> None:
        rules = [
            RuleInfo('general', ('mass',), targets=parse_targets('@mesni'), season='ordinary', page=25),
            RuleInfo('specific', ('mass',), targets=parse_targets('523'), celebration='c', page=38),
        ]
        o = occ('C', 'c', '3.1', 'památka')
        parts, _ = resolve_mass(snap(*rules), ctx(date(2027, 1, 27), o), o)
        first = parts[0].entries[0]
        self.assertEqual((first.code, first.tier), ('523', '▲'))
        self.assertEqual([r.source for r in first.reasons], ['Direktář s. 38', 'Direktář s. 25'])
        self.assertEqual(codes(parts[0]), ['523', '512'])

    def test_silence(self) -> None:
        rules = [
            RuleInfo('season', ('entrance', 'mass'), targets=parse_targets('523'), season='lent'),
            RuleInfo('quiet', ('entrance',), kind='silence', celebration='gf', note='Při vstupu se nic nezpívá.'),
        ]
        o = occ('Velký pátek', 'gf', '1.1', 'Velikonoční triduum')
        parts, _ = resolve_mass(snap(*rules), ctx(date(2027, 3, 26), o, season='lent'), o)
        by = {p.part: p for p in parts}
        self.assertTrue(by['entrance'].silenced)
        self.assertEqual(codes(by['entrance']), [])
        self.assertEqual(codes(by['mass']), ['523'])

    def test_neighbours(self) -> None:
        rules = [*ORDINARY_RULES, RuleInfo('cm', ('mass',), targets=parse_targets('828, 829'), celebration='cm')]
        day = date(2027, 7, 8)
        neighbours = (
            NeighbourCtx(date(2027, 7, 5), 'Sv. Cyrila a Metoděje', 'cm', Decimal('1.4')),
            NeighbourCtx(date(2027, 7, 20), 'Daleko', 'cm', Decimal('1.4')),  # outside the window
        )
        parts, _ = resolve_mass(snap(*rules), ctx(day, neighbours=neighbours), occ())
        recessional = {p.part: p for p in parts}['recessional']
        self.assertEqual(codes(recessional), ['828', '829', '930A'])
        self.assertIn('ze svátku Sv. Cyrila a Metoděje (po 5. 7.)', recessional.entries[0].reasons[0].text())


class PlanTests(unittest.TestCase):
    def _plan(self, rules: list, o: OccurrenceCtx | None = None, day: date = date(2027, 1, 27), **kw: object) -> list:
        o = o or occ()
        c = ctx(day, o, **kw)
        s = snap(*rules)
        parts, _ = resolve_mass(s, c, o)
        return build_plan({p.part: p for p in parts}, s, c, o)

    def test_prescribed_mass_songs_all_used(self) -> None:
        rules = [RuleInfo('cm', ('mass',), strength='prescribed', targets=parse_targets('828, 829'), celebration='cm')]
        plan = self._plan(rules, occ('CM', 'cm', '1.4', 'slavnost'))
        mass = plan[0]
        self.assertEqual([s.code for s in mass.songs], ['828', '829'])
        self.assertEqual(mass.covers, ('entrance', 'gospel', 'offertory'))

    def test_specific_entrance_overrides_mass_song(self) -> None:
        rules = [*ORDINARY_RULES, RuleInfo('p', ('entrance',), targets=parse_targets('838/5'), celebration='prokop')]
        plan = self._plan(rules, occ('Sv. Prokopa', 'prokop', '3.1', 'památka'))
        entrance = next(e for e in plan if e.part == 'entrance')
        self.assertEqual((entrance.songs[0].code, entrance.songs[0].verses_label, entrance.tier), ('838', '5. sl.', '▲'))

    def test_unverified_mass_song_gets_separate_communion(self) -> None:
        rules = [RuleInfo('m', ('mass',), targets=parse_targets('512'), season='ordinary'),
                 RuleInfo('c', ('communion',), targets=parse_targets('714'), season='ordinary')]
        plan = self._plan(rules)
        communion = next(e for e in plan if e.part == 'communion')
        self.assertEqual((communion.kind, communion.songs[0].code), ('songs', '714'))

    def test_mass_verse_when_no_other_communion(self) -> None:
        rules = [RuleInfo('m', ('mass',), targets=parse_targets('523'), season='ordinary')]
        plan = self._plan(rules)
        communion = next(e for e in plan if e.part == 'communion')
        self.assertEqual((communion.kind, communion.songs[0].code, communion.songs[0].verses), ('mass_verse', '523', '4'))
        recessional = next(e for e in plan if e.part == 'recessional')
        self.assertEqual((recessional.kind, recessional.songs[0].verses), ('mass_verse', ''))  # '*' shows no hint

    def test_gaps_are_visible(self) -> None:
        plan = self._plan([RuleInfo('m', ('mass',), targets=parse_targets('512'), season='ordinary')])
        self.assertEqual([(e.part, e.kind) for e in plan], [('mass', 'songs'), ('communion', 'gap'),
                                                             ('recessional', 'gap')])

    def test_recessional_prefers_neighbours_over_general(self) -> None:
        rules = [*ORDINARY_RULES, RuleInfo('cm', ('mass',), targets=parse_targets('828'), celebration='cm')]
        nb = (NeighbourCtx(date(2027, 7, 5), 'Sv. Cyrila a Metoděje', 'cm', Decimal('1.4')),)
        plan = self._plan(rules, day=date(2027, 7, 8), neighbours=nb)
        recessional = next(e for e in plan if e.part == 'recessional')
        self.assertEqual(recessional.songs[0].code, '828')
        self.assertIn('ze svátku', recessional.reasons[0].text())

    def test_no_song_twice(self) -> None:
        rules = [RuleInfo('m', ('mass', 'recessional'), targets=parse_targets('523, 910'), season='ordinary')]
        plan = self._plan(rules)
        used = [s.code for e in plan if e.kind == 'songs' for s in e.songs]
        self.assertEqual(len(used), len(set(used)))

    def test_deterministic_and_varies_by_week(self) -> None:
        rules = [RuleInfo('m', ('mass',), targets=parse_targets('512, 523, 805, 827, 828, 829'), season='ordinary')]
        picks = set()
        for week in range(12):
            day = date(2027, 1, 27) + timedelta(weeks=week)
            first = self._plan(rules, day=day, week=3 + week)[0].songs[0].code
            again = self._plan(rules, day=day, week=3 + week)[0].songs[0].code
            self.assertEqual(first, again)
            picks.add(first)
        self.assertGreater(len(picks), 1)


class RecommendTests(unittest.TestCase):
    def test_skip_last_weeks_mass_song_and_gap_flag(self) -> None:
        rules = [RuleInfo('m', ('mass',), targets=parse_targets('512, 523'), season='ordinary')]
        s = snap(*rules)
        memorial = occ('Sv. X', 'x', '3.1', 'památka')
        previous = ctx(date(2027, 1, 20), memorial)
        current = DayCtx(date(2027, 1, 27), 'czech', 'ordinary', 3, 'B', 1, (memorial,), (), previous)
        last = recommend(previous, s).masses[0].plan[0].songs[0].code
        now = recommend(current, s).masses[0].plan[0].songs[0].code
        self.assertNotEqual(last, now)
        result = recommend(current, s).masses[0]
        self.assertTrue(result.gap)  # memorial without ▲/■ recommendations
        self.assertEqual(result.summary[0].kind, 'song')

    def test_commemorations_are_not_masses(self) -> None:
        c = ctx(date(2027, 12, 21), occ('21. prosince', None, '2.9'), occ('Sv. Petra Kanisia', 'pk', '4.0', 'připomínka'),
                season='advent', week=4)
        result = recommend(c, snap())
        self.assertEqual([m.title for m in result.masses], ['21. prosince'])
        self.assertEqual(result.commemorations, ['Sv. Petra Kanisia'])

    def test_masses_ordered_by_rank(self) -> None:
        c = ctx(date(2027, 1, 27), occ('Feria', None, '3.13'), occ('Sv. Y', 'y', '3.12', 'nezávazná památka'))
        self.assertEqual([m.title for m in recommend(c, snap()).masses], ['Sv. Y', 'Feria'])


if __name__ == '__main__':
    unittest.main()
