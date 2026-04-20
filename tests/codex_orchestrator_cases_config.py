import unittest
from typing import Any

from tests.codex_orchestrator_test_support import module


class NativeRegistryTests(unittest.TestCase):
    def test_registry_contains_all_builtin_presets(self):
        self.assertEqual(
            set(module.list_builtin_preset_identifiers()),
            {"implement_loop", "refactor_loop", "reviewer_loop", "doc_reviewer_loop", "doc_doctor"},
        )

    def test_registry_identifier_list_is_sorted(self):
        self.assertEqual(
            module.list_builtin_preset_identifiers(),
            ["doc_doctor", "doc_reviewer_loop", "implement_loop", "refactor_loop", "reviewer_loop"],
        )


class NativeFlowValidationTests(unittest.TestCase):
    def test_validate_stages_rejects_missing_start(self):
        with self.assertRaisesRegex(RuntimeError, "workflow.start target not found"):
            module.validate_stages("n1", {})

    def test_validate_stages_rejects_invalid_transition(self):
        nodes: dict[str, dict[str, Any]] = {
            "n1": {
                "id": "n1",
                "prompt": "x",
                "input_map": {},
                "on_success": "missing",
                "on_failure": "END",
                "parse_output_json": True,
                "route_bindings": {"success": {}, "failure": {}},
            }
        }
        with self.assertRaisesRegex(RuntimeError, "invalid on_success"):
            module.validate_stages("n1", nodes)
