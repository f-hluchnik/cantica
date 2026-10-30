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

    def test_marian_solemnity_beats_advent_avoid(self) -> None:  # p. 8, 46 vs author's Advent rule (●)
        m = mass(date(2026, 12, 8))
        self.assertEqual(tier_of(m, 'mass'), '▲')
        self.assertIn(plan(m, 'mass')[1][0], ('130', '801'))
        self.assertIn('805', candidates(m, 'mass'))  # @marianske, possible as well
        self.assertEqual(plan(m, 'recessional')[1], ['117'])

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
        self.assertEqual(plan(palm, 'recessional')[1], ['315'])  # "po mši" = na závěr
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
        self.assertFalse(m.gap)  # no gap message on Sundays: the general songs are what the book says
        self.assertEqual([i.label for s in m.summary for i in s.items], ['mešní písně obecné'])
        self.assertIn('707', candidates(m, 'mass'))  # the other general groups still feed the plan
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
        self.assertEqual(tier_of(cm, 'entrance'), '▲')  # 838/1 (p. 38)

    def test_813_is_for_thanksgiving_not_communion(self) -> None:  # p. 8, 25: "po přijímání", "při díkůvzdání"
        weekday = mass(date(2027, 1, 27), title='Středa')
        self.assertFalse(any(c.startswith(('8', '9')) for c in candidates(weekday, 'communion')))
        self.assertTrue({'813A', '902'} <= set(candidates(weekday, 'thanksgiving')))
        self.assertEqual(plan(weekday, 'thanksgiving'), ('', []))  # not a standard part: only when specific
        self.assertEqual(plan(mass(date(2027, 5, 31)), 'thanksgiving')[1], ['813A'])  # Navštívení Panny Marie
        visitation = mass(date(2027, 5, 31))  # Navštívení Panny Marie: "po přijímání je vhodná 813" (p. 8)
        self.assertNotIn('813A', candidates(visitation, 'communion'))
        self.assertIn('813A', candidates(visitation, 'thanksgiving'))


class CategoryTests(unittest.TestCase):
    """■ songs by category (pp. 8-9), as decided in the M4 category review."""

    def test_saint_without_own_song(self) -> None:  # p. 9: 840/841 by default, 845 for women
        m = mass(date(2027, 8, 27))  # sv. Monika
        self.assertEqual(tier_of(m, 'mass'), '■')
        self.assertTrue({'840', '841', '845'} <= set(candidates(m, 'mass')))
        self.assertIn(plan(m, 'mass')[1][0], ('840', '841', '845'))

    def test_martyrs_always_get_842(self) -> None:  # p. 9
        agatha = mass(date(2027, 2, 5))
        self.assertTrue({'842', '845'} <= set(candidates(agatha, 'mass')))
        wenceslas = mass(date(2027, 9, 28))  # own song 831: 842 stays, the general 840/841 go
        self.assertIn('842', candidates(wenceslas, 'mass'))
        self.assertFalse({'840', '841'} & set(candidates(wenceslas, 'mass')))

    def test_own_song_replaces_dedication_songs(self) -> None:  # p. 40, 44, 45
        lateran = mass(harness.date_of('posveceni-lateranske-baziliky', 2027))
        self.assertTrue({'917', '918'} <= set(candidates(lateran, 'mass')))
        basilicas = ('posveceni-rimske-baziliky-panny-marie', 'posveceni-rimskych-bazilik-svatych-apostolu-petra-a-pavla')
        for key in basilicas:
            m = mass(harness.date_of(key, 2027))
            with self.subTest(key):
                mass_part = next(p for p in m.parts if p.part == 'mass')
                self.assertEqual(tier_of(m, 'mass'), '▲')
                self.assertFalse([e.code for e in mass_part.entries if e.tier == '■'])  # no ■ 917/918

    def test_christmas_octave(self) -> None:  # p. 19: Christmas repertoire, 201 at the end every day
        for day in (date(2026, 12, 25), date(2026, 12, 29), date(2027, 1, 1)):
            m = mass(day)
            with self.subTest(day=day):
                self.assertEqual(plan(m, 'recessional')[1], ['201'])
                self.assertFalse(any(c.startswith('8') for c in candidates(m, 'mass')))

    def test_pentecost_is_not_a_saints_day(self) -> None:
        m = mass(date(2027, 5, 16))
        self.assertFalse({'840', '841'} & set(candidates(m, 'mass')))


