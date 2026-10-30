"""Book assertions: the transcribed rules + engine on the real calendar (Direktář pp. 6–28).

They target behaviour that can go wrong in the engine or in the rule scopes (dates, periods,
cycles, avoid/silence, neighbours, the plan). They do not prove the transcription is faithful;
that is checked by reading the rules next to the book. Page numbers refer to the Direktář.
"""
import unittest
from datetime import date, timedelta

from engine.recommend import MassResult
from tests.book import harness


def mass(day: date, diocese: str = 'czech', title: str | None = None) -> MassResult:
    masses = harness.day(day, diocese).masses
    if title is None:
        return masses[0]
    return next(m for m in masses if title in m.title)


def candidates(m: MassResult, part: str) -> list[str]:
    result = next((p for p in m.parts if p.part == part), None)
    return [e.code for e in result.entries] if result else []


def plan(m: MassResult, part: str) -> tuple[str, list[str]]:
    entry = next((e for e in m.plan if e.part == part), None)
    return (entry.kind, [s.code for s in entry.songs]) if entry else ('', [])


def tier_of(m: MassResult, part: str) -> str | None:
    return next((p.coverage for p in m.parts if p.part == part), None)


class AdventTests(unittest.TestCase):
    def test_first_sunday(self) -> None:  # p. 17, 18
        m = mass(harness.date_of('1-nedele-adventni', 2026))
        self.assertEqual(candidates(m, 'mass')[:2], ['129', '126'])
        self.assertIn(plan(m, 'mass')[1][0], ('129', '126'))
        self.assertEqual(plan(m, 'before_mass')[1], ['128'])
        self.assertFalse(any(c.startswith('8') or c.startswith('9') for c in candidates(m, 'mass')))

    def test_early_weekday(self) -> None:  # p. 17, 18
        m = mass(date(2026, 12, 1), title='Úterý')  # the feria, not the optional memorial
        self.assertEqual(candidates(m, 'mass')[:4], ['121', '123', '126', '129'])
        self.assertEqual(plan(m, 'before_mass')[1], ['101A'])
        self.assertIn('127', candidates(m, 'communion'))

    def test_late_weekday_rorate_parts(self) -> None:  # p. 17
        m = mass(date(2026, 12, 18))
        self.assertEqual(candidates(m, 'entrance'), ['102', '110'])
        self.assertIn('106', candidates(m, 'communion'))
        self.assertIn('130', candidates(m, 'mass'))
        # one song per part, not a mass song plus a song for every part
        self.assertEqual(plan(m, 'mass'), ('', []))
        for part in ('entrance', 'gospel', 'offertory', 'communion', 'recessional'):
            self.assertEqual(plan(m, part)[0], 'songs', part)

    def test_marian_solemnity_beats_advent_avoid(self) -> None:  # p. 8 (■) vs author's Advent rule (●)
        m = mass(date(2026, 12, 8))
        self.assertEqual(tier_of(m, 'mass'), '■')
        self.assertIn('805', candidates(m, 'mass'))

    def test_no_occasional_songs_on_advent_weekday(self) -> None:  # author's rule
        m = mass(date(2026, 12, 2))
        self.assertFalse(any(c.startswith('9') for c in candidates(m, 'mass') + candidates(m, 'communion')))


class ChristmasTests(unittest.TestCase):
    def test_octave_feasts_use_christmas_songs(self) -> None:  # p. 19
        for d in (date(2026, 12, 26), date(2026, 12, 27), date(2026, 12, 28), date(2027, 1, 1)):
            m = mass(d)
            with self.subTest(day=d):
                self.assertTrue(candidates(m, 'mass'))
                self.assertTrue(all(c.lstrip('Z').startswith('2') for c in candidates(m, 'mass')), candidates(m, 'mass'))

    def test_new_year_te_deum(self) -> None:  # p. 19
        self.assertIn('932A', candidates(mass(date(2026, 12, 31)), 'recessional'))

    def test_epiphany(self) -> None:  # p. 19
        m = mass(date(2027, 1, 6))
        self.assertEqual(plan(m, 'mass')[1], ['202'])
        self.assertIn(plan(m, 'communion')[1][0], ('213', '219'))
        self.assertEqual(plan(m, 'psalm')[1], ['613'])

    def test_neighbour_recessional_after_epiphany(self) -> None:  # p. 10, 27
        m = mass(date(2027, 1, 8))
        kind, songs = plan(m, 'recessional')
        self.assertEqual(songs, ['202'])
        entry = next(e for e in m.plan if e.part == 'recessional')
        self.assertIn('ze svátku Zjevení Páně', entry.reasons[0].text())


