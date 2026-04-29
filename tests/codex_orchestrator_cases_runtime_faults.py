import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from tests.codex_orchestrator_fake_exec import make_fake_codex_exec
from tests.codex_orchestrator_module_loader import run_workflow_direct
from tests.codex_orchestrator_runtime_patch import patch_native_exec


class NativeFlowRuntimeFaultTests(unittest.TestCase):
    def test_openspec_implement_missing_prompt_template_fails_fast(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            import importlib
            from unittest.mock import patch

            native_io = cast(Any, importlib.import_module("_codex_orchestrator.native_workflows.runtime_io"))
            original_read_text = cast(Callable[[Path], str], native_io.read_text)

            def fake_read_text(path: Path) -> str:
                if str(path).endswith("/presets/prompts/openspec_implement_first.md"):
                    raise FileNotFoundError(path)
                return original_read_text(path)

            with patch.object(native_io, "read_text", side_effect=fake_read_text):
                with self.assertRaisesRegex(
                    RuntimeError,
                    r"prompt_file\(path\) file not found: ./openspec_implement_first.md",
                ):
                    run_workflow_direct("openspec_implement", {}, str(tmp_path))

    def test_max_steps_hard_termination(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            def raw_output_for_call(**_kwargs: Any) -> str:
                return '{"pass": false}'

            fake_exec = make_fake_codex_exec(raw_output_for_call=cast(Callable[..., str], raw_output_for_call))
            overrides = {"__max_steps": "2"}
            with patch_native_exec(fake_exec), self.assertRaisesRegex(RuntimeError, "Reached max_steps without END: 2"):
                run_workflow_direct("bug_review_loop", overrides, str(tmp_path))