def summary(m: MassResult) -> dict[str, list[str]]:
    return {line.part: [x for i in line.items for x in ([i.label] if i.kind == 'group' else [s.code for s in i.songs])]
            for line in m.summary}


class ReviewM5Tests(unittest.TestCase):
    """The author's review before M5."""

    def test_mass_song_continues_at_communion(self) -> None:  # 827 for sv. Ondřej is sung at communion too
        m = mass(date(2026, 11, 30))
        self.assertEqual(plan(m, 'mass')[1], ['827'])
        self.assertEqual(plan(m, 'communion'), ('', []))
        epiphany = mass(harness.date_of('zjeveni-pane', 2027))  # but a ▲ communion song is named (p. 19)
        self.assertIn(plan(epiphany, 'communion')[1][0], ('213', '219'))

    def test_season_label_every_day_but_no_single_general_songs(self) -> None:  # p. 17
        feria = mass(date(2026, 12, 1), title='Úterý')
        self.assertEqual(summary(feria), {'mass': ['Adventní písně']})
        self.assertIn(plan(feria, 'mass')[1][0], ('121', '123', '126', '129', '101A', '109', '127', '128'))
        memorial = mass(date(2026, 12, 1), title='Edmunda')
        self.assertIn('Adventní písně', summary(memorial)['mass'])
        self.assertIn('842', summary(memorial)['mass'])

    def test_prescribed_and_own_song_is_specific(self) -> None:  # p. 30: 910 on 18. 1.
        m = mass(date(2027, 1, 18), title='Panny Marie')
        entry = next(e for e in next(p for p in m.parts if p.part == 'recessional').entries if e.code == '910')
        self.assertEqual((entry.tier, entry.strength), ('▲', 'prescribed'))

    def test_feasts_take_no_neighbour_songs(self) -> None:  # p. 27 is about ordinary days and Sundays
        for day in (date(2027, 2, 2), date(2027, 11, 2)):
            m = mass(day)
            with self.subTest(day=day):
                self.assertFalse(any(e.neighbour for p in m.parts for e in p.entries))

    def test_short_ranges_are_songs_long_ones_a_label(self) -> None:
        self.assertEqual(summary(mass(date(2027, 5, 1), title='Josefa'))['mass'], ['821', '822', '823', 'velikonoční písně'])
        self.assertEqual(summary(mass(date(2027, 11, 2)))['mass'], ['921', '922', '923', '924', '925'])
        self.assertEqual(summary(mass(date(2027, 4, 14), title='Středa')), {'mass': ['velikonoční písně']})

    def test_general_notes_belong_to_the_day(self) -> None:  # p. 24, 34
        day = harness.day(date(2027, 5, 4), 'czech')
        self.assertTrue(any('V květnu' in n for n in day.notes))
        self.assertTrue(any('415' in n for n in day.notes))
        self.assertFalse(any('V květnu' in n for m in day.masses for e in m.plan for n in e.notes))

    def test_first_friday_votive_mass(self) -> None:
        titles = [m.title for m in harness.day(date(2027, 7, 2), 'czech').masses]
        self.assertTrue(any(t.startswith('První pátek') for t in titles), titles)
        votive = mass(date(2027, 7, 2), title='První pátek')
        self.assertEqual(votive.rank_label, 'votivní mše')
        self.assertIn(plan(votive, 'mass')[1][0], ('702', '709', '715', '728'))
        self.assertEqual(tier_of(votive, 'mass'), '▲')
        for day in (date(2027, 10, 1), date(2027, 3, 5), date(2027, 7, 9)):  # memorial · Lent · 2nd Friday
            with self.subTest(day=day):
                self.assertFalse(any('První pátek' in m.title for m in harness.day(day, 'czech').masses))


