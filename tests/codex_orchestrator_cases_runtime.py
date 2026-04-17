import json
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from tests.codex_orchestrator_test_support import (
    TEST_CONFIG_RELATIVE_PATH,
    PatchedYamlMixin,
    WorkflowTestFactoryMixin,
    module,
)


class RouteBindingRuntimeTests(PatchedYamlMixin, WorkflowTestFactoryMixin, unittest.TestCase):
    def _run_workflow_with_fake_exec(
        self,
        config_path: Path,
        *,
        payload_for_call: Any = None,
        raw_output_for_call: Any = None,
        captured_prompts: list[str] | None = None,
        expect_error: str | None = None,
    ) -> dict[str, Any] | None:
        fake_exec = self.make_fake_codex_exec(
            payload_for_call,
            raw_output_for_call=raw_output_for_call,
            captured_prompts=captured_prompts,
        )
        with self.patch_yaml(), patch.object(module, "run_codex_exec", side_effect=fake_exec):
            if expect_error is None:
                return module.run_workflow(str(config_path), {})
            with self.assertRaisesRegex(RuntimeError, expect_error):
                module.run_workflow(str(config_path), {})
            return None

    def test_run_workflow_applies_route_bindings_and_keeps_outputs_by_node_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = self.write_workflow_config(
                tmp_path,
                run_args={"project_root": tmp_path, "max_steps": 6},
                defaults={"user_instruction": "first pass", "spec": "s"},
                start="implement_first",
                nodes=[
                    {
                        "id": "implement_first",
                        "prompt": "implement_first",
                        "input_map": {"instruction": "context.defaults.user_instruction"},
                        "parse_output_json": False,
                        "on_success": "check",
                        "on_failure": "END",
                        "route_bindings": {"success": {"context.runtime.latest_impl": "outputs.implement_first"}},
                    },
                    {
                        "id": "check",
                        "prompt": "check",
                        "input_map": {"latest_impl": "context.runtime.latest_impl"},
                        "on_success": "END",
                        "on_failure": "implement_loop",
                        "route_bindings": {"failure": {"context.runtime.latest_check": "outputs.check.control"}},
                    },
                    {
                        "id": "implement_loop",
                        "prompt": "implement_loop",
                        "input_map": {"latest_check": "context.runtime.latest_check"},
                        "parse_output_json": False,
                        "on_success": "check",
                        "on_failure": "END",
                        "route_bindings": {"success": {"context.runtime.latest_impl": "outputs.implement_loop"}},
                    },
                ],
            )

            def payload_for_call(*, node_id: str, step: int, attempt: int, prompt: str) -> dict[str, Any]:
                payload: dict[str, Any]
                if node_id == "implement_first":
                    payload = {"pass": True, "node": node_id, "step": step}
                elif node_id == "check" and attempt == 1:
                    payload = {"pass": False, "node": node_id, "todo": ["missing part"]}
                elif node_id == "implement_loop":
                    payload = {"pass": True, "node": node_id, "fixed": ["missing part"]}
                elif node_id == "check" and attempt == 2:
                    payload = {"pass": True, "node": node_id, "todo": []}
                else:  # pragma: no cover - defensive branch
                    raise AssertionError(f"unexpected node/attempt: {node_id}/{attempt}")
                return payload

            summary = self._run_workflow_with_fake_exec(config_path, payload_for_call=payload_for_call)
            assert summary is not None

            self.assertEqual(summary["status"], "completed")
            self.assertEqual(summary["final_node"], "END")
            self.assertIn("implement_first", summary["outputs"])
            self.assertIn("implement_loop", summary["outputs"])
            self.assertIn("check", summary["outputs"])
            self.assertIn("result", summary["outputs"]["check"])
            self.assertIn("control", summary["outputs"]["check"])
            self.assertEqual(summary["outputs"]["check"]["control"]["pass"], True)

            runtime_state = json.loads((Path(summary["run_state_dir"]) / "runtime_state.json").read_text(encoding="utf-8"))
            self.assertIsInstance(runtime_state["context"]["runtime"]["latest_impl"], str)
            self.assertEqual(
                json.loads(runtime_state["context"]["runtime"]["latest_impl"])["node"],
                "implement_loop",
            )
            self.assertEqual(runtime_state["context"]["runtime"]["latest_check"]["node"], "check")

    def test_run_workflow_uses_run_level_state_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = self.write_workflow_config(
                tmp_path,
                run_args={"project_root": tmp_path, "max_steps": 1},
                defaults={"spec": "s"},
                start="n1",
                nodes=[
                    {
                        "id": "n1",
                        "prompt": "run once",
                        "input_map": {"spec": "context.defaults.spec"},
                        "on_success": "END",
                        "on_failure": "END",
                    }
                ],
            )

            def payload_for_call(*, node_id: str, step: int, attempt: int, prompt: str) -> dict[str, Any]:
                return {"pass": True, "node": node_id, "step": step}

            summary1 = self._run_workflow_with_fake_exec(config_path, payload_for_call=payload_for_call)
            summary2 = self._run_workflow_with_fake_exec(config_path, payload_for_call=payload_for_call)
            assert summary1 is not None and summary2 is not None

            state_root = tmp_path / ".codex-loop-state"
            runs_root = state_root / "runs"
            run_dirs = sorted([p for p in runs_root.iterdir() if p.is_dir()])
            self.assertEqual(len(run_dirs), 2)
            self.assertNotEqual(summary1["run_id"], summary2["run_id"])
            self.assertEqual(
                (state_root / "latest_run_id").read_text(encoding="utf-8").strip(),
                summary2["run_id"],
            )

            for run_dir in run_dirs:
                self.assertTrue((run_dir / "history.jsonl").is_file())
                lines = [line for line in (run_dir / "history.jsonl").read_text(encoding="utf-8").splitlines() if line]
                self.assertEqual(len(lines), 1)
                self.assertTrue((run_dir / "step001__n1__attempt01__meta.json").is_file())

    def test_run_workflow_supports_plain_text_output_when_json_parse_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = self.write_workflow_config(
                tmp_path,
                run_args={"project_root": tmp_path, "max_steps": 3},
                defaults={},
                start="implement",
                nodes=[
                    {
                        "id": "implement",
                        "prompt": "implement",
                        "input_map": {},
                        "parse_output_json": False,
                        "on_success": "check",
                        "on_failure": "END",
                    },
                    {
                        "id": "check",
                        "prompt": "check {{ inputs.impl }}",
                        "input_map": {"impl": "outputs.implement"},
                        "on_success": "END",
                        "on_failure": "END",
                    },
                ],
            )
            captured_prompts: list[str] = []

            def raw_output_for_call(*, node_id: str, step: int, attempt: int, prompt: str):
                if node_id == "implement":
                    return "Implemented feature A.\nNo JSON line."
                return '{"pass": true, "verified": true}'

            summary = self._run_workflow_with_fake_exec(
                config_path,
                raw_output_for_call=raw_output_for_call,
                captured_prompts=captured_prompts,
            )
            assert summary is not None

            self.assertEqual(summary["status"], "completed")
            self.assertEqual(summary["outputs"]["implement"], "Implemented feature A.\nNo JSON line.")
            self.assertIn("Implemented feature A.", captured_prompts[1])

    def test_run_workflow_plain_text_history_and_persisted_outputs_remain_strings(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = self.write_workflow_config(
                tmp_path,
                run_args={"project_root": tmp_path, "max_steps": 1},
                defaults={},
                start="implement",
                nodes=[
                    {
                        "id": "implement",
                        "prompt": "implement",
                        "input_map": {},
                        "parse_output_json": False,
                        "collect_history_to": "context.runtime.implement_history",
                        "on_success": "END",
                        "on_failure": "END",
                    }
                ],
            )

            def raw_output_plain_text(**_kwargs: Any) -> str:
                return "Implemented feature B.\nStill plain text.\n"

            summary = self._run_workflow_with_fake_exec(
                config_path,
                raw_output_for_call=cast(Callable[..., str], raw_output_plain_text),
            )
            assert summary is not None

            expected_output = "Implemented feature B.\nStill plain text."
            self.assertEqual(summary["status"], "completed")
            self.assertEqual(summary["outputs"]["implement"], expected_output)

            runtime_state = json.loads((Path(summary["run_state_dir"]) / "runtime_state.json").read_text(encoding="utf-8"))
            self.assertIsInstance(runtime_state["outputs"]["implement"], str)
            self.assertEqual(runtime_state["outputs"]["implement"], expected_output)
            self.assertEqual(runtime_state["context"]["runtime"]["implement_history"], [expected_output])
            self.assertTrue(all(isinstance(item, str) for item in runtime_state["context"]["runtime"]["implement_history"]))

            parsed_step = json.loads(
                (Path(summary["run_state_dir"]) / "step001__implement__attempt01__parsed.json").read_text(encoding="utf-8")
            )
            self.assertIsInstance(parsed_step, str)
            self.assertEqual(parsed_step, expected_output)

            run_summary = json.loads((Path(summary["run_state_dir"]) / "run_summary.json").read_text(encoding="utf-8"))
            self.assertIsInstance(run_summary["outputs"]["implement"], str)
            self.assertEqual(run_summary["outputs"]["implement"], expected_output)

    def test_build_step_prefix_and_log_name_use_same_node_sanitization(self):
        prefix = module.build_step_prefix(1, "node/a b", 2)
        self.assertEqual(prefix, "step001__node_a_b__attempt02")
        with tempfile.TemporaryDirectory() as tmp:
            log_path = module.make_codex_log_path(Path(tmp), "node/a b", 1, 2)
        self.assertIn("node_a_b", log_path.name)

    def test_run_workflow_collects_output_history_for_node(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = self.write_workflow_config(
                tmp_path,
                run_args={"project_root": tmp_path, "max_steps": 3},
                defaults={},
                start="review",
                nodes=[
                    {
                        "id": "review",
                        "prompt": "review {{ inputs.last_result }}",
                        "input_map": {"last_result": "context.runtime.review_history"},
                        "collect_history_to": "context.runtime.review_history",
                        "on_success": "END",
                        "on_failure": "review",
                    }
                ],
            )
            captured_prompts: list[str] = []

            def payload_for_call(*, node_id: str, step: int, attempt: int, prompt: str) -> dict[str, Any]:
                captured_prompts.append(prompt)
                payloads: list[dict[str, Any]] = [
                    {"pass": False, "issues": ["a"]},
                    {"pass": False, "issues": ["a", "b"]},
                    {"pass": True, "issues": []},
                ]
                return payloads[attempt - 1]

            summary = self._run_workflow_with_fake_exec(
                config_path,
                payload_for_call=payload_for_call,
            )
            assert summary is not None

            self.assertEqual(summary["status"], "completed")
            runtime_state = json.loads((Path(summary["run_state_dir"]) / "runtime_state.json").read_text(encoding="utf-8"))
            self.assertEqual(
                runtime_state["context"]["runtime"]["review_history"],
                [
                    {"result": "", "control": {"pass": False, "issues": ["a"]}},
                    {"result": "", "control": {"pass": False, "issues": ["a", "b"]}},
                    {"result": "", "control": {"pass": True, "issues": []}},
                ],
            )
            self.assertIn('"result": ""', captured_prompts[1])
            parsed_step_3 = json.loads(
                (Path(summary["run_state_dir"]) / "step003__review__attempt03__parsed.json").read_text(encoding="utf-8")
            )
            self.assertEqual(parsed_step_3, {"result": "", "control": {"pass": True, "issues": []}})

    def test_run_workflow_initializes_history_before_first_prompt_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = self.write_workflow_config(
                tmp_path,
                run_args={"project_root": tmp_path, "max_steps": 1},
                defaults={},
                start="review",
                nodes=[
                    {
                        "id": "review",
                        "prompt": "review",
                        "input_map": {"history": "context.runtime.review_history"},
                        "collect_history_to": "context.runtime.review_history",
                        "on_success": "END",
                        "on_failure": "END",
                    }
                ],
            )
            captured_prompts: list[str] = []

            def payload_for_call(*, node_id: str, step: int, attempt: int, prompt: str) -> dict[str, Any]:
                captured_prompts.append(prompt)
                return {"pass": True, "issues": []}

            summary = self._run_workflow_with_fake_exec(
                config_path,
                payload_for_call=payload_for_call,
            )
            assert summary is not None

            self.assertEqual(summary["status"], "completed")
            self.assertEqual(len(captured_prompts), 1)
            runtime_state = json.loads((Path(summary["run_state_dir"]) / "runtime_state.json").read_text(encoding="utf-8"))
            self.assertEqual(
                runtime_state["context"]["runtime"]["review_history"],
                [{"result": "", "control": {"pass": True, "issues": []}}],
            )

    def test_run_workflow_parse_output_json_failure_stops_without_on_failure_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = self.write_workflow_config(
                tmp_path,
                run_args={"project_root": tmp_path, "max_steps": 3},
                defaults={},
                start="review",
                nodes=[
                    {
                        "id": "review",
                        "prompt": "review",
                        "input_map": {},
                        "on_success": "END",
                        "on_failure": "fix",
                    },
                    {
                        "id": "fix",
                        "prompt": "fix",
                        "input_map": {},
                        "on_success": "END",
                        "on_failure": "END",
                    },
                ],
            )
            called_nodes: list[str] = []

            def raw_output_for_call(*, node_id: str, step: int, attempt: int, prompt: str):
                called_nodes.append(node_id)
                return "NOT_JSON"

            self._run_workflow_with_fake_exec(
                config_path,
                raw_output_for_call=raw_output_for_call,
                expect_error="Invalid JSON on last line",
            )

            self.assertEqual(called_nodes, ["review"])

    def test_run_workflow_route_binding_supports_control_and_result_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = self.write_workflow_config(
                tmp_path,
                run_args={"project_root": tmp_path, "max_steps": 2},
                defaults={},
                start="check",
                nodes=[
                    {
                        "id": "check",
                        "prompt": "check",
                        "input_map": {},
                        "on_success": "END",
                        "on_failure": "END",
                        "route_bindings": {
                            "success": {
                                "context.runtime.latest_check_control": "outputs.check.control",
                                "context.runtime.latest_check_result": "outputs.check.result",
                            }
                        },
                    }
                ],
            )

            def raw_output_review_done(**_kwargs: Any) -> str:
                return '已检查完成\n{"pass": true, "issues": []}\n'

            summary = self._run_workflow_with_fake_exec(
                config_path,
                raw_output_for_call=cast(Callable[..., str], raw_output_review_done),
            )
            assert summary is not None

            runtime_state = json.loads((Path(summary["run_state_dir"]) / "runtime_state.json").read_text(encoding="utf-8"))
            self.assertEqual(
                runtime_state["context"]["runtime"]["latest_check_control"],
                {"pass": True, "issues": []},
            )
            self.assertEqual(runtime_state["context"]["runtime"]["latest_check_result"], "已检查完成\n")


class MaxStepsTests(PatchedYamlMixin, unittest.TestCase):
    def test_run_workflow_stops_when_reaching_max_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config: dict[str, Any] = {
                "version": 1,
                "run": {
                    "project_root": str(tmp_path),
                    "state_dir": ".codex-loop-state",
                    "max_steps": 2,
                },
                "executor": {"cmd": ["codex", "exec", "--skip-git-repo-check"]},
                "context": {"defaults": {}},
                "workflow": {
                    "start": "loop",
                    "nodes": [
                        {
                            "id": "loop",
                            "prompt": "loop",
                            "input_map": {},
                            "on_success": "loop",
                            "on_failure": "END",
                        }
                    ],
                },
            }
            config_path = tmp_path / TEST_CONFIG_RELATIVE_PATH
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(json.dumps(config), encoding="utf-8")

            def raw_output_loop(**_kwargs: Any) -> str:
                return '{"pass": true, "node": "loop"}'

            fake_exec = WorkflowTestFactoryMixin().make_fake_codex_exec(
                raw_output_for_call=cast(Callable[..., str], raw_output_loop)
            )
            with (
                self.patch_yaml(),
                patch.object(module, "run_codex_exec", side_effect=fake_exec),
                self.assertRaisesRegex(RuntimeError, "Reached max_steps without END: 2"),
            ):
                module.run_workflow(str(config_path), {})
