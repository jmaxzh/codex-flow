import json
import unittest
from typing import Any

from tests.codex_orchestrator_test_support import runtime_harness


class NativeFlowRuntimeMarkersTests(unittest.TestCase):
    def test_openspec_propose_runtime_marker_controls_post_review_routing(self):
        called_nodes: list[str] = []

        def payload_for_call(*, node_id: str, step: int, attempt: int, prompt: str) -> dict[str, Any]:
            called_nodes.append(node_id)
            if node_id == "openspec_propose_review" and attempt == 1:
                return {"pass": False, "issues": ["a"]}
            if node_id == "openspec_propose_review" and attempt == 2:
                return {"pass": True, "issues": []}
            if node_id == "openspec_propose_review" and attempt == 3:
                return {"pass": True, "issues": []}
            raise AssertionError(f"unexpected node/attempt: {node_id}/{attempt}")

        def raw_output_for_call(*, node_id: str, step: int, attempt: int, prompt: str) -> str:
            if node_id == "openspec_propose_revise":
                called_nodes.append(node_id)
                return "fixed"
            payload = payload_for_call(node_id=node_id, step=step, attempt=attempt, prompt=prompt)
            return json.dumps(payload, ensure_ascii=False)

        with runtime_harness(raw_output_for_call=raw_output_for_call) as (_tmp_path, run):
            summary = run("openspec_propose")

        self.assertEqual(summary["status"], "completed")
        self.assertEqual(
            called_nodes,
            [
                "openspec_propose_review",
                "openspec_propose_review",
                "openspec_propose_revise",
                "openspec_propose_review",
            ],
        )
        self.assertIn("openspec_propose_revise", summary["outputs"])

    def test_doc_revise_runtime_marker_controls_post_review_routing(self):
        called_nodes: list[str] = []

        def payload_for_call(*, node_id: str, step: int, attempt: int, prompt: str) -> dict[str, Any]:
            called_nodes.append(node_id)
            if node_id == "doc_review" and attempt == 1:
                return {"pass": False, "issues": ["a"]}
            if node_id == "doc_review" and attempt == 2:
                return {"pass": True, "issues": []}
            if node_id == "doc_review" and attempt == 3:
                return {"pass": True, "issues": []}
            raise AssertionError(f"unexpected node/attempt: {node_id}/{attempt}")

        def raw_output_for_call(*, node_id: str, step: int, attempt: int, prompt: str) -> str:
            if node_id == "doc_revise":
                called_nodes.append(node_id)
                return "fixed"
            payload = payload_for_call(node_id=node_id, step=step, attempt=attempt, prompt=prompt)
            return json.dumps(payload, ensure_ascii=False)

        with runtime_harness(raw_output_for_call=raw_output_for_call) as (_tmp_path, run):
            summary = run("doc_doctor")

        self.assertEqual(summary["status"], "completed")
        self.assertEqual(called_nodes, ["doc_review", "doc_review", "doc_revise", "doc_review"])
        self.assertIn("doc_revise", summary["outputs"])