class LentTests(unittest.TestCase):
    def test_ash_wednesday(self) -> None:  # p. 20
        m = mass(harness.date_of('popelecni-streda', 2027))
        self.assertIn(plan(m, 'mass')[1][0], ('322', '309'))
        self.assertIn(plan(m, 'ashes')[1][0], ('320', '319', '312'))
        self.assertIn('696', candidates(m, 'gospel'))
        self.assertNotIn('691', candidates(m, 'gospel'))

    def test_penitential_songs_first(self) -> None:  # p. 19–20
        m = mass(date(2027, 3, 3))
        self.assertEqual(candidates(m, 'mass')[:6], ['322', '321', '320', '319', '312', '309'])
        self.assertEqual(m.parts[0].entries[-1].strength, 'alternative')

    def test_first_sunday(self) -> None:  # p. 20
        m = mass(harness.date_of('1-nedele-postni', 2027))
        self.assertEqual(plan(m, 'mass')[1], ['307'])
        self.assertIn('068A', candidates(m, 'entrance'))

    def test_palm_sunday_and_holy_week(self) -> None:  # p. 21
        palm = mass(date(2027, 3, 21))
        self.assertEqual(plan(palm, 'procession')[1], ['318A'])
        self.assertIn(plan(palm, 'mass')[1][0], ('303', '305', '308'))
        self.assertEqual(plan(palm, 'after_mass')[1], ['315'])
        monday = mass(date(2027, 3, 22))
        self.assertEqual(candidates(monday, 'mass')[:4], ['303', '305', '306', '308'])

    def test_holy_thursday(self) -> None:  # p. 21–22
        m = mass(date(2027, 3, 25))
        self.assertEqual(plan(m, 'offertory'), ('songs', ['681']))
        self.assertEqual(plan(m, 'transfer')[1], ['704A'])
        self.assertIn(plan(m, 'mass')[1][0], ('710', '717A', '717B', '717C'))
        self.assertTrue(any('preludium' in n for n in m.notes))
        self.assertNotIn('401', candidates(m, 'recessional'))  # no Easter Vigil songs via neighbours (p. 27)
        self.assertEqual(plan(m, 'recessional')[0], 'silence')  # the Mass ends with the transfer (author rule)
        self.assertFalse(any(c in ('840', '841') for c in candidates(m, 'mass')))  # not a saint's day
        mass_entry = next(e for e in m.plan if e.part == 'mass')
        self.assertNotIn('offertory', mass_entry.covers)  # 681 has its own line

    def test_good_friday(self) -> None:  # p. 22
        m = mass(date(2027, 3, 26))
        self.assertEqual(plan(m, 'mass')[0], 'silence')
        self.assertEqual(plan(m, 'entrance')[0], 'silence')
        self.assertEqual(plan(m, 'recessional')[0], 'silence')
        self.assertIn(plan(m, 'veneration')[1][0], ('304', '315', '316', '317'))
        self.assertIn(plan(m, 'gospel')[1][0], ('696', '697'))

    def test_easter_vigil(self) -> None:  # p. 22–23
        m = mass(date(2027, 3, 27))
        self.assertEqual(plan(m, 'mass')[1], ['401'])
        self.assertEqual(plan(m, 'recessional')[1], ['407'])
        self.assertEqual(plan(m, 'baptismal_water')[1], ['511A'])
        self.assertFalse(any(c.startswith('3') for c in candidates(m, 'mass')))


class EasterTests(unittest.TestCase):
    def test_easter_sunday(self) -> None:  # p. 23
        m = mass(date(2027, 3, 28))
        self.assertEqual(plan(m, 'sequence'), ('songs', ['406A']))  # prescribed, one variant
        self.assertNotIn('406A', candidates(m, 'mass'))
        self.assertEqual(plan(m, 'asperges')[1], ['511A'])
        self.assertEqual(plan(m, 'psalm')[1], ['627'])

    def test_octave_does_not_borrow_holy_week_songs(self) -> None:  # neighbours stay within the season
        m = mass(date(2027, 3, 29))
        self.assertNotIn('710', candidates(m, 'recessional'))
        self.assertIn('407', candidates(m, 'recessional'))

    def test_ascension_and_415(self) -> None:  # p. 24
        ascension = harness.date_of('nanebevstoupeni-pane', 2027)
        self.assertEqual(plan(mass(ascension), 'mass'), ('songs', ['415']))
        before = mass(ascension - timedelta(days=1))
        for part in ('mass', 'recessional', 'communion'):
            self.assertNotIn('415', candidates(before, part))
        novena = mass(ascension + timedelta(days=5))
        self.assertIn('415', candidates(novena, 'mass'))
        self.assertIn(plan(novena, 'recessional')[1][0], ('423', '422A', '422B', '422C'))

    def test_third_and_seventh_sunday(self) -> None:  # p. 24
        self.assertEqual(plan(mass(harness.date_of('3-nedele-velikonocni', 2027)), 'mass')[1], ['410'])
        seventh = mass(harness.date_of('7-nedele-velikonocni', 2027))
        self.assertEqual(plan(seventh, 'mass')[1], ['415'])
        self.assertEqual(tier_of(seventh, 'recessional'), '▲')

    def test_pentecost(self) -> None:  # p. 25
        m = mass(harness.date_of('seslani-ducha-svateho', 2027))
        self.assertEqual(plan(m, 'mass')[1], ['421'])
        self.assertEqual(plan(m, 'sequence'), ('songs', ['422A']))
        self.assertEqual(plan(m, 'recessional')[1], ['407'])


