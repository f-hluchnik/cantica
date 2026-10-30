import unittest
from datetime import date

from liturgy import norms
from liturgy.norms import ACCLAMATION_ALLELUIA as ALL
from liturgy.norms import ACCLAMATION_LENT as LENT
from tests.helpers import fixture_snapshot


class EasterAndAdventTests(unittest.TestCase):
    def test_easter(self) -> None:
        known = {
            2024: date(2024, 3, 31),
            2025: date(2025, 4, 20),
            2026: date(2026, 4, 5),
            2027: date(2027, 3, 28),
            2028: date(2028, 4, 16),
            2038: date(2038, 4, 25),
        }
        for year, expected in known.items():
            self.assertEqual(norms.easter(year), expected, year)

    def test_first_advent_sunday(self) -> None:
        self.assertEqual(norms.first_advent_sunday(2026), date(2026, 11, 29))
        self.assertEqual(norms.first_advent_sunday(2027), date(2027, 11, 28))
        self.assertEqual(norms.first_advent_sunday(2022), date(2022, 11, 27))  # Christmas on Sunday
        self.assertEqual(norms.first_advent_sunday(2023), date(2023, 12, 3))

    def test_liturgical_year_and_cycles(self) -> None:
        # 2025/26 = A, II ; 2026/27 = B, I ; 2027/28 = C, II (calapi /2027 says C, 2)
        self.assertEqual(norms.liturgical_year(date(2026, 11, 28)), 2026)
        self.assertEqual(norms.liturgical_year(date(2026, 11, 29)), 2027)
        self.assertEqual(norms.sunday_cycle(date(2026, 10, 30)), 'A')
        self.assertEqual(norms.ferial_cycle(date(2026, 10, 30)), 2)
        self.assertEqual(norms.sunday_cycle(date(2027, 7, 4)), 'B')
        self.assertEqual(norms.ferial_cycle(date(2027, 7, 4)), 1)
        self.assertEqual(norms.sunday_cycle(date(2027, 11, 28)), 'C')
        self.assertEqual(norms.ferial_cycle(date(2027, 12, 1)), 2)


