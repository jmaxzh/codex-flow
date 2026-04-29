import json
import unittest
from pathlib import Path
from typing import Any

from tests.codex_orchestrator_test_support import runtime_harness


class NativeFlowRuntimeHistoryTests(unittest.TestCase):
    def test_quality_review_loop_history_accumulates_until_converged(self):
        observed_prompts: list[str] = []

        def payload_for_call(*, node_id: str, step: int, attempt: int, prompt: str) -> dict[str, Any]:
            self.assertEqual(node_id, "quality_review")
            observed_prompts.append(prompt)
            if attempt == 1:
                return {"pass": False, "issues": ["arch issue 1"]}
            return {"pass": True, "issues": []}

        with runtime_harness(payload_for_call=payload_for_call) as (_tmp_path, run):
            summary = run("quality_review_loop")
            self.assertEqual(summary["status"], "completed")
            self.assertEqual(summary["final_node"], "END")
            runtime_state = json.loads((Path(summary["run_state_dir"]) / "runtime_state.json").read_text(encoding="utf-8"))
            history = runtime_state["context"]["runtime"]["quality_review_history"]
            self.assertEqual(len(history), 2)
            self.assertEqual(history[0]["control"]["pass"], False)
            self.assertEqual(history[1]["control"]["pass"], True)
            self.assertEqual(summary["outputs"]["quality_review"]["control"]["pass"], True)
            self.assertEqual(len(observed_prompts), 2)
            self.assertIn("历史评审输出: []", observed_prompts[0])
            self.assertIn('"pass": false', observed_prompts[1])

    def test_doc_review_loop_history_accumulates_until_converged(self):
        observed_prompts: list[str] = []

        def payload_for_call(*, node_id: str, step: int, attempt: int, prompt: str) -> dict[str, Any]:
            self.assertEqual(node_id, "doc_review")
            observed_prompts.append(prompt)
            if attempt == 1:
                return {"pass": False, "issues": ["doc issue 1"]}
            return {"pass": True, "issues": []}

        with runtime_harness(payload_for_call=payload_for_call) as (_tmp_path, run):
            summary = run("doc_review_loop")
            self.assertEqual(summary["status"], "completed")
            self.assertEqual(summary["final_node"], "END")
            runtime_state = json.loads((Path(summary["run_state_dir"]) / "runtime_state.json").read_text(encoding="utf-8"))
            history = runtime_state["context"]["runtime"]["doc_review_history"]
            self.assertEqual(len(history), 2)
            self.assertEqual(history[0]["control"]["pass"], False)
            self.assertEqual(history[1]["control"]["pass"], True)
            self.assertEqual(summary["outputs"]["doc_review"]["control"]["pass"], True)
            self.assertEqual(len(observed_prompts), 2)
            self.assertIn("历史评审输出: []", observed_prompts[0])
            self.assertIn('"pass": false', observed_prompts[1])
