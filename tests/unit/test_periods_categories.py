import unittest
from datetime import date
from pathlib import Path

from liturgy.catalog import Catalog
from liturgy.categorize import suggest_categories
from liturgy.periods import PeriodError, Periods

ROOT = Path(__file__).resolve().parents[2]


class PeriodTests(unittest.TestCase):
    def setUp(self) -> None:
        self.periods = Periods.load(ROOT / 'data' / 'liturgy' / 'periods.yaml')

    def test_committed_periods_load(self) -> None:
        self.assertIn('advent_late', self.periods.items)

    def test_fixed_and_wrapping(self) -> None:
        self.assertEqual(self.periods.active(date(2027, 12, 31), 'christmas', 1), {'christmas_octave', 'new_year'})
        self.assertEqual(self.periods.active(date(2028, 1, 1), 'christmas', 1), {'christmas_octave', 'new_year'})
        self.assertEqual(self.periods.active(date(2028, 1, 2), 'christmas', 1), set())

    def test_fixed_with_season(self) -> None:
        self.assertIn('advent_early', self.periods.active(date(2026, 11, 29), 'advent', 1))
        self.assertNotIn('advent_early', self.periods.active(date(2026, 11, 28), 'ordinary', 34))
        self.assertIn('advent_late', self.periods.active(date(2026, 12, 17), 'advent', 3))

    def test_easter_relative(self) -> None:
        # Easter 2027 = 28 March
        self.assertIn('holy_week_mon_wed', self.periods.active(date(2027, 3, 22), 'lent', 6))
        self.assertNotIn('holy_week_mon_wed', self.periods.active(date(2027, 3, 25), 'lent', 6))
        self.assertIn('before_ascension', self.periods.active(date(2027, 5, 5), 'easter', 6))
        self.assertNotIn('before_ascension', self.periods.active(date(2027, 5, 6), 'easter', 6))  # Ascension
        self.assertIn('pentecost_novena', self.periods.active(date(2027, 5, 7), 'easter', 6))
        self.assertIn('sunday_after_corpus_christi', self.periods.active(date(2027, 5, 30), 'ordinary', 9))

    def test_season_week(self) -> None:
        self.assertIn('ordinary_week_34', self.periods.active(date(2027, 11, 23), 'ordinary', 34))
        self.assertNotIn('ordinary_week_34', self.periods.active(date(2027, 11, 16), 'ordinary', 33))

    def test_invalid(self) -> None:
        for text in (
            '- {key: x, kind: fixed, from: 13-01, to: 12-01}',
            '- {key: x, kind: easter, from: 5, to: 1}',
            '- {key: x, kind: season_week, weeks: [3]}',
            '- {key: x, kind: nonsense}',
            '- {key: Bad, kind: easter, from: 0, to: 1}',
            '- {key: x, kind: easter, from: 0, to: 1}\n- {key: x, kind: easter, from: 0, to: 1}',
        ):
            with self.subTest(text=text), self.assertRaises(PeriodError):
                Periods.loads(text)


class CategoryTests(unittest.TestCase):
    CASES = {
        'Sv. Jana Nepomuckého, kněze a mučedníka, hlavního patrona Čech':
            ['martyr', 'pastor', 'czech_patron', 'saint'],
        'Sv. Lucie, panny a mučednice': ['martyr', 'virgin', 'saint'],
        'Sv. Petra a Pavla, apoštolů': ['apostle_evangelist'],
        'Svaté rodiny Ježíše, Marie a Josefa': [],
        'Čtvrtek Svatého týdne': [],
        'Panny Marie Růžencové': ['virgin_mary'],
        'Sobotní památka Panny Marie': ['virgin_mary'],
        'Sv. Jáchyma a Anny, rodičů Panny Marie': ['saint'],  # not Marian
        'Nejsvětějšího srdce Ježíšova': ['lord'],
        'Narození Páně': [],  # seasonal songs apply, not "701 ad."
        '2. neděle po Narození Páně': [],
        'Posvěcení lateránské baziliky': ['dedication'],
        'Výročí posvěcení katedrály sv. Václava': ['dedication'],
        'Vzpomínka na všechny věrné zemřelé': ['dead'],
        'Svatých andělů strážných': ['angel'],
        'Umučení sv. Jana Křtitele': ['martyr', 'saint'],
        'Sv. Prokopa, opata': ['religious', 'czech_patron', 'saint'],
        'Sv. Kateřiny Sienské, panny a učitelky církve, patronky Evropy': ['doctor', 'virgin', 'saint'],
    }

    def test_suggestions(self) -> None:
        for title, expected in self.CASES.items():
            with self.subTest(title=title):
                self.assertEqual(suggest_categories(title), expected)

    def test_committed_catalog_is_valid(self) -> None:
        catalog = Catalog.load(ROOT / 'data' / 'liturgy' / 'celebrations.yaml')
        self.assertGreater(len(catalog), 300)


if __name__ == '__main__':
    unittest.main()
