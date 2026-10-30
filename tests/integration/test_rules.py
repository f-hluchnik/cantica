"""Django integration tests: rules in the DB, recommendations on the day page, rule admin, lint command."""
from datetime import date, timedelta
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from catalog.curation import Curation
from catalog.dbsync import export_curation, import_curation
from catalog.models import CurationState
from rules.models import Rule
from rules.services import reset_caches
from tests.integration.test_build_and_views import DataDirMixin

COMMITTED = Path(__file__).resolve().parents[2] / 'data' / 'curated' / 'curation.yaml'


class RecommendationPageTests(DataDirMixin, TestCase):
    """Fixture calendar (Nov–Dec 2027, Jul 2027) + the committed songs and rules."""

    def setUp(self) -> None:
        super().setUp()
        self.build()
        import_curation(Curation.load(COMMITTED))
        reset_caches()

    def test_rules_are_imported_and_exported_unchanged(self) -> None:
        self.assertGreater(Rule.objects.count(), 100)
        self.assertEqual(export_curation().dumps(), COMMITTED.read_text(encoding='utf-8'))

    def test_christ_the_king(self) -> None:  # Direktář p. 26
        response = self.client.get('/2027-11-21/')
        self.assertContains(response, '707: Ježíši, Králi')
        self.assertContains(response, 'Direktář s. 26')
        self.assertContains(response, 'detailní doporučení')
        self.assertNotContains(response, 'Jedna z možných sestav podle Direktáře')  # moved to the about page

    def test_first_sunday_of_advent(self) -> None:  # p. 17
        response = self.client.get('/2027-11-28/')
        self.assertContains(response, '129: Volá hlas')
        self.assertContains(response, '▲')
        self.assertContains(response, 'před mší')  # 128 on Advent Sundays (p. 18)

    def test_general_day_is_honest(self) -> None:
        response = self.client.get('/2027-11-14/')  # 33. neděle v mezidobí, year C (519 is for all cycles)
        self.assertContains(response, '519: Buďte bdělí')
        response = self.client.get('/2027-11-07/')  # 32. neděle, year C: nothing specific, but no gap note on Sundays
        self.assertNotContains(response, 'Direktář žádnou konkrétní píseň neuvádí')
        self.assertContains(response, 'mešní písně obecné')

    def test_commemoration_and_silence_markup(self) -> None:
        response = self.client.get('/2027-12-21/')
        self.assertContains(response, 'Připomínka: Sv. Petra Kanisia')
        self.assertContains(response, 'ke vstupu')  # late Advent: rorate songs per part (p. 17)

    def test_admin_edit_changes_page_immediately(self) -> None:
        rule = Rule.objects.get(celebration='jezise-krista-krale', parts='mass')
        rule.songs = '523'
        rule.save()
        response = self.client.get('/2027-11-21/')
        self.assertContains(response, '523: Ty jsi, Pane, v každém chrámě')
        self.assertTrue(CurationState.current().has_unexported_changes)