class MassNormsTests(unittest.TestCase):
    """Expected values per the General Instruction of the Roman Missal (čl. 53, 68) and calapi ranks."""

    # date: (gloria, credo, acclamation)
    EXPECTED = {
        # Lent / Holy Week / Triduum / Easter octave
        date(2027, 3, 7): (False, True, LENT),    # 4. neděle postní
        date(2027, 3, 8): (False, False, LENT),   # Lent feria
        date(2027, 3, 19): (True, True, LENT),    # sv. Josef, slavnost in Lent: Gloria yes, Aleluja no
        date(2027, 3, 21): (False, True, LENT),   # Květná neděle
        date(2027, 3, 22): (False, False, LENT),  # Pondělí Svatého týdne
        date(2027, 3, 25): (True, False, LENT),   # Zelený čtvrtek
        date(2027, 3, 26): (None, None, LENT),    # Velký pátek: no mass
        date(2027, 3, 27): (None, None, None),    # Bílá sobota: no mass
        date(2027, 3, 28): (True, True, ALL),     # Zmrtvýchvstání Páně
        date(2027, 3, 29): (True, False, ALL),    # octave weekday
        # Ordinary time, November
        date(2027, 11, 1): (True, True, ALL),     # Všech svatých
        date(2027, 11, 2): (False, False, ALL),   # Dušičky (ranked 'slavnost' by calapi)
        date(2027, 11, 4): (False, False, ALL),   # památka
        date(2027, 11, 7): (True, True, ALL),     # ordinary Sunday
        date(2027, 11, 9): (True, False, ALL),    # svátek on a weekday
        date(2027, 11, 21): (True, True, ALL),    # Krista Krále
        # Advent and Christmas
        date(2027, 11, 28): (False, True, ALL),   # 1. neděle adventní
        date(2027, 11, 30): (True, False, ALL),   # sv. Ondřej, svátek in Advent
        date(2027, 12, 8): (True, True, ALL),     # Neposkvrněné početí
        date(2027, 12, 17): (False, False, ALL),  # privileged Advent feria
        date(2027, 12, 25): (True, True, ALL),    # Narození Páně (Saturday, primary day)
        date(2027, 12, 26): (True, True, ALL),    # Svaté rodiny on Sunday
        date(2027, 12, 29): (True, False, ALL),   # Christmas octave feria
        date(2027, 1, 1): (True, True, ALL),      # Matky Boží
        date(2027, 1, 4): (False, False, ALL),    # Christmas-time feria after the octave
        date(2027, 1, 6): (True, True, ALL),      # Zjevení Páně (weekday, primary day)
        date(2027, 1, 10): (True, True, ALL),     # Křtu Páně (Sunday feast)
        # Easter time, May
        date(2027, 5, 2): (True, True, ALL),      # Easter Sunday of the season
        date(2027, 5, 6): (True, True, ALL),      # Nanebevstoupení Páně (Thursday)
        date(2027, 5, 16): (True, True, ALL),     # Seslání Ducha svatého
        date(2027, 5, 20): (True, False, ALL),    # Kristus kněz, svátek
        date(2027, 5, 27): (True, True, ALL),     # Těla a krve Páně (Thursday)
    }

    def _first_mass_option(self, day: date) -> tuple:
        snapshot = fixture_snapshot('czech', day.year, day.month)
        raw = next(d for d in snapshot.days() if d.date == day)
        occ = raw.occurrences[0]
        return raw, occ

    def test_expected_norms(self) -> None:
        for day, (gloria, credo, acclamation) in self.EXPECTED.items():
            raw, occ = self._first_mass_option(day)
            result = norms.mass_norms(day, raw.season, occ.rank_label, occ.title)
            with self.subTest(day=day.isoformat(), title=occ.title):
                self.assertEqual(result.gloria, gloria, 'gloria')
                self.assertEqual(result.credo, credo, 'credo')
                self.assertEqual(result.acclamation, acclamation, 'acclamation')

    def test_optional_memorial_has_no_gloria(self) -> None:
        raw, _ = self._first_mass_option(date(2027, 11, 3))
        memorial = raw.occurrences[1]
        result = norms.mass_norms(raw.date, raw.season, memorial.rank_label, memorial.title)
        self.assertFalse(result.gloria)
        self.assertFalse(result.credo)

    def test_no_mass_notes(self) -> None:
        self.assertIsNotNone(norms.mass_norms(date(2027, 3, 26), 'lent', 'Velikonoční triduum', 'Velký pátek').note)
        self.assertIsNotNone(norms.mass_norms(date(2027, 3, 27), 'lent', 'Velikonoční triduum', 'Bílá sobota').note)

    def test_ash_wednesday(self) -> None:
        result = norms.mass_norms(date(2027, 2, 10), 'lent', 'Primární liturgické dny', 'Popeleční středa')
        self.assertEqual((result.gloria, result.credo, result.acclamation), (False, False, LENT))

    def test_rank_display(self) -> None:
        self.assertEqual(norms.rank_display(date(2027, 12, 25), 'Primární liturgické dny', 'Narození Páně'), 'slavnost')
        self.assertEqual(norms.rank_display(date(2027, 12, 5), 'Primární liturgické dny', '2. neděle adventní'), 'neděle')
        self.assertEqual(norms.rank_display(date(2027, 3, 22), 'Primární liturgické dny', 'Pondělí Svatého týdne'), '')
        self.assertEqual(norms.rank_display(date(2027, 11, 2), 'slavnost', 'Vzpomínka na všechny věrné zemřelé'), '')
        self.assertEqual(norms.rank_display(date(2027, 11, 3), 'ferie', 'Středa 31. týdne v mezidobí'), '')
        self.assertEqual(norms.rank_display(date(2027, 11, 9), 'svátek', 'Posvěcení lateránské baziliky'), 'svátek')


if __name__ == '__main__':
    unittest.main()
