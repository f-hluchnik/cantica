"""The committed ruleset must lint cleanly against the committed calendar (CI gate)."""
import unittest

from catalog.curation import Curation
from catalog.rulerecords import RuleRecord
from engine.lint import lint
from liturgy.periods import Periods
from tests.book import harness


def _days() -> dict:
    return {code: harness.calendar_days(calendar).values() for code, calendar in harness.CALENDAR_OF.items()}


class CommittedRulesetTests(unittest.TestCase):
    def test_lint_is_clean(self) -> None:
        curation = Curation.load(harness.DATA / 'curated' / 'curation.yaml')
        report = lint(curation, harness.catalog(), Periods.load(harness.DATA / 'liturgy' / 'periods.yaml'),
                      _days(), harness.categories())
        self.assertEqual(report.errors, [])
        self.assertGreater(report.days_checked, 1000)
        # Some Sunday rules legitimately never fire in the data window (e.g. 14.A in 2026 is replaced by
        # sv. Cyril a Metoděj, 20.B in 2027 by Nanebevzetí Panny Marie); anything else is a real warning.
        self.assertTrue(all('never applies' in w for w in report.warnings), report.warnings)
        self.assertLessEqual(len(report.warnings), 5, report.warnings)
        self.assertEqual(report.overrides, [])


class LintDetectsProblemsTests(unittest.TestCase):
    def _lint(self, *rules: RuleRecord) -> object:
        curation = Curation.load(harness.DATA / 'curated' / 'curation.yaml')
        curation.rules = list(rules)
        return lint(curation, harness.catalog(), Periods.load(harness.DATA / 'liturgy' / 'periods.yaml'),
                    _days(), harness.categories())

    def test_unknown_references(self) -> None:
        report = self._lint(
            RuleRecord(parts=['mass'], songs='523', celebration='no-such-day', position=1),
            RuleRecord(parts=['mass'], songs='523', period='no_such_period', position=2),
            RuleRecord(parts=['mass'], songs='999', season='advent', position=3),
        )
        text = ' | '.join(report.errors)
        self.assertIn('unknown celebration', text)
        self.assertIn('unknown period', text)
        self.assertIn('unknown song', text)

    def test_contradiction_and_never_fires(self) -> None:
        report = self._lint(
            RuleRecord(parts=['mass'], songs='523', season='ordinary', position=1),
            RuleRecord(parts=['mass'], strength='avoid', songs='523', season='ordinary', position=2),
            RuleRecord(parts=['mass'], songs='512', season='ordinary', cycles='A', day='weekday',
                       celebration='5-nedele-v-mezidobi', position=3),  # Sundays only exist on Sundays
        )
        self.assertTrue(any('both recommended and avoided' in e for e in report.errors), report.errors)  # same source
        self.assertTrue(any('never applies' in w for w in report.warnings), report.warnings)

    def test_not_a_mass_song(self) -> None:
        report = self._lint(RuleRecord(parts=['mass'], songs='510', season='ordinary', position=1))
        self.assertEqual(report.errors, [])  # 510A/510B are unverified (None), not False

    def test_coverage_gaps_are_reported(self) -> None:
        report = self._lint(RuleRecord(parts=['mass'], songs='523', season='ordinary', position=1))
        self.assertTrue(any(g.celebration_key == 'sv-tomase-akvinskeho-kneze-a-ucitele-cirkve' for g in report.gaps))


if __name__ == '__main__':
    unittest.main()
