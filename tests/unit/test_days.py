import unittest
from datetime import date

from liturgy.catalog import Catalog
from liturgy.days import build, unknown_titles
from tests.helpers import all_fixture_snapshots, fixture_snapshot


def _catalog_for(snapshots: list) -> Catalog:
    catalog = Catalog()
    for title in unknown_titles(snapshots, catalog):
        catalog.register(title)
    return catalog


class BuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshots = [fixture_snapshot('czech', 2027, 11), fixture_snapshot('czech', 2027, 12)]
        self.catalog = _catalog_for(self.snapshots)

    def test_clean_build(self) -> None:
        result = build(self.snapshots, self.catalog)
        self.assertTrue(result.ok, result.problems)
        self.assertEqual(len(result.days), 61)

    def test_ferias_are_not_catalogued(self) -> None:
        result = build(self.snapshots, self.catalog)
        day = next(d for d in result.days if d.date == date(2027, 11, 3))
        feria, memorial = day.occurrences
        self.assertIsNone(feria.celebration_key)
        self.assertEqual(memorial.celebration_key, 'sv-martina-de-porres-reholnika')
        self.assertIsNone(self.catalog.resolve('17. prosince'))  # privileged feria, still a feria

    def test_commemoration_is_not_a_mass_option(self) -> None:
        result = build(self.snapshots, self.catalog)
        day = next(d for d in result.days if d.date == date(2027, 12, 21))
        self.assertEqual([o.is_mass_option for o in day.occurrences], [True, False])

    def test_cycles_are_computed(self) -> None:
        result = build(self.snapshots, self.catalog)
        before = next(d for d in result.days if d.date == date(2027, 11, 27))
        after = next(d for d in result.days if d.date == date(2027, 11, 28))
        self.assertEqual((before.sunday_cycle, before.ferial_cycle), ('B', 1))
        self.assertEqual((after.sunday_cycle, after.ferial_cycle), ('C', 2))

    def test_unknown_title_is_a_problem(self) -> None:
        result = build(self.snapshots, Catalog())
        self.assertFalse(result.ok)
        self.assertIn('Všech svatých', result.unknown_titles)
        self.assertTrue(any('Všech svatých' in p for p in result.problems))

    def test_month_gap_is_a_problem(self) -> None:
        snapshots = [fixture_snapshot('czech', 2027, 3), fixture_snapshot('czech', 2027, 5)]
        result = build(snapshots, _catalog_for(snapshots))
        self.assertTrue(any('not contiguous' in p for p in result.problems))

    def test_dioceses_differ(self) -> None:
        snapshots = [fixture_snapshot('czech-olm', 2027, 7), fixture_snapshot('czech-pha', 2027, 7)]
        result = build(snapshots, _catalog_for(snapshots))
        self.assertTrue(result.ok, result.problems)
        by_calendar = {d.calendar: d for d in result.days if d.date == date(2027, 7, 27)}
        self.assertEqual([o.rank_label for o in by_calendar['czech-olm'].occurrences], ['památka'])
        self.assertEqual([o.rank_label for o in by_calendar['czech-pha'].occurrences], ['ferie', 'nezávazná památka'])
        # same celebration, same key, in both dioceses
        self.assertEqual(by_calendar['czech-olm'].occurrences[0].celebration_key,
                         by_calendar['czech-pha'].occurrences[1].celebration_key)

    def test_all_fixtures_have_known_seasons_and_ranks(self) -> None:
        snapshots = all_fixture_snapshots()
        result = build(snapshots, _catalog_for(snapshots))
        non_gap = [p for p in result.problems if 'not contiguous' not in p]
        self.assertEqual(non_gap, [])


if __name__ == '__main__':
    unittest.main()
