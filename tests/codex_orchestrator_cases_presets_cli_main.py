import os
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from tests.codex_orchestrator_module_loader import get_cli_module


@dataclass
class _Args:
    preset: str
    context: list[list[str]] | None


class MainCliContractTests(unittest.TestCase):
    def test_main_errors_are_written_to_stderr_via_unified_path(self):
        cli_module = cast(Any, get_cli_module())
        run_cli = cli_module.run_cli_main
        args = _Args(preset="openspec_implement", context=None)

        def _resolve_main_config(_preset: str, _context: list[list[str]] | None) -> tuple[str, dict[str, str]]:
            return "openspec_implement", {}

        def _run_workflow(_preset: str, _overrides: dict[str, str], _launch: str) -> dict[str, Any]:
            return {}

        def _fail_with_stderr(message: str) -> int:
            print(message, file=sys.stderr)
            return 2

        cli_main_module = __import__("importlib").import_module("_codex_orchestrator.orchestrator_cli.main")
        with patch.object(cli_main_module.Path, "cwd", side_effect=RuntimeError("cwd error")):
            with patch("sys.stderr") as fake_stderr:
                exit_code = run_cli(
                    parse_args_func=lambda: args,
                    resolve_main_config_func=_resolve_main_config,
                    run_workflow_func=_run_workflow,
                    fail_with_stderr_func=_fail_with_stderr,
                )
        self.assertEqual(exit_code, 2)
        written = "".join(call.args[0] for call in fake_stderr.write.call_args_list)
        self.assertIn("cwd error", written)

    def test_main_dispatches_registry_runner_and_merges_context_overrides(self):
        cli_module = cast(Any, get_cli_module())
        run_cli = cli_module.run_cli_main
        args = _Args(
            preset="openspec_implement",
            context=[["spec", "s1"], ["spec", "s2"], ["user_instruction", "u2"]],
        )

        captured: dict[str, Any] = {}

        def fake_resolve_main_config(preset: str, context_pairs: list[list[str]] | None) -> tuple[str, dict[str, str]]:
            self.assertEqual(preset, "openspec_implement")
            self.assertEqual(context_pairs, args.context)
            return "openspec_implement", {"spec": "s2", "user_instruction": "u2"}

        def fake_run_workflow(preset: str, overrides: dict[str, str], launch: str) -> dict[str, Any]:
            captured["preset"] = preset
            captured["context_overrides"] = dict(overrides)
            captured["launch_cwd"] = launch
            return {
                "status": "completed",
                "run_id": "run__fake",
                "run_state_dir": "/tmp/run__fake",
                "final_node": "END",
                "steps_executed": 1,
                "outputs": {},
            }

        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = Path.cwd()
            try:
                os.chdir(tmp)

                def _fail_with_stderr(_message: str) -> int:
                    return 2

                exit_code = run_cli(
                    parse_args_func=lambda: args,
                    resolve_main_config_func=fake_resolve_main_config,
                    run_workflow_func=fake_run_workflow,
                    fail_with_stderr_func=_fail_with_stderr,
                )
            finally:
                os.chdir(original_cwd)

        self.assertEqual(exit_code, 0)
        self.assertEqual(captured["preset"], "openspec_implement")
        self.assertEqual(captured["context_overrides"], {"spec": "s2", "user_instruction": "u2"})
        self.assertEqual(captured["launch_cwd"], str(Path(tmp).resolve()))
