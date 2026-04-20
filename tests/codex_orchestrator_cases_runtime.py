import json
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from tests.codex_orchestrator_test_support import make_fake_codex_exec, patch_native_exec, run_workflow_direct


class NativeFlowRuntimeTests(unittest.TestCase):
    def test_implement_loop_applies_route_bindings_and_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            def payload_for_call(*, node_id: str, step: int, attempt: int, prompt: str) -> dict[str, Any]:
                if node_id == "implement_first":
                    return {"pass": True, "node": node_id, "step": step}
                if node_id == "check" and attempt == 1:
                    return {"pass": False, "node": node_id, "todo": ["missing part"]}
                if node_id == "implement_loop":
                    return {"pass": True, "node": node_id, "fixed": ["missing part"]}
                if node_id == "check" and attempt == 2:
                    return {"pass": True, "node": node_id, "todo": []}
                raise AssertionError(f"unexpected node/attempt: {node_id}/{attempt}")

            fake_exec = make_fake_codex_exec(payload_for_call=payload_for_call)
            with patch_native_exec(fake_exec):
                summary = run_workflow_direct("implement_loop", {}, str(tmp_path))

            self.assertEqual(summary["status"], "completed")
            self.assertEqual(summary["final_node"], "END")
            self.assertIn("implement_first", summary["outputs"])
            self.assertIn("implement_loop", summary["outputs"])
            self.assertIn("check", summary["outputs"])
            self.assertEqual(summary["outputs"]["check"]["control"]["pass"], True)

            runtime_state = json.loads((Path(summary["run_state_dir"]) / "runtime_state.json").read_text(encoding="utf-8"))
            self.assertIsInstance(runtime_state["context"]["runtime"]["latest_impl"], str)
            self.assertEqual(json.loads(runtime_state["context"]["runtime"]["latest_impl"])["node"], "implement_loop")
            self.assertEqual(runtime_state["context"]["runtime"]["latest_check"]["node"], "check")

    def test_run_state_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            def payload_for_call(*, node_id: str, step: int, attempt: int, prompt: str) -> dict[str, Any]:
                return {"pass": True, "node": node_id, "step": step}

            fake_exec = make_fake_codex_exec(payload_for_call=payload_for_call)
            with patch_native_exec(fake_exec):
                summary1 = run_workflow_direct("reviewer_loop", {"__max_steps": "1"}, str(tmp_path))
                summary2 = run_workflow_direct("reviewer_loop", {"__max_steps": "1"}, str(tmp_path))

            state_root = tmp_path / ".codex-loop-state"
            runs_root = state_root / "runs"
            run_dirs = sorted([p for p in runs_root.iterdir() if p.is_dir()])
            self.assertEqual(len(run_dirs), 2)
            self.assertNotEqual(summary1["run_id"], summary2["run_id"])
            self.assertEqual((state_root / "latest_run_id").read_text(encoding="utf-8").strip(), summary2["run_id"])

    def test_plain_text_output_and_history_remain_strings(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            def raw_output_for_call(*, node_id: str, step: int, attempt: int, prompt: str):
                if node_id == "implement_first":
                    return "Implemented feature A.\nNo JSON line."
                return '{"pass": true, "verified": true}'

            fake_exec = make_fake_codex_exec(raw_output_for_call=raw_output_for_call)
            with patch_native_exec(fake_exec):
                summary = run_workflow_direct("implement_loop", {"__max_steps": "2"}, str(tmp_path))

            self.assertEqual(summary["status"], "completed")
            self.assertEqual(summary["outputs"]["implement_first"], "Implemented feature A.\nNo JSON line.")

    def test_parse_output_json_failure_stops_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            called_nodes: list[str] = []

            def raw_output_for_call(*, node_id: str, step: int, attempt: int, prompt: str):
                called_nodes.append(node_id)
                return "NOT_JSON"

            fake_exec = make_fake_codex_exec(raw_output_for_call=raw_output_for_call)
            with patch_native_exec(fake_exec), self.assertRaisesRegex(RuntimeError, "Invalid JSON on last line"):
                run_workflow_direct("reviewer_loop", {}, str(tmp_path))

            self.assertEqual(called_nodes, ["bug_reviwer"])

    def test_doc_doctor_runtime_marker_controls_post_review_routing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            called_nodes: list[str] = []

            def payload_for_call(*, node_id: str, step: int, attempt: int, prompt: str) -> dict[str, Any]:
                called_nodes.append(node_id)
                if node_id == "doc_reviwer" and attempt == 1:
                    return {"pass": False, "issues": ["a"]}
                if node_id == "doc_reviwer" and attempt == 2:
                    return {"pass": True, "issues": []}
                if node_id == "doc_reviwer" and attempt == 3:
                    return {"pass": True, "issues": []}
                raise AssertionError(f"unexpected node/attempt: {node_id}/{attempt}")

            def raw_output_for_call(*, node_id: str, step: int, attempt: int, prompt: str) -> str:
                if node_id == "doc_fix":
                    called_nodes.append(node_id)
                    return "fixed"
                payload = payload_for_call(node_id=node_id, step=step, attempt=attempt, prompt=prompt)
                return json.dumps(payload, ensure_ascii=False)

            fake_exec = make_fake_codex_exec(raw_output_for_call=raw_output_for_call)
            with patch_native_exec(fake_exec):
                summary = run_workflow_direct("doc_doctor", {}, str(tmp_path))

            self.assertEqual(summary["status"], "completed")
            self.assertEqual(called_nodes, ["doc_reviwer", "doc_reviwer", "doc_fix", "doc_reviwer"])
            self.assertIn("doc_fix", summary["outputs"])

    def test_max_steps_hard_termination(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            def raw_output_for_call(**_kwargs: Any) -> str:
                return '{"pass": false}'

            fake_exec = make_fake_codex_exec(raw_output_for_call=cast(Callable[..., str], raw_output_for_call))
            with patch_native_exec(fake_exec), self.assertRaisesRegex(RuntimeError, "Reached max_steps without END: 2"):
                run_workflow_direct("reviewer_loop", {"__max_steps": "2"}, str(tmp_path))

    def test_refactor_loop_history_accumulates_until_converged(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            observed_prompts: list[str] = []

            def payload_for_call(*, node_id: str, step: int, attempt: int, prompt: str) -> dict[str, Any]:
                self.assertEqual(node_id, "arch_reviwer")
                observed_prompts.append(prompt)
                if attempt == 1:
                    return {"pass": False, "issues": ["arch issue 1"]}
                return {"pass": True, "issues": []}

            fake_exec = make_fake_codex_exec(payload_for_call=payload_for_call)
            with patch_native_exec(fake_exec):
                summary = run_workflow_direct("refactor_loop", {"__max_steps": "3"}, str(tmp_path))

            self.assertEqual(summary["status"], "completed")
            self.assertEqual(summary["final_node"], "END")
            runtime_state = json.loads((Path(summary["run_state_dir"]) / "runtime_state.json").read_text(encoding="utf-8"))
            history = runtime_state["context"]["runtime"]["arch_review_history"]
            self.assertEqual(len(history), 2)
            self.assertEqual(history[0]["control"]["pass"], False)
            self.assertEqual(history[1]["control"]["pass"], True)
            self.assertEqual(summary["outputs"]["arch_reviwer"]["control"]["pass"], True)
            self.assertEqual(len(observed_prompts), 2)
            self.assertIn("历史评审输出: []", observed_prompts[0])
            self.assertIn('"pass": false', observed_prompts[1])

    def test_doc_reviewer_loop_history_accumulates_until_converged(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            observed_prompts: list[str] = []

            def payload_for_call(*, node_id: str, step: int, attempt: int, prompt: str) -> dict[str, Any]:
                self.assertEqual(node_id, "doc_reviwer")
                observed_prompts.append(prompt)
                if attempt == 1:
                    return {"pass": False, "issues": ["doc issue 1"]}
                return {"pass": True, "issues": []}

            fake_exec = make_fake_codex_exec(payload_for_call=payload_for_call)
            with patch_native_exec(fake_exec):
                summary = run_workflow_direct("doc_reviewer_loop", {"__max_steps": "3"}, str(tmp_path))

            self.assertEqual(summary["status"], "completed")
            self.assertEqual(summary["final_node"], "END")
            runtime_state = json.loads((Path(summary["run_state_dir"]) / "runtime_state.json").read_text(encoding="utf-8"))
            history = runtime_state["context"]["runtime"]["doc_review_history"]
            self.assertEqual(len(history), 2)
            self.assertEqual(history[0]["control"]["pass"], False)
            self.assertEqual(history[1]["control"]["pass"], True)
            self.assertEqual(summary["outputs"]["doc_reviwer"]["control"]["pass"], True)
            self.assertEqual(len(observed_prompts), 2)
            self.assertIn("历史评审输出: []", observed_prompts[0])
            self.assertIn('"pass": false', observed_prompts[1])
