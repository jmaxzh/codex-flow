import importlib
import inspect
import pkgutil
import types
import unittest
from collections.abc import Iterator, Mapping, MutableMapping

CASE_MODULE_PREFIX = "codex_orchestrator_cases_"
EXCLUDED_CASE_MODULES = {"codex_orchestrator_cases_runtime"}
REQUIRED_RUNTIME_MODULES = {
    "codex_orchestrator_cases_runtime_bindings",
    "codex_orchestrator_cases_runtime_flow_control",
    "codex_orchestrator_cases_runtime_history",
    "codex_orchestrator_cases_runtime_markers",
}


def iter_module_local_test_cases(case_module: types.ModuleType) -> Iterator[type[unittest.TestCase]]:
    for _, case_class in inspect.getmembers(case_module, inspect.isclass):
        if not issubclass(case_class, unittest.TestCase):
            continue
        if case_class is unittest.TestCase:
            continue
        # Keep only classes defined in the case module itself.
        if case_class.__module__ != case_module.__name__:
            continue
        yield case_class


def discover_case_modules() -> tuple[types.ModuleType, ...]:
    tests_package = importlib.import_module("tests")
    candidate_names = sorted(
        name
        for _, name, is_pkg in pkgutil.iter_modules(tests_package.__path__)
        if not is_pkg and name.startswith(CASE_MODULE_PREFIX)
    )

    discovered_modules: list[types.ModuleType] = []
    for module_name in candidate_names:
        if module_name in EXCLUDED_CASE_MODULES:
            continue
        case_module = importlib.import_module(f"tests.{module_name}")
        if tuple(iter_module_local_test_cases(case_module)):
            discovered_modules.append(case_module)
    return tuple(discovered_modules)


CASE_MODULES = discover_case_modules()
CASE_MODULE_NAMES = {case_module.__name__.split(".")[-1] for case_module in CASE_MODULES}


def iter_case_classes() -> Iterator[tuple[types.ModuleType, type[unittest.TestCase]]]:
    for case_module in CASE_MODULES:
        for case_class in iter_module_local_test_cases(case_module):
            yield case_module, case_class


def export_case_classes_for_pytest(
    target_globals: MutableMapping[str, object],
    target_module_name: str,
    existing_globals: Mapping[str, object] | None = None,
) -> None:
    existing_names = set((existing_globals or target_globals).keys())
    for case_module, case_class in iter_case_classes():
        export_name = case_class.__name__
        if export_name in existing_names:
            module_suffix = case_module.__name__.split("codex_orchestrator_cases_", 1)[-1]
            export_name = f"{module_suffix}_{export_name}"

        exported_case = type(export_name, (case_class,), {})
        exported_case.__module__ = target_module_name
        target_globals[export_name] = exported_case
        existing_names.add(export_name)
