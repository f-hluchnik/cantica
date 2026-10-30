"""Django integration tests: curated data import/export, version guard, admin pages."""
import tempfile
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from catalog.curation import Curation, GroupRecord, SongRecord
from catalog.dbsync import export_curation, import_curation
from catalog.models import CurationState, Song, SongGroup, SongGroupMember

COMMITTED = Path(__file__).resolve().parents[2] / 'data' / 'curated' / 'curation.yaml'


def _small() -> Curation:
    return Curation(
        version=1,
        songs=[
            SongRecord('523', 'Ty jsi, Pane, v každém chrámě', 'mass_general', communion_verses='*'),
            SongRecord('813A', 'Velebí má duše Hospodina', 'mary_saints'),
            SongRecord('813B', 'Velebí má duše s jásotem', 'mary_saints'),
            SongRecord('Z781', 'Pojď k Spasiteli', 'jesus', recessional_verses='4,5', verse_count=6),
        ],
        groups=[GroupRecord('test_group', 'Testovací', ['813B', '523'], source_page=25)],
    )


class ImportExportTests(TestCase):
    def test_import_into_empty_db_and_export_roundtrip(self) -> None:
        curation = _small()
        self.assertEqual(import_curation(curation), 'imported')
        self.assertEqual(Song.objects.count(), 4)
        song = Song.objects.get(code='Z781')
        self.assertEqual((song.number, song.recessional_verses), ('Z781', '4,5'))
        self.assertEqual(Song.objects.get(code='813B').number, '813')
        self.assertEqual(
            list(SongGroupMember.objects.filter(group_id='test_group').values_list('song_id', flat=True)),
            ['813B', '523'],  # order kept
        )
        state = CurationState.current()
        self.assertEqual((state.version, state.exported_version), (1, 1))
        self.assertEqual(export_curation().dumps(), curation.dumps())  # identical file, no spurious diff

    def test_reimport_of_same_content_is_a_noop(self) -> None:
        import_curation(_small())
        self.assertEqual(import_curation(_small()), 'unchanged')
        self.assertEqual(CurationState.current().version, 1)

    def test_admin_change_bumps_version_and_blocks_import(self) -> None:
        import_curation(_small())
        song = Song.objects.get(code='523')
        song.mass_song = True
        song.save()
        state = CurationState.current()
        self.assertEqual(state.version, 2)
        self.assertTrue(state.has_unexported_changes)
        changed = _small()
        changed.songs[1].title = 'Jiný název'
        with self.assertRaises(Exception) as ctx:
            import_curation(changed)
        self.assertIn('never exported', str(ctx.exception))
        self.assertEqual(import_curation(changed, force=True), 'imported')
        self.assertEqual(Song.objects.get(code='813A').title, 'Jiný název')
        self.assertIsNone(Song.objects.get(code='523').mass_song)  # forced import discarded the edit

    def test_export_then_import_is_allowed(self) -> None:
        import_curation(_small())
        song = Song.objects.get(code='523')
        song.note = 'x'
        song.save()
        export_curation()
        changed = _small()
        changed.songs.pop()  # drop Z781
        changed.groups[0].members = ['523']
        self.assertEqual(import_curation(changed), 'imported')
        self.assertFalse(Song.objects.filter(code='Z781').exists())
        self.assertEqual(SongGroupMember.objects.count(), 1)

    def test_validators(self) -> None:
        Song(code='999', title='x', section='mass_general', communion_verses='4,5', verse_count=6).full_clean()
        cases = (
            ({'code': '999', 'communion_verses': '4,x'}, 'communion_verses'),
            ({'code': '999', 'recessional_verses': '7', 'verse_count': 6}, 'recessional_verses'),
            ({'code': '52'}, 'code'),
        )
        for fields, bad_field in cases:
            song = Song(title='x', section='mass_general', **fields)
            with self.subTest(fields=fields), self.assertRaises(ValidationError) as ctx:
                song.full_clean()
            self.assertEqual(list(ctx.exception.message_dict), [bad_field])