class DayPageM5Tests(DataDirMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.build()
        import_curation(Curation.load(COMMITTED))
        reset_caches()

    def test_fragment_and_caching(self) -> None:
        full = self.client.get('/2027-11-21/')
        self.assertContains(full, '<div id="day">')
        fragment = self.client.get('/2027-11-21/?fragment=1')
        self.assertContains(fragment, 'class="day-view"')
        self.assertNotContains(fragment, '<html')
        self.assertIn('Cookie', fragment['Vary'])
        again = self.client.get('/2027-11-21/?fragment=1', HTTP_IF_NONE_MATCH=fragment['ETag'])
        self.assertEqual(again.status_code, 304)

    def test_saturday_and_christmas_eve_show_the_evening_mass(self) -> None:
        saturday = self.client.get('/2027-11-27/')
        self.assertContains(saturday, 'Večerní mše z neděle')
        self.assertContains(saturday, '1. neděle adventní')
        eve = self.client.get('/2027-12-24/')
        self.assertContains(eve, 'Večerní mše z vigilie Narození Páně')
        self.assertNotContains(self.client.get('/2027-11-26/'), 'Večerní mše')

    def test_no_acclamation_badge_and_sources_markup(self) -> None:
        response = self.client.get('/2027-11-21/')
        self.assertNotContains(response, 'Před evangeliem: Aleluja')
        self.assertContains(response, 'class="source">Direktář s. 26')
        self.assertContains(response, 'id="zdroje"')

    def test_json_api(self) -> None:
        response = self.client.get('/api/v1/days/2027-11-21.json?dieceze=czech')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual((data['date'], data['diocese'], data['season']), ('2027-11-21', 'czech', 'ordinary'))
        mass = data['masses'][0]
        self.assertEqual(mass['summary'][0]['items'][0]['songs'][0]['code'], '707')
        self.assertTrue(mass['plan'])
        self.assertEqual(self.client.get('/api/v1/days/2027-11-21.json?dieceze=xx').status_code, 400)
        self.assertEqual(self.client.get('/api/v1/days/2031-01-01.json').status_code, 404)


class OccasionPageTests(DataDirMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.build()
        import_curation(Curation.load(COMMITTED))
        reset_caches()

    def test_list(self) -> None:
        response = self.client.get('/prilezitosti/')
        self.assertContains(response, 'href="/prilezitosti/pohreb/"')
        self.assertContains(response, 'Vyberte příležitost')

    def test_funeral(self) -> None:  # Direktář p. 48
        response = self.client.get('/prilezitosti/pohreb/')
        self.assertContains(response, '921:')
        self.assertContains(response, 'při obřadu')
        self.assertContains(response, 'Direktář s. 48')

    def test_unknown_occasion(self) -> None:
        self.assertEqual(self.client.get('/prilezitosti/neco/').status_code, 404)

    def test_occasion_rules_never_reach_days(self) -> None:
        response = self.client.get('/2027-11-21/')
        self.assertNotContains(response, '921:')


class RuleAdminTests(DataDirMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.build()
        import_curation(Curation.load(COMMITTED))
        reset_caches()
        user = get_user_model().objects.create_superuser('admin', 'a@example.com', 'pw')
        self.client.force_login(user)

    def _form(self, **overrides: str) -> dict:
        data = {
            'celebration': '', 'category': '', 'period': '', 'season': 'ordinary', 'occasion': '',
            'day': '', 'min_rank': '',
            'parts': ['mass'], 'kind': 'songs', 'strength': 'recommended', 'songs': '523, 838/5, @mesni_obecne',
            'window_days': '7', 'note': '', 'internal': '', 'page': '', 'position': '5000', 'active': 'on',
        }
        data.update(overrides)
        return data

    def test_pages_load(self) -> None:
        rule = Rule.objects.get(celebration='jezise-krista-krale', parts='mass')
        for url in ('/admin/rules/rule/', '/admin/rules/rule/?kind=silence', f'/admin/rules/rule/{rule.pk}/change/',
                    '/admin/rules/rule/add/'):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        if date.today() + timedelta(days=400) >= date(2027, 11, 21) >= date.today():  # preview window of fixtures
            self.assertContains(self.client.get(f'/admin/rules/rule/{rule.pk}/change/'), '21. 11. 2027')

    def test_add_valid_rule(self) -> None:
        count = Rule.objects.count()
        response = self.client.post('/admin/rules/rule/add/', self._form())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Rule.objects.count(), count + 1)
        rule = Rule.objects.order_by('-pk').first()
        self.assertEqual((rule.parts, rule.songs, rule.cycles), ('mass', '523, 838/5, @mesni_obecne', ''))

    def test_add_occasion_rule(self) -> None:
        response = self.client.post('/admin/rules/rule/add/', self._form(season='', occasion='svatba', songs='904'))
        self.assertEqual(response.status_code, 302)
        rule = Rule.objects.order_by('-pk').first()
        self.assertEqual(rule.occasion, 'svatba')
        reset_caches()
        self.assertContains(self.client.get('/prilezitosti/svatba/'), '904:')
        self.assertEqual(self.client.get(f'/admin/rules/rule/{rule.pk}/change/').status_code, 200)

    def test_invalid_rules_are_rejected(self) -> None:
        for overrides in ({'songs': '999'}, {'songs': '82'}, {'songs': '@no_group'}, {'parts': []},
                          {'celebration': 'no-such-day'}, {'kind': 'note', 'songs': '', 'note': ''}):
            with self.subTest(overrides=overrides):
                response = self.client.post('/admin/rules/rule/add/', self._form(**overrides))
                self.assertEqual(response.status_code, 200)  # form redisplayed with errors


class LintCommandTests(TestCase):
    def test_lint_committed_file(self) -> None:
        out = StringIO()
        call_command('rules_lint', '--file', '--coverage', stdout=out, stderr=StringIO())
        self.assertIn('OK:', out.getvalue())
        self.assertIn('without a ▲/■ mass song', out.getvalue())
