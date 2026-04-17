import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests import (
    codex_orchestrator_cases_config as cases_config,
)
from tests import (
    codex_orchestrator_cases_core as cases_core,
)
from tests import (
    codex_orchestrator_cases_presets_cli as cases_presets_cli,
)
from tests import (
    codex_orchestrator_cases_prompt as cases_prompt,
)
from tests import (
    codex_orchestrator_cases_runtime as cases_runtime,
)

CASE_MODULES = (
    cases_config,
    cases_core,
    cases_prompt,
    cases_runtime,
    cases_presets_cli,
)


def _iter_case_classes():
    for case_module in CASE_MODULES:
        for _, case_class in inspect.getmembers(case_module, inspect.isclass):
            if not issubclass(case_class, unittest.TestCase):
                continue
            if case_class is unittest.TestCase:
                continue
            # Keep only classes defined in the case module itself.
            if case_class.__module__ != case_module.__name__:
                continue
            yield case_module, case_class


def _export_case_classes_for_pytest():
    for case_module, case_class in _iter_case_classes():
        export_name = case_class.__name__
        if export_name in globals():
            module_suffix = case_module.__name__.split("codex_orchestrator_cases_", 1)[-1]
            export_name = f"{module_suffix}_{export_name}"

        exported_case = type(export_name, (case_class,), {})
        exported_case.__module__ = __name__
        globals()[export_name] = exported_case


_export_case_classes_for_pytest()


def load_tests(loader: unittest.TestLoader, tests: unittest.TestSuite, pattern: str | None):
    suite = unittest.TestSuite()
    # Case classes are re-exported in this module for pytest discovery.
    # Ignore preloaded tests here to avoid duplicate execution in unittest flows.
    for case_module in CASE_MODULES:
        suite.addTests(loader.loadTestsFromModule(case_module, pattern=pattern))
    return suite


if __name__ == "__main__":
    unittest.main()