class CommandTests(TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / 'curation.yaml'
        _small().save(self.path)
        self._settings = override_settings(CANTICA_CURATION_FILE=self.path)
        self._settings.enable()

    def tearDown(self) -> None:
        self._settings.disable()
        self._tmp.cleanup()

    def test_import_if_empty_then_export(self) -> None:
        call_command('curation_import', '--if-empty', stdout=StringIO())
        self.assertEqual(Song.objects.count(), 4)
        Song.objects.filter(code='523').update(title='changed directly')  # no signal: still "exported"
        out = StringIO()
        call_command('curation_import', '--if-empty', stdout=out)
        self.assertIn('nothing to do', out.getvalue())
        call_command('curation_export', stdout=StringIO())
        self.assertIn('changed directly', self.path.read_text(encoding='utf-8'))

    def test_export_print(self) -> None:
        call_command('curation_import', stdout=StringIO())
        out = StringIO()
        call_command('curation_export', '--print', stdout=out)
        self.assertEqual(Curation.loads(out.getvalue()).dumps(), _small().dumps())

    def test_export_without_mark_then_mark(self) -> None:
        call_command('curation_import', stdout=StringIO())
        song = Song.objects.get(code='523')
        song.note = 'edited'
        song.save()  # version 2, unexported
        call_command('curation_export', '--print', '--no-mark', stdout=StringIO())
        self.assertTrue(CurationState.current().has_unexported_changes)
        call_command('curation_export', '--mark-exported', '2', stdout=StringIO())
        self.assertFalse(CurationState.current().has_unexported_changes)
        with self.assertRaises(CommandError):
            call_command('curation_export', '--mark-exported', '99', stdout=StringIO())

    def test_group_inline_appends_new_members(self) -> None:
        call_command('curation_import', stdout=StringIO())
        user = get_user_model().objects.create_superuser('admin', 'a@example.com', 'pw')
        self.client.force_login(user)
        existing = list(SongGroupMember.objects.filter(group_id='test_group').order_by('position'))
        data = {
            'name': 'Testovací',
            'description': '',
            'source_page': '25',
            'memberships-TOTAL_FORMS': '3',
            'memberships-INITIAL_FORMS': '2',
            'memberships-MIN_NUM_FORMS': '0',
            'memberships-MAX_NUM_FORMS': '1000',
        }
        for i, member in enumerate(existing):
            data.update({
                f'memberships-{i}-id': str(member.pk),
                f'memberships-{i}-group': 'test_group',
                f'memberships-{i}-song': member.song_id,
                f'memberships-{i}-position': str(member.position),
            })
        data.update({'memberships-2-group': 'test_group', 'memberships-2-song': 'Z781', 'memberships-2-position': '0'})
        response = self.client.post('/admin/catalog/songgroup/test_group/change/', data)
        self.assertEqual(response.status_code, 302)
        order = list(SongGroupMember.objects.filter(group_id='test_group').order_by('position').values_list('song_id', flat=True))
        self.assertEqual(order, ['813B', '523', 'Z781'])

    def test_missing_or_invalid_file(self) -> None:
        with self.assertRaises(CommandError):
            call_command('curation_import', '--path', str(self.path.with_name('missing.yaml')), stdout=StringIO())
        self.path.write_text('songs: [{code: "1", title: x, section: nowhere}]', encoding='utf-8')
        with self.assertRaises(CommandError):
            call_command('curation_import', stdout=StringIO())


class CommittedDataImportTests(TestCase):
    def test_committed_file_imports_and_exports_identically(self) -> None:
        curation = Curation.load(COMMITTED)
        import_curation(curation)
        self.assertGreater(Song.objects.count(), 500)
        self.assertTrue(SongGroup.objects.filter(key='mesni_obecne').exists())
        self.assertEqual(export_curation().dumps(), COMMITTED.read_text(encoding='utf-8'))


class AdminPagesTests(TestCase):
    def setUp(self) -> None:
        import_curation(_small())
        user = get_user_model().objects.create_superuser('admin', 'a@example.com', 'pw')
        self.client.force_login(user)

    def test_pages_load(self) -> None:
        for url in (
            '/admin/catalog/song/',
            '/admin/catalog/song/?prijimani=unknown',
            '/admin/catalog/song/?zaver=specific',
            '/admin/catalog/song/523/change/',
            '/admin/catalog/songgroup/',
            '/admin/catalog/songgroup/test_group/change/',
            '/admin/catalog/curationstate/',
            '/admin/liturgy/celebration/',
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_verse_filter(self) -> None:
        response = self.client.get('/admin/catalog/song/?zaver=specific')
        self.assertContains(response, 'Pojď k Spasiteli')
        self.assertNotContains(response, 'Velebí má duše s jásotem')
