"""Pure modules must stay importable and testable without Django (design §4)."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PURE_MODULES = (
    'catalog/codes.py',
    'catalog/curation.py',
    'liturgy/calapi.py',
    'liturgy/catalog.py',
    'liturgy/constants.py',
    'liturgy/days.py',
    'liturgy/keys.py',
    'liturgy/norms.py',
    'liturgy/snapshot.py',
    'liturgy/sync.py',
)
FORBIDDEN = (
    'django',
    'liturgy.models', 'liturgy.dbbuild', 'liturgy.services',
    'catalog.models', 'catalog.admin', 'catalog.dbsync', 'catalog.signals',
    'web',
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class PurityTests(unittest.TestCase):
    def test_pure_modules_do_not_import_django(self) -> None:
        for relative in PURE_MODULES:
            for name in _imports(ROOT / relative):
                with self.subTest(module=relative, imports=name):
                    self.assertFalse(
                        any(name == f or name.startswith(f + '.') for f in FORBIDDEN),
                        f'{relative} imports {name}',
                    )


if __name__ == '__main__':
    unittest.main()
