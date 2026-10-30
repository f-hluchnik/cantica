import tempfile
import unittest
from pathlib import Path

from liturgy.catalog import Catalog, CatalogError, Entry
from liturgy.keys import MAX_KEY_LENGTH, key_from_title, slugify_cs, title_similarity


class KeysTests(unittest.TestCase):
    def test_slugify(self) -> None:
        self.assertEqual(slugify_cs('Sv. Cyrila, mnicha, a Metoděje'), 'sv-cyrila-mnicha-a-metodeje')
        self.assertEqual(slugify_cs('Úterý 17. týdne v mezidobí'), 'utery-17-tydne-v-mezidobi')
        self.assertEqual(slugify_cs('Sv. Marie Magdalény de \'Pazzi, panny'), 'sv-marie-magdaleny-de-pazzi-panny')
        self.assertEqual(slugify_cs('Sv. Šarbela Makhlūfa, kněze'), 'sv-sarbela-makhlufa-kneze')

    def test_case_and_punctuation_do_not_matter(self) -> None:
        self.assertEqual(slugify_cs('sv. Hilaria, biskupa'), slugify_cs('Sv. Hilaria, biskupa'))
        self.assertEqual(
            slugify_cs('Sv. Augustina Čao Žung, kněze, a druhů, mučedníků.'),
            slugify_cs('Sv. Augustina Čao Žung, kněze, a druhů, mučedníků'),
        )

    def test_long_key_is_cut_at_word_boundary(self) -> None:
        key = key_from_title('Sv. ' + 'Velmi dlouhého jména ' * 10)
        self.assertLessEqual(len(key), MAX_KEY_LENGTH)
        self.assertFalse(key.endswith('-'))

    def test_similarity(self) -> None:
        self.assertGreater(
            title_similarity('Sv. Cyrila, mnicha, a Metoděje, biskupa, patronů Evropy',
                             'Sv. Cyrila, mnicha, a Metoděje, biskupa, patronů Evropy, hlavních patronů Moravy'),
            0.6,
        )
        self.assertLess(title_similarity('Sv. Marty', 'Sv. Ignáce z Loyoly, kněze'), 0.2)


class CatalogTests(unittest.TestCase):
    def test_register_and_resolve(self) -> None:
        catalog = Catalog()
        entry = catalog.register('Sv. Gorazda a druhů')
        self.assertEqual(entry.key, 'sv-gorazda-a-druhu')
        self.assertEqual(catalog.resolve('sv. gorazda a druhů'), entry.key)
        with self.assertRaises(CatalogError):
            catalog.register('SV. GORAZDA A DRUHŮ')

    def test_alias_resolves_to_entry(self) -> None:
        catalog = Catalog([Entry(key='cyril-metodej', name='Sv. Cyrila a Metoděje', aliases=['Cyril a Metoděj'])])
        self.assertEqual(catalog.resolve('cyril a metoděj'), 'cyril-metodej')

    def test_conflicting_titles_are_rejected(self) -> None:
        with self.assertRaises(CatalogError):
            Catalog([Entry(key='a', name='Sv. Marty'), Entry(key='b', name='X', aliases=['sv. marty'])])

    def test_invalid_key_and_category(self) -> None:
        with self.assertRaises(CatalogError):
            Catalog([Entry(key='Bad Key', name='X')])
        with self.assertRaises(CatalogError):
            Catalog([Entry(key='x', name='X', categories=['nonsense'])])

    def test_key_collision_gets_suffix(self) -> None:
        catalog = Catalog([Entry(key='sv-marty', name='Něco jiného')])
        self.assertEqual(catalog.register('Sv. Marty').key, 'sv-marty-2')

    def test_yaml_roundtrip_is_stable(self) -> None:
        catalog = Catalog([
            Entry(key='sv-marty', name='Sv. Marty', categories=['saint'], categories_reviewed=True),
            Entry(key='cyril-metodej', name='Sv. Cyrila a Metoděje', aliases=['Cyril a Metoděj']),
        ])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'celebrations.yaml'
            self.assertTrue(catalog.save(path))
            self.assertFalse(catalog.save(path))  # unchanged
            loaded = Catalog.load(path)
            self.assertEqual(loaded.dumps(), catalog.dumps())
            self.assertIn('Metoděje', path.read_text(encoding='utf-8'))  # unicode kept readable
            self.assertEqual(loaded.entries['sv-marty'].categories, ['saint'])

    def test_missing_file_is_empty_catalog(self) -> None:
        self.assertEqual(len(Catalog.load(Path('/nonexistent/celebrations.yaml'))), 0)

    def test_duplicate_hints(self) -> None:
        catalog = Catalog([Entry(key='cyril-metodej', name='Sv. Cyrila, mnicha, a Metoděje, biskupa, patronů Evropy')])
        new = catalog.register('Sv. Cyrila, mnicha, a Metoděje, biskupa, patronů Evropy, hlavních patronů Moravy')
        hints = catalog.duplicate_hints(new)
        self.assertEqual([h.existing_key for h in hints], ['cyril-metodej'])


if __name__ == '__main__':
    unittest.main()
