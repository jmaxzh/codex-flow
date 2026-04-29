import json
import unittest
from pathlib import Path
from typing import Any

from tests.codex_orchestrator_test_support import runtime_harness


class NativeFlowRuntimeBindingsTests(unittest.TestCase):
    def test_implement_loop_applies_route_bindings_and_outputs(self):
        def payload_for_call(*, node_id: str, step: int, attempt: int, prompt: str) -> dict[str, Any]:
            if node_id == "implement_first":
                return {"pass": True, "node": node_id, "step": step}
            if node_id == "implement_review" and attempt == 1:
                return {"pass": False, "node": node_id, "todo": ["missing part"]}
            if node_id == "implement_continue":
                return {"pass": True, "node": node_id, "fixed": ["missing part"]}
            if node_id == "implement_review" and attempt == 2:
                return {"pass": True, "node": node_id, "todo": []}
            raise AssertionError(f"unexpected node/attempt: {node_id}/{attempt}")

        with runtime_harness(payload_for_call=payload_for_call) as (_tmp_path, run):
            summary = run("implement_loop")
            self.assertEqual(summary["status"], "completed")
            self.assertEqual(summary["final_node"], "END")
            self.assertIn("implement_first", summary["outputs"])
            self.assertIn("implement_continue", summary["outputs"])
            self.assertIn("implement_review", summary["outputs"])
            self.assertEqual(summary["outputs"]["implement_review"]["control"]["pass"], True)

            runtime_state = json.loads((Path(summary["run_state_dir"]) / "runtime_state.json").read_text(encoding="utf-8"))
            self.assertIsInstance(runtime_state["context"]["runtime"]["latest_impl"], str)
            self.assertEqual(json.loads(runtime_state["context"]["runtime"]["latest_impl"])["node"], "implement_continue")
            self.assertEqual(runtime_state["context"]["runtime"]["latest_check"]["node"], "implement_review")

    def test_openspec_implement_applies_route_bindings_and_outputs(self):
        def payload_for_call(*, node_id: str, step: int, attempt: int, prompt: str) -> dict[str, Any]:
            if node_id == "openspec_implement_first":
                return {"pass": True, "node": node_id, "step": step}
            if node_id == "openspec_implement_review" and attempt == 1:
                return {"pass": False, "node": node_id, "todo": ["missing part"]}
            if node_id == "openspec_implement_continue":
                return {"pass": True, "node": node_id, "fixed": ["missing part"]}
            if node_id == "openspec_implement_review" and attempt == 2:
                return {"pass": True, "node": node_id, "todo": []}
            raise AssertionError(f"unexpected node/attempt: {node_id}/{attempt}")

        with runtime_harness(payload_for_call=payload_for_call) as (_tmp_path, run):
            summary = run("openspec_implement")
            self.assertEqual(summary["status"], "completed")
            self.assertEqual(summary["final_node"], "END")
            self.assertIn("openspec_implement_first", summary["outputs"])
            self.assertIn("openspec_implement_continue", summary["outputs"])
            self.assertIn("openspec_implement_review", summary["outputs"])
            self.assertEqual(summary["outputs"]["openspec_implement_review"]["control"]["pass"], True)

            runtime_state = json.loads((Path(summary["run_state_dir"]) / "runtime_state.json").read_text(encoding="utf-8"))
            self.assertIsInstance(runtime_state["context"]["runtime"]["latest_impl"], str)
            latest_impl_node = json.loads(runtime_state["context"]["runtime"]["latest_impl"])["node"]
            self.assertEqual(latest_impl_node, "openspec_implement_continue")
            self.assertEqual(runtime_state["context"]["runtime"]["latest_check"]["node"], "openspec_implement_review")
