"""Django integration tests: calendar_build into the DB and the day page.

Run with:  python manage.py test tests
"""
import importlib
import tempfile
from datetime import date
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from liturgy.catalog import Catalog
from liturgy.constants import CATEGORIES, DIOCESES
from liturgy.days import unknown_titles
from liturgy.models import CalendarBuild, CalendarDay, Celebration, Diocese, Occurrence
from liturgy.snapshot import write_snapshot
from tests.helpers import fixture_snapshot

FIXTURE_MONTHS = (('czech', 2027, 11), ('czech', 2027, 12), ('czech-olm', 2027, 7), ('czech-pha', 2027, 7))


class DataDirMixin:
    """Temporary data/ dir with fixture snapshots and a catalog that knows every title."""

    def setUp(self) -> None:
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)
        self.raw_dir = self.data_dir / 'calendar' / 'raw'
        self.catalog_file = self.data_dir / 'liturgy' / 'celebrations.yaml'
        snapshots = [fixture_snapshot(*m) for m in FIXTURE_MONTHS]
        for snapshot in snapshots:
            write_snapshot(self.raw_dir, snapshot)
        catalog = Catalog()
        for title in sorted(unknown_titles(snapshots, catalog)):
            catalog.register(title)
        catalog.save(self.catalog_file)
        self._settings = override_settings(
            CANTICA_RAW_CALENDAR_DIR=self.raw_dir,
            CANTICA_CELEBRATIONS_FILE=self.catalog_file,
        )
        self._settings.enable()

    def tearDown(self) -> None:
        self._settings.disable()
        self._tmp.cleanup()
        super().tearDown()

    def build(self, *args: str) -> str:
        out = StringIO()
        call_command('calendar_build', *args, stdout=out, stderr=StringIO())
        return out.getvalue()


class SeedTests(TestCase):
    def test_seed_matches_constants(self) -> None:
        seed = importlib.import_module('liturgy.migrations.0002_seed_dioceses_categories')
        self.assertEqual(seed.DIOCESES, tuple((d.code, d.name, d.calapi_calendar) for d in DIOCESES))
        self.assertEqual(seed.CATEGORIES, CATEGORIES)
        self.assertEqual(Diocese.objects.count(), len(DIOCESES))


class CalendarBuildTests(DataDirMixin, TestCase):
    def test_build_writes_days_and_occurrences(self) -> None:
        self.build()
        self.assertEqual(CalendarDay.objects.filter(diocese_id='czech').count(), 61)
        self.assertEqual(CalendarDay.objects.filter(diocese_id='olm').count(), 31)
        immaculate = Occurrence.objects.get(day__diocese_id='czech', day__date=date(2027, 12, 8))
        self.assertEqual(immaculate.celebration.name, 'Panny Marie, počaté bez poskvrny prvotního hříchu')
        feria = Occurrence.objects.get(day__diocese_id='czech', day__date=date(2027, 12, 2))
        self.assertIsNone(feria.celebration)
        build = CalendarBuild.objects.get()
        self.assertEqual(build.last_date, date(2027, 7, 31))  # earliest end among calendars

    def test_second_build_is_skipped_and_force_rebuilds(self) -> None:
        self.build()
        self.assertIn('unchanged', self.build())
        self.build('--force')
        self.assertEqual(CalendarBuild.objects.count(), 2)
        self.assertEqual(CalendarDay.objects.filter(diocese_id='czech').count(), 61)

    def test_unknown_title_fails_and_writes_nothing(self) -> None:
        catalog = Catalog.load(self.catalog_file)
        del catalog.entries['vsech-svatych']
        Catalog(list(catalog.entries.values())).save(self.catalog_file)
        with self.assertRaises(CommandError):
            self.build()
        self.assertEqual(CalendarDay.objects.count(), 0)

    def test_check_does_not_touch_db(self) -> None:
        self.build('--check')
        self.assertEqual(CalendarDay.objects.count(), 0)

    def test_catalog_command_check(self) -> None:
        call_command('calendar_catalog', stdout=StringIO())
        self.catalog_file.write_text('', encoding='utf-8')
        with self.assertRaises(CommandError):
            call_command('calendar_catalog', stdout=StringIO(), stderr=StringIO())
        call_command('calendar_catalog', '--register-new', stdout=StringIO())
        self.assertIn('vsech-svatych', Catalog.load(self.catalog_file).entries)

    def test_removed_celebration_is_deleted_on_rebuild(self) -> None:
        self.build()
        self.assertTrue(Celebration.objects.filter(key='vsech-svatych').exists())
        (self.raw_dir / 'czech' / '2027-11.json').unlink()
        catalog = Catalog.load(self.catalog_file)
        del catalog.entries['vsech-svatych']
        Catalog(list(catalog.entries.values())).save(self.catalog_file)
        self.build()
        self.assertFalse(Celebration.objects.filter(key='vsech-svatych').exists())


