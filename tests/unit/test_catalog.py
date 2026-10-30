import tempfile
import unittest
from pathlib import Path

from catalog.codes import (
    code_sort_key,
    expand,
    has_verse,
    is_valid_code,
    is_valid_verses,
    number_of,
    verse_numbers,
)
from catalog.curation import Curation, CurationError, GroupRecord, SongRecord

ROOT = Path(__file__).resolve().parents[2]
CURATION_FILE = ROOT / 'data' / 'curated' / 'curation.yaml'


class CodesTests(unittest.TestCase):
    def test_codes(self) -> None:
        for code in ('001', '523', '101A', 'Z781', 'Z079', '930C'):
            self.assertTrue(is_valid_code(code), code)
        for code in ('1', '5230', 'z781', '101a', 'Z', '523 '):
            self.assertFalse(is_valid_code(code), code)

    def test_number_of(self) -> None:
        self.assertEqual(number_of('101A'), '101')
        self.assertEqual(number_of('523'), '523')
        self.assertEqual(number_of('Z781'), 'Z781')
        with self.assertRaises(ValueError):
            number_of('abc')

    def test_sort_order(self) -> None:
        codes = ['Z781', '782', '781', '101B', '101A', '1000X']
        self.assertEqual(sorted(codes, key=code_sort_key), ['101A', '101B', '781', 'Z781', '782', '1000X'])

    def test_verses(self) -> None:
        self.assertTrue(all(is_valid_verses(v) for v in (None, '-', '*', '4', '4,5', '12')))
        self.assertFalse(any(is_valid_verses(v) for v in ('', '0', '4,', '4 ,5', 'a', '*,4')))
        self.assertEqual(verse_numbers('4,5'), (4, 5))
        self.assertEqual(verse_numbers('*'), ())
        self.assertEqual(verse_numbers(None), ())
        self.assertTrue(has_verse('*'))
        self.assertTrue(has_verse('4'))
        self.assertFalse(has_verse(None))  # unknown is never treated as yes
        self.assertFalse(has_verse('-'))

    def test_expand(self) -> None:
        catalog = ['523', '813A', '813B', '781', 'Z781', '101A', '101B', '101C']
        self.assertEqual(expand('813', catalog), ['813A', '813B'])
        self.assertEqual(expand('813B', catalog), ['813B'])
        self.assertEqual(expand('781', catalog), ['781'])  # never the Z appendix song
        self.assertEqual(expand('Z781', catalog), ['Z781'])
        self.assertEqual(expand('523', catalog), ['523'])
        self.assertEqual(expand('999', catalog), [])


class CurationTests(unittest.TestCase):
    def _sample(self) -> Curation:
        return Curation(
            version=3,
            songs=[
                SongRecord('523', 'Ty jsi, Pane, v každém chrámě', 'mass_general', mass_song=True,
                           communion_verses='4', recessional_verses='6', verse_count=6, reviewed=True),
                SongRecord('813A', 'Velebí má duše Hospodina', 'mary_saints', communion_verses='-'),
                SongRecord('001', 'Modlitba Páně', 'prayers'),
            ],
            groups=[GroupRecord('mesni_obecne', 'mešní písně obecné', ['523'], source_page=25)],
        )

    def test_roundtrip_and_compact_format(self) -> None:
        curation = self._sample()
        text = curation.dumps()
        again = Curation.loads(text)
        self.assertEqual(again.dumps(), text)
        self.assertEqual(again.version, 3)
        self.assertEqual(again.songs[0].code, '001')  # sorted in Kancionál order, '001' stays a string
        self.assertIn("{code: '001', title: Modlitba Páně, section: prayers}", text)  # defaults omitted
        self.assertEqual(again.problems(), [])

    def test_validation(self) -> None:
        curation = self._sample()
        curation.songs.append(SongRecord('523', 'dup', 'mass_general'))
        curation.songs.append(SongRecord('77', 'bad', 'nowhere', communion_verses='x'))
        curation.songs[0].recessional_verses = '7'  # > verse_count
        curation.groups.append(GroupRecord('Bad-Key', 'x', ['999', '999']))
        problems = ' | '.join(curation.problems())
        for expected in ('duplicate code', 'invalid code', 'unknown section', 'invalid communion_verses',
                         'exceeds verse_count', 'key must be', 'unknown songs', 'duplicate members'):
            self.assertIn(expected, problems)
        with self.assertRaises(CurationError):
            curation.validate()

    def test_malformed_file(self) -> None:
        with self.assertRaises(CurationError):
            Curation.loads('songs: [{title: x}]')
        with self.assertRaises(CurationError):
            Curation.loads('- a list')
        with self.assertRaises(CurationError):
            Curation.loads('version: [')

    def test_save_reports_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'curation.yaml'
            self.assertTrue(self._sample().save(path))
            self.assertFalse(self._sample().save(path))


class CommittedDataTests(unittest.TestCase):
    """The committed curation file must always be valid."""

    def test_committed_curation_is_valid(self) -> None:
        curation = Curation.load(CURATION_FILE)
        self.assertEqual(curation.problems(), [])
        codes = {s.code for s in curation.songs}
        self.assertGreater(len(codes), 500)
        for code in ('523', '101A', 'Z781', '813B', '930C', 'Z991'):
            self.assertIn(code, codes)


if __name__ == '__main__':
    unittest.main()
