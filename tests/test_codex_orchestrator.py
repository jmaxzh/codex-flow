import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

case_discovery = importlib.import_module("tests.codex_orchestrator_case_discovery")


class CaseCollectionHealthTests(unittest.TestCase):
    def test_case_modules_discovery_not_empty(self):
        self.assertTrue(case_discovery.CASE_MODULES, "No case modules discovered")

    def test_case_classes_discovery_not_empty(self):
        self.assertTrue(tuple(case_discovery.iter_case_classes()), "No case classes discovered")

    def test_runtime_split_modules_are_discovered(self):
        missing_modules = sorted(case_discovery.REQUIRED_RUNTIME_MODULES - case_discovery.CASE_MODULE_NAMES)
        self.assertFalse(missing_modules, f"Missing runtime split modules: {missing_modules}")


case_discovery.export_case_classes_for_pytest(globals(), __name__)


def load_tests(loader: unittest.TestLoader, tests: unittest.TestSuite, pattern: str | None):
    suite = unittest.TestSuite()
    # Case classes are re-exported in this module for pytest discovery.
    # Ignore preloaded tests here to avoid duplicate execution in unittest flows.
    for case_module in case_discovery.CASE_MODULES:
        suite.addTests(loader.loadTestsFromModule(case_module, pattern=pattern))
    return suite


if __name__ == "__main__":
    unittest.main()
