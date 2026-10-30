import copy
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError, URLError

from liturgy.calapi import CalapiClient, CalapiError
from liturgy.snapshot import MonthSnapshot, SnapshotError, read_snapshots, snapshot_path, write_snapshot
from liturgy.sync import add_months, month_range, sync
from tests.helpers import FakeResponse, api_payload


class SnapshotTests(unittest.TestCase):
    def test_from_api_parses_days(self) -> None:
        snapshot = MonthSnapshot.from_api('czech', 2027, 3, api_payload('czech', 2027, 3))
        days = snapshot.days()
        self.assertEqual(len(days), 31)
        thursday = days[3]
        self.assertEqual(thursday.occurrences[1].title, 'Sv. Kazimíra')
        self.assertEqual(thursday.occurrences[1].rank_num, Decimal('4.0'))
        self.assertEqual(days[18].occurrences[0].rank_num, Decimal('1.3'))

    def test_missing_day_is_rejected(self) -> None:
        payload = api_payload('czech', 2027, 3)
        del payload[10]
        with self.assertRaises(SnapshotError):
            MonthSnapshot.from_api('czech', 2027, 3, payload)

    def test_wrong_month_is_rejected(self) -> None:
        with self.assertRaises(SnapshotError):
            MonthSnapshot.from_api('czech', 2027, 4, api_payload('czech', 2027, 3))

    def test_weekday_mismatch_is_rejected(self) -> None:
        payload = api_payload('czech', 2027, 3)
        payload[0]['weekday'] = 'sunday'
        with self.assertRaises(SnapshotError):
            MonthSnapshot.from_api('czech', 2027, 3, payload)

    def test_empty_celebrations_are_rejected(self) -> None:
        payload = api_payload('czech', 2027, 3)
        payload[0]['celebrations'] = []
        with self.assertRaises(SnapshotError):
            MonthSnapshot.from_api('czech', 2027, 3, payload)

    def test_not_a_list(self) -> None:
        with self.assertRaises(SnapshotError):
            MonthSnapshot.from_api('czech', 2027, 3, {'error': 'x'})

    def test_roundtrip_and_stable_format(self) -> None:
        snapshot = MonthSnapshot.from_api('czech', 2027, 3, api_payload('czech', 2027, 3))
        text = snapshot.dumps()
        self.assertEqual(MonthSnapshot.loads(text).dumps(), text)
        self.assertEqual(len(text.splitlines()), 31 + 6)  # one line per day
        self.assertIn('Kazimíra', text)  # not \u-escaped
        json.loads(text)  # valid JSON

    def test_write_reports_changes_and_read_back(self) -> None:
        snapshot = MonthSnapshot.from_api('czech', 2027, 3, api_payload('czech', 2027, 3))
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp)
            self.assertTrue(write_snapshot(raw, snapshot))
            self.assertFalse(write_snapshot(raw, snapshot))
            self.assertTrue(snapshot_path(raw, 'czech', 2027, 3).exists())
            [loaded] = list(read_snapshots(raw))
            self.assertEqual(loaded.label, '2027-03')

    def test_file_in_wrong_place_is_rejected(self) -> None:
        snapshot = MonthSnapshot.from_api('czech', 2027, 3, api_payload('czech', 2027, 3))
        with tempfile.TemporaryDirectory() as tmp:
            wrong = Path(tmp) / 'czech-olm' / '2027-03.json'
            wrong.parent.mkdir()
            wrong.write_text(snapshot.dumps(), encoding='utf-8')
            with self.assertRaises(SnapshotError):
                list(read_snapshots(Path(tmp)))


class FakeOpener:
    """Plays back a list of results: bytes -> response, Exception -> raised."""

    def __init__(self, results: list) -> None:
        self.results = list(results)
        self.calls: list[str] = []

    def __call__(self, request: object, timeout: float) -> FakeResponse:
        self.calls.append(request.full_url)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return FakeResponse(result)


def _client(opener: FakeOpener) -> CalapiClient:
    return CalapiClient(opener=opener, sleep=lambda _: None, retries=3)


class CalapiClientTests(unittest.TestCase):
    def test_retries_then_succeeds(self) -> None:
        opener = FakeOpener([URLError('down'), b'not json', b'[1]'])
        self.assertEqual(_client(opener).month('czech', 2027, 3), [1])
        self.assertEqual(len(opener.calls), 3)
        self.assertTrue(opener.calls[0].endswith('/czech/2027/3'))

    def test_client_error_is_not_retried(self) -> None:
        opener = FakeOpener([HTTPError('u', 404, 'nf', {}, None)])
        with self.assertRaises(CalapiError):
            _client(opener).month('czech', 2027, 3)
        self.assertEqual(len(opener.calls), 1)

    def test_server_error_and_empty_body_are_retried(self) -> None:
        opener = FakeOpener([HTTPError('u', 503, 'x', {}, None), b'', b'[]'])
        self.assertEqual(_client(opener).month('czech', 2027, 3), [])

    def test_gives_up(self) -> None:
        opener = FakeOpener([URLError('a'), URLError('b'), URLError('c')])
        with self.assertRaises(CalapiError):
            _client(opener).month('czech', 2027, 3)


class FakeClient:
    def __init__(self, data: dict) -> None:
        self.data = data

    def month(self, calendar: str, year: int, month: int) -> object:
        value = self.data[(calendar, year, month)]
        if isinstance(value, Exception):
            raise value
        return copy.deepcopy(value)


class SyncTests(unittest.TestCase):
    def test_month_helpers(self) -> None:
        self.assertEqual(list(month_range((2026, 11), (2027, 2))), [(2026, 11), (2026, 12), (2027, 1), (2027, 2)])
        self.assertEqual(add_months(2026, 10, 24), (2028, 10))
        self.assertEqual(add_months(2026, 1, -1), (2025, 12))

    def test_sync_writes_changed_only_and_reports_errors(self) -> None:
        client = FakeClient({
            ('czech', 2027, 11): api_payload('czech', 2027, 11),
            ('czech', 2027, 12): api_payload('czech', 2027, 12),
            ('czech-olm', 2027, 11): CalapiError('boom'),
            ('czech-olm', 2027, 12): {'not': 'a list'},
        })
        months = [(2027, 11), (2027, 12)]
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp)
            first = sync(client, raw, ['czech', 'czech-olm'], months)
            self.assertEqual(first.changed, ['czech 2027-11', 'czech 2027-12'])
            self.assertEqual(len(first.errors), 2)
            self.assertFalse(first.ok)
            second = sync(client, raw, ['czech'], months)
            self.assertEqual(second.unchanged, ['czech 2027-11', 'czech 2027-12'])
            self.assertTrue(second.ok)


if __name__ == '__main__':
    unittest.main()
