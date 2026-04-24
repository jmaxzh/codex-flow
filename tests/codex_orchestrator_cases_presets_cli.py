import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.codex_orchestrator_test_support import module


class CliHelperTests(unittest.TestCase):
    def test_parse_context_overrides_last_value_wins(self):
        overrides = module.parse_context_overrides([["spec", "v1"], ["spec", "v2"], ["user_instruction", "do it"]])
        self.assertEqual(overrides["spec"], "v2")
        self.assertEqual(overrides["user_instruction"], "do it")

    def test_parse_context_overrides_rejects_nested_key(self):
        with self.assertRaisesRegex(RuntimeError, "cannot contain"):
            module.parse_context_overrides([["a.b", "x"]])

    def test_resolve_main_config_validates_preset(self):
        preset_id, overrides = module.resolve_main_config("openspec_implement", [["spec", "s"]])
        self.assertEqual(preset_id, "openspec_implement")
        self.assertEqual(overrides, {"spec": "s"})

    def test_resolve_main_config_rejects_unknown_preset_with_available_list(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "Unknown preset identifier: 'missing'.*Available built-in presets: "
            "doc_reviewer_loop, openspec_implement, openspec_propose, refactor_loop, reviewer_loop",
        ):
            module.resolve_main_config("missing", None)

    def test_resolve_main_config_rejects_legacy_preset_identifiers(self):
        for legacy_id in ("implement_loop", "doc_doctor"):
            with self.assertRaisesRegex(
                RuntimeError,
                "Unknown preset identifier: '.*'.*Available built-in presets: "
                "doc_reviewer_loop, openspec_implement, openspec_propose, refactor_loop, reviewer_loop",
            ):
                module.resolve_main_config(legacy_id, None)

    def test_validate_preset_identifier_is_cwd_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = Path.cwd()
            cwd_a = Path(tmp) / "a"
            cwd_b = Path(tmp) / "b"
            cwd_a.mkdir(parents=True, exist_ok=True)
            cwd_b.mkdir(parents=True, exist_ok=True)
            try:
                os.chdir(cwd_a)
                a = module.resolve_main_config("openspec_implement", None)[0]
                os.chdir(cwd_b)
                b = module.resolve_main_config("openspec_implement", None)[0]
            finally:
                os.chdir(original_cwd)
        self.assertEqual(a, b)
        self.assertEqual(a, "openspec_implement")

    def test_validate_preset_identifier_rejects_path_like_value(self):
        with self.assertRaisesRegex(RuntimeError, "expects a preset identifier"):
            module.resolve_main_config("presets/openspec_implement.yaml", None)

    def test_validate_preset_identifier_rejects_empty_or_whitespace_value(self):
        with self.assertRaisesRegex(RuntimeError, "non-empty preset identifier"):
            module.resolve_main_config("   ", None)

    def test_validate_preset_identifier_rejects_yaml_suffix_with_migration_hint(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "Use 'openspec_implement' instead of 'openspec_implement.yaml'",
        ):
            module.resolve_main_config("openspec_implement.yaml", None)


class MainCliContractTests(unittest.TestCase):
    def test_main_dependency_error_uses_unified_stderr_path(self):
        args = type("Args", (), {"preset": "openspec_implement", "context": None})()
        with patch.object(module, "parse_args", return_value=args):
            with patch.object(module, "PREFECT_IMPORT_ERROR", RuntimeError("prefect missing")):
                with patch("sys.stderr") as fake_stderr:
                    exit_code = module.main()
        self.assertEqual(exit_code, 2)
        written = "".join(call.args[0] for call in fake_stderr.write.call_args_list)
        self.assertIn("Missing dependency: prefect (prefect missing)", written)

    def test_main_dispatches_registry_runner_and_merges_context_overrides(self):
        args = type(
            "Args",
            (),
            {
                "preset": "openspec_implement",
                "context": [["spec", "s1"], ["spec", "s2"], ["user_instruction", "u2"]],
            },
        )()

        captured: dict[str, Any] = {}

        def fake_runner(context_overrides: dict[str, str], launch_cwd: str) -> dict[str, Any]:
            captured["context_overrides"] = dict(context_overrides)
            captured["launch_cwd"] = launch_cwd
            return {
                "status": "completed",
                "run_id": "run__fake",
                "run_state_dir": "/tmp/run__fake",
                "final_node": "END",
                "steps_executed": 1,
                "outputs": {},
            }

        def fake_run_workflow(preset: str, overrides: dict[str, str], launch: str) -> dict[str, Any]:
            return module.get_flow_runner(preset)(overrides, launch)

        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = Path.cwd()
            try:
                os.chdir(tmp)
                with patch.object(module, "parse_args", return_value=args):
                    with patch.object(module, "format_missing_dependency_error", return_value=None):
                        with patch.object(module, "get_flow_runner", return_value=fake_runner) as get_runner_mock:
                            with patch.object(module, "run_workflow", side_effect=fake_run_workflow):
                                exit_code = module.main()
            finally:
                os.chdir(original_cwd)

        self.assertEqual(exit_code, 0)
        get_runner_mock.assert_called_once_with("openspec_implement")
        self.assertEqual(captured["context_overrides"], {"spec": "s2", "user_instruction": "u2"})
        self.assertEqual(captured["launch_cwd"], str(Path(tmp).resolve()))