class OrdinaryTimeTests(unittest.TestCase):
    def test_ordinary_sunday_is_honest_about_gaps(self) -> None:  # p. 25
        m = mass(date(2027, 1, 31))
        self.assertTrue(m.gap)
        self.assertEqual(tier_of(m, 'mass'), '●')
        self.assertIn('523', candidates(m, 'mass'))
        self.assertNotIn('510A', candidates(m, 'mass'))

    def test_cycle_specific_sundays(self) -> None:  # p. 26
        a32 = mass(harness.date_of('32-nedele-v-mezidobi', 2026))  # year A
        self.assertEqual(plan(a32, 'mass')[1], ['519'])
        b32 = mass(harness.date_of('32-nedele-v-mezidobi', 2027))  # year B
        self.assertNotIn('519', candidates(b32, 'mass')[:1])
        b18 = mass(harness.date_of('18-nedele-v-mezidobi', 2027))  # 18.AB
        self.assertIn(plan(b18, 'mass')[1][0], ('710', '717A', '717B', '717C'))

    def test_trinity_corpus_christi_sacred_heart(self) -> None:  # p. 26–27
        self.assertIn(plan(mass(date(2027, 5, 23)), 'mass')[1][0], ('514', '520'))
        corpus = mass(date(2027, 5, 27))
        self.assertIn(plan(corpus, 'mass')[1][0], ('710', '717A', '717B', '717C'))
        self.assertEqual(plan(corpus, 'adoration')[1], ['704A'])
        after_corpus = mass(date(2027, 5, 30))
        self.assertIn(plan(after_corpus, 'mass')[1][0], ('710', '717A', '717B', '717C'))
        heart = mass(harness.date_of('nejsvetejsiho-srdce-jezisova', 2027))
        self.assertIn(plan(heart, 'mass')[1][0], ('702', '709', '715', '728'))

    def test_christ_the_king_and_week_34(self) -> None:  # p. 26–27
        king = mass(date(2027, 11, 21))
        self.assertEqual(plan(king, 'mass')[1], ['707'])
        self.assertIn(plan(king, 'adoration')[1][0], ('703', '631'))
        self.assertEqual(candidates(mass(date(2027, 11, 23), title='Úterý'), 'mass')[0], '519')

    def test_categories(self) -> None:  # p. 8–9
        apostles = mass(date(2027, 5, 3))  # sv. Filip a Jakub
        self.assertEqual(plan(apostles, 'mass')[1], ['827'])
        martyr = mass(date(2027, 11, 22))  # sv. Cecílie, panna a mučednice
        self.assertIn('842', candidates(martyr, 'mass'))
        cm = mass(date(2027, 7, 5), 'olm')
        self.assertEqual(plan(cm, 'entrance')[1], ['838'])
        self.assertEqual(plan(cm, 'mass')[0], 'songs')  # mešní píseň + 838 ke vstupu (p. 8)
        self.assertEqual(tier_of(cm, 'entrance'), '■')

    def test_marian_communion_only_on_marian_days(self) -> None:  # p. 8 + author's rule
        self.assertNotIn('813A', candidates(mass(date(2027, 1, 27), title='Středa'), 'communion'))
        self.assertIn('813A', candidates(mass(date(2027, 5, 31)), 'communion'))  # Navštívení Panny Marie


class SmokeTests(unittest.TestCase):
    def test_whole_year_two_dioceses(self) -> None:
        for diocese in ('czech', 'olm'):
            d = date(2027, 1, 1)
            while d.year == 2027:
                result = harness.day(d, diocese)
                for m in result.masses:
                    with self.subTest(day=d, diocese=diocese, mass=m.title):
                        parts = [e.part for e in m.plan]
                        # either a mešní píseň, or one song per part (late Advent), or a silenced mass (Velký pátek)
                        self.assertTrue('mass' in parts or {'entrance', 'gospel', 'offertory'} <= set(parts), parts)
                        sung = {e.part for e in m.plan if e.kind == 'songs'}
                        self.assertFalse('mass' in sung and {'entrance', 'gospel', 'offertory'} <= sung, parts)
                d += timedelta(days=1)

    def test_deterministic(self) -> None:
        a = harness.day(date(2027, 2, 3))
        b = harness.day(date(2027, 2, 3))
        self.assertEqual([[(e.part, [s.code for s in e.songs]) for e in m.plan] for m in a.masses],
                         [[(e.part, [s.code for s in e.songs]) for e in m.plan] for m in b.masses])


if __name__ == '__main__':
    unittest.main()