class KalendariumTests(unittest.TestCase):
    """Direktář pp. 29-46."""

    def test_czech_patrons_get_their_verse_of_838(self) -> None:  # p. 33-45
        cases = {
            (date(2026, 7, 4), 'Prokopa'): '5',
            (date(2027, 7, 5), 'Cyrila'): '1',
            (date(2027, 9, 28), 'Václava'): '3',
            (date(2027, 11, 13), 'Anežky'): '7',
            (date(2027, 5, 16), None): None,  # Pentecost 2027 replaces Jan Nepomucký: no 838 at all
        }
        for (day, title), verses in cases.items():
            m = mass(day, title=title)
            with self.subTest(day=day):
                entry = next((e for e in m.plan if e.part == 'entrance'), None)
                if verses is None:
                    self.assertIsNone(entry)
                else:
                    self.assertEqual((entry.songs[0].code, entry.songs[0].verses, entry.tier), ('838', verses, '▲'))

    def test_cyril_and_methodius(self) -> None:  # p. 38
        m = mass(date(2027, 7, 5), 'olm')
        self.assertIn(plan(m, 'mass')[1][0], ('828', '829'))
        self.assertEqual(tier_of(m, 'mass'), '▲')

    def test_wenceslas(self) -> None:  # p. 41
        m = mass(date(2027, 9, 28))
        self.assertEqual(plan(m, 'mass')[1], ['831'])
        self.assertEqual(plan(m, 'recessional')[1], ['830A'])
        later = mass(date(2027, 9, 30))  # sv. Jeroným: závěr from a nearby feast, never the archangels' 512
        self.assertNotIn('512', candidates(later, 'recessional'))
        self.assertIn('830A', candidates(later, 'recessional'))

    def test_unity_week(self) -> None:  # p. 30
        m = mass(date(2027, 1, 19))
        self.assertEqual(plan(m, 'recessional')[1], ['910'])
        self.assertEqual(candidates(m, 'mass')[:2], ['706', '911'])

    def test_may(self) -> None:  # p. 34
        feria = mass(date(2027, 5, 12), title='Středa')
        self.assertFalse(any(c.startswith('8') for c in candidates(feria, 'mass')))
        fatima = mass(date(2027, 5, 13), title='Fatimské')
        self.assertIn('805', candidates(fatima, 'mass'))  # Marian celebrations keep Marian songs

    def test_annunciation_in_lent(self) -> None:  # p. 32
        m = mass(date(2026, 3, 25))
        self.assertIn(plan(m, 'mass')[1][0], ('130', '111'))
        self.assertNotIn('817', candidates(m, 'mass'))
        self.assertFalse(any(c.startswith('3') for c in candidates(m, 'mass')))
        self.assertEqual(plan(m, 'recessional')[1], ['117'])

    def test_immaculate_conception(self) -> None:  # p. 46
        m = mass(date(2027, 12, 8))
        self.assertIn(plan(m, 'mass')[1][0], ('130', '801'))
        self.assertIn(plan(m, 'communion')[1][0], ('106', '107', '108', '114', '115', '116', '127'))

    def test_seasonal_notes(self) -> None:  # p. 31, 44
        self.assertIn('811', candidates(mass(date(2027, 2, 11)), 'recessional'))
        self.assertIn(plan(mass(date(2027, 11, 4)), 'recessional')[1][0], ('922', '924'))

    def test_authors_of_texts(self) -> None:  # p. 30, 39, 42
        self.assertEqual(plan(mass(date(2027, 7, 31)), 'communion')[1], ['929'])
        self.assertIn(plan(mass(date(2027, 10, 4)), 'communion')[1][0], ('909', '928'))


class OccasionTests(unittest.TestCase):
    """Direktář pp. 47-48."""

    def _parts(self, key: str) -> dict:
        from engine.occasion import occasion_result

        result = occasion_result(harness.snapshot(), key)
        return result, {p.part: [e.code for e in p.entries] for p in result.parts}

    def test_funeral(self) -> None:
        _, parts = self._parts('pohreb')
        self.assertEqual(parts['mass'], ['921', '923', '925'])
        self.assertEqual(parts['rite'], ['922', '924', '926'])

    def test_confirmation_and_baptism(self) -> None:
        result, parts = self._parts('birmovani')
        self.assertEqual(parts['mass'], ['421', '424', '425'])
        self.assertIn('422A', parts['chrismation'])
        self.assertTrue(result.notes)
        _, parts = self._parts('krest')
        self.assertEqual(parts['rite'], ['906'])

    def test_liturgy_of_the_word_is_notes_and_eucharistic_songs(self) -> None:
        result, parts = self._parts('bohosluzba_slova')
        self.assertEqual(len(result.notes), 2)
        self.assertIn('712', parts['adoration'])

    def test_occasion_rules_never_apply_to_days(self) -> None:
        m = mass(date(2027, 2, 3))
        self.assertNotIn('906', candidates(m, 'mass'))
        self.assertNotIn('rite', [p.part for p in m.parts])


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
