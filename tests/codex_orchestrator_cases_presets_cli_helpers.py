import os
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from tests.codex_orchestrator_module_loader import get_cli_module


class CliHelperTests(unittest.TestCase):
    def test_parse_context_overrides_last_value_wins(self):
        cli_module = cast(Any, get_cli_module())
        overrides = cli_module.parse_context_overrides([["spec", "v1"], ["spec", "v2"], ["user_instruction", "do it"]])
        self.assertEqual(overrides["spec"], "v2")
        self.assertEqual(overrides["user_instruction"], "do it")

    def test_parse_context_overrides_rejects_nested_key(self):
        cli_module = cast(Any, get_cli_module())
        with self.assertRaisesRegex(RuntimeError, "cannot contain"):
            cli_module.parse_context_overrides([["a.b", "x"]])

    def test_resolve_main_config_validates_preset(self):
        cli_module = cast(Any, get_cli_module())
        preset_id, overrides = cli_module.resolve_main_config("openspec_implement", [["spec", "s"]])
        self.assertEqual(preset_id, "openspec_implement")
        self.assertEqual(overrides, {"spec": "s"})

    def test_resolve_main_config_rejects_unknown_preset_with_available_list(self):
        cli_module = cast(Any, get_cli_module())
        with self.assertRaisesRegex(
            RuntimeError,
            "Unknown preset identifier: 'missing'.*Available built-in presets: "
            "bug_review_loop, doc_doctor, doc_review_loop, implement_loop, openspec_implement, openspec_propose, "
            "quality_review_loop",
        ):
            cli_module.resolve_main_config("missing", None)

    def test_resolve_main_config_accepts_legacy_preset_identifiers(self):
        cli_module = cast(Any, get_cli_module())
        for legacy_id in ("implement_loop", "doc_doctor"):
            preset_id, overrides = cli_module.resolve_main_config(legacy_id, None)
            self.assertEqual(preset_id, legacy_id)
            self.assertEqual(overrides, {})

    def test_validate_preset_identifier_is_cwd_independent(self):
        cli_module = cast(Any, get_cli_module())
        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = Path.cwd()
            cwd_a = Path(tmp) / "a"
            cwd_b = Path(tmp) / "b"
            cwd_a.mkdir(parents=True, exist_ok=True)
            cwd_b.mkdir(parents=True, exist_ok=True)
            try:
                os.chdir(cwd_a)
                a = cli_module.resolve_main_config("openspec_implement", None)[0]
                os.chdir(cwd_b)
                b = cli_module.resolve_main_config("openspec_implement", None)[0]
            finally:
                os.chdir(original_cwd)
        self.assertEqual(a, b)
        self.assertEqual(a, "openspec_implement")

    def test_validate_preset_identifier_rejects_path_like_value(self):
        cli_module = cast(Any, get_cli_module())
        with self.assertRaisesRegex(RuntimeError, "expects a preset identifier"):
            cli_module.resolve_main_config("presets/openspec_implement.yaml", None)

    def test_validate_preset_identifier_rejects_empty_or_whitespace_value(self):
        cli_module = cast(Any, get_cli_module())
        with self.assertRaisesRegex(RuntimeError, "non-empty preset identifier"):
            cli_module.resolve_main_config("   ", None)

    def test_validate_preset_identifier_rejects_yaml_suffix_with_migration_hint(self):
        cli_module = cast(Any, get_cli_module())
        with self.assertRaisesRegex(
            RuntimeError,
            "Use 'openspec_implement' instead of 'openspec_implement.yaml'",
        ):
            cli_module.resolve_main_config("openspec_implement.yaml", None)

    def test_run_workflow_extracts_max_steps_override(self):
        cli_module = cast(Any, get_cli_module())
        runtime_dispatch_module = __import__("importlib").import_module("_codex_orchestrator.orchestrator_cli.runtime_dispatch")
        captured: dict[str, Any] = {}

        def fake_run_workflow_with_options(
            *,
            preset_id: str,
            context_overrides: dict[str, str],
            launch_cwd: str | None = None,
            max_steps_override: int | None = None,
        ) -> dict[str, Any]:
            captured["preset_id"] = preset_id
            captured["context_overrides"] = context_overrides
            captured["launch_cwd"] = launch_cwd
            captured["max_steps_override"] = max_steps_override
            return {"run_state_dir": "/tmp/run_state_dir"}

        with patch.object(runtime_dispatch_module, "_run_workflow_with_options", side_effect=fake_run_workflow_with_options):
            summary = cli_module.run_workflow(
                "openspec_implement",
                {
                    "spec": "docs/new-spec.md",
                    "__max_steps": "7",
                },
                "/tmp/launch",
            )

        self.assertEqual(summary["run_state_dir"], "/tmp/run_state_dir")
        self.assertEqual(captured["preset_id"], "openspec_implement")
        self.assertEqual(captured["context_overrides"], {"spec": "docs/new-spec.md"})
        self.assertEqual(captured["launch_cwd"], "/tmp/launch")
        self.assertEqual(captured["max_steps_override"], 7)
