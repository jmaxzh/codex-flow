import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from tests.codex_orchestrator_fake_exec import make_fake_codex_exec
from tests.codex_orchestrator_module_loader import run_workflow_direct
from tests.codex_orchestrator_runtime_patch import patch_native_exec


class PromptPathResolutionWorkflowTests(unittest.TestCase):
    def _run_with_include(self, launch_cwd: Path, captured_prompts: list[str]) -> None:
        call_counter = {"check": 0}

        def raw_output_for_call(*, node_id: str, **_kwargs: Any) -> str:
            if node_id == "openspec_implement_first":
                return "implemented"
            if node_id == "openspec_implement_review":
                call_counter["check"] += 1
                if call_counter["check"] == 1:
                    return '{"pass": true}'
                return '{"pass": false}'
            return '{"pass": true}'

        fake_exec = make_fake_codex_exec(
            raw_output_for_call=cast(Callable[..., str], raw_output_for_call),
            captured_prompts=captured_prompts,
        )
        with patch_native_exec(fake_exec):
            run_workflow_direct("openspec_implement", {"spec": "x", "user_instruction": "u"}, str(launch_cwd))

    def test_include_resolution_is_consistent_across_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd_a = root / "cwd_a"
            cwd_b = root / "cwd_b"
            cwd_a.mkdir(parents=True, exist_ok=True)
            cwd_b.mkdir(parents=True, exist_ok=True)

            captured_prompts: list[str] = []
            self._run_with_include(cwd_a, captured_prompts)
            self._run_with_include(cwd_b, captured_prompts)

            self.assertEqual(len(captured_prompts), 4)
            self.assertEqual(captured_prompts[0], captured_prompts[2])
            self.assertEqual(captured_prompts[1], captured_prompts[3])

    def test_include_resolution_is_independent_of_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launch_cwd = root / "caller"
            launch_cwd.mkdir(parents=True, exist_ok=True)
            prompts: list[str] = []
            self._run_with_include(launch_cwd, prompts)
            self.assertEqual(len(prompts), 2)
            self.assertIn("使用 openspec apply change 实现 x.", prompts[0])

    def test_openspec_prompt_assets_are_loaded_from_prompt_file(self):
        captured_prompts: list[str] = []

        def raw_output_for_call(*, node_id: str, **_kwargs: Any) -> str:
            if node_id == "openspec_implement_first":
                return "implemented"
            return '{"pass": true}'

        fake_exec = make_fake_codex_exec(
            raw_output_for_call=cast(Callable[..., str], raw_output_for_call),
            captured_prompts=captured_prompts,
        )
        with tempfile.TemporaryDirectory() as tmp:
            with patch_native_exec(fake_exec):
                run_workflow_direct("openspec_implement", {"spec": "x", "user_instruction": "u"}, tmp)

        self.assertGreaterEqual(len(captured_prompts), 2)
        self.assertIn("使用 openspec apply change 实现 x.", captured_prompts[0])
        self.assertIn("若全部完成，pass=true", captured_prompts[1])
