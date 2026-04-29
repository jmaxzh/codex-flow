import importlib
import unittest
from typing import Any, cast

from tests.codex_orchestrator_module_loader import get_cli_module, module


class PublicApiContractTests(unittest.TestCase):
    def test_native_api_exports_expected_public_symbols(self):
        expected = {
            "apply_route_bindings",
            "build_prompt_inputs",
            "build_step_prefix",
            "ensure_history_list",
            "extract_last_non_empty_line",
            "get_flow_runner",
            "list_builtin_preset_identifiers",
            "make_codex_log_path",
            "parse_and_validate_output",
            "render_prompt",
            "resolve_next_node",
            "resolve_node_output",
            "run_codex_exec",
            "run_workflow",
            "validate_stages",
        }

        self.assertTrue(hasattr(module, "__all__"))
        exported = set(module.__all__)
        self.assertEqual(exported, expected)

    def test_native_api_exports_callable_entrypoints(self):
        callable_names = (
            "run_workflow",
            "build_prompt_inputs",
            "render_prompt",
            "parse_and_validate_output",
        )
        for name in callable_names:
            self.assertTrue(callable(getattr(module, name)))

    def test_removed_entrypoints_module_not_importable(self):
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("_codex_orchestrator.native_workflows.entrypoints")

    def test_cli_package_exports_expected_public_symbols(self):
        cli_module = cast(Any, get_cli_module())
        expected = {
            "fail_with_stderr",
            "parse_args",
            "parse_context_overrides",
            "parse_max_steps_override",
            "resolve_main_config",
            "run_cli_main",
            "run_workflow",
            "run_workflow_with_options",
            "split_context_overrides_and_max_steps_override",
        }
        self.assertTrue(hasattr(cli_module, "__all__"))
        self.assertEqual(set(cli_module.__all__), expected)