class DayPageTests(DataDirMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.build()

    def test_day_page(self) -> None:
        response = self.client.get('/2027-12-08/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Panny Marie, počaté bez poskvrny prvotního hříchu')
        self.assertContains(response, 'Sláva na výsostech: ano')
        self.assertContains(response, 'Věřím: ano')
        self.assertContains(response, 'colour-white')

    def test_optional_memorial_and_feria_are_both_shown(self) -> None:
        response = self.client.get('/2027-11-03/')
        self.assertContains(response, 'Středa 31. týdne v mezidobí')
        self.assertContains(response, 'Sv. Martina de Porres, řeholníka')
        self.assertContains(response, 'z kteréhokoli z uvedených formulářů')

    def test_commemoration_is_a_note(self) -> None:
        response = self.client.get('/2027-12-21/')
        self.assertContains(response, 'Připomínka: Sv. Petra Kanisia')
        self.assertNotContains(response, '<h3>Sv. Petra Kanisia')

    def test_invalid_date_is_404(self) -> None:
        self.assertEqual(self.client.get('/2027-02-30/').status_code, 404)
        self.assertEqual(self.client.get('/2027-13-01/').status_code, 404)

    def test_day_without_data(self) -> None:
        response = self.client.get('/2031-01-01/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'zatím nemáme liturgický kalendář')

    def test_date_picker_redirects(self) -> None:
        response = self.client.get('/?datum=2027-12-08')
        self.assertRedirects(response, '/2027-12-08/', fetch_redirect_response=False)
        response = self.client.get('/?date=2027-12-08&dieceze=olm')  # v1 links
        self.assertRedirects(response, '/2027-12-08/?dieceze=olm', fetch_redirect_response=False)
        response = self.client.get('/?datum=nonsense')
        self.assertRedirects(response, '/', fetch_redirect_response=False)

    def test_diocese_selection_and_cookie(self) -> None:
        response = self.client.get('/2027-07-27/?dieceze=olm')
        self.assertContains(response, 'Sv. Gorazda a druhů')
        self.assertNotContains(response, 'Úterý 17. týdne v mezidobí')  # obligatory memorial in Olomouc
        self.assertEqual(response.cookies['dieceze'].value, 'olm')
        response = self.client.get('/2027-07-27/?dieceze=pha')
        self.assertContains(response, 'Úterý 17. týdne v mezidobí')  # optional memorial in Prague
        self.client.cookies['dieceze'] = 'olm'
        response = self.client.get('/2027-07-27/')
        self.assertNotIn('dieceze', response.cookies)  # unchanged -> not re-set
        self.assertContains(response, 'value="olm" selected')

    def test_unknown_diocese_falls_back(self) -> None:
        response = self.client.get('/2027-12-08/?dieceze=xyz')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('dieceze', response.cookies)

    def test_about_and_health(self) -> None:
        self.assertEqual(self.client.get('/o-aplikaci/').status_code, 200)
        data = self.client.get('/health').json()
        self.assertEqual(data['calendar_last_date'], '2027-07-31')
        self.assertIn(data['status'], ('ok', 'warn'))


class EmptyHealthTests(TestCase):
    def test_live_ignores_unknown_host(self) -> None:
        response = self.client.get('/live', HTTP_HOST='172.19.0.2')  # Fly checks may use the private IP
        self.assertEqual(response.status_code, 200)


    def test_health_without_build(self) -> None:
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['status'], 'error')
