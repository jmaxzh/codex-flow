import unittest

from tests.codex_orchestrator_test_support import runtime_harness


class NativeFlowRuntimeFlowControlTests(unittest.TestCase):
    def test_run_state_isolation(self):
        def payload_for_call(*, node_id: str, step: int, attempt: int, prompt: str):
            return {"pass": True, "node": node_id, "step": step}

        with runtime_harness(payload_for_call=payload_for_call) as (tmp_path, run):
            summary1 = run("bug_review_loop")
            summary2 = run("bug_review_loop")

            state_root = tmp_path / ".codex-loop-state"
            runs_root = state_root / "runs"
            run_dirs = sorted([p for p in runs_root.iterdir() if p.is_dir()])
            self.assertEqual(len(run_dirs), 2)
            self.assertNotEqual(summary1["run_id"], summary2["run_id"])
            self.assertEqual((state_root / "latest_run_id").read_text(encoding="utf-8").strip(), summary2["run_id"])

    def test_plain_text_output_and_history_remain_strings(self):
        def raw_output_for_call(*, node_id: str, step: int, attempt: int, prompt: str):
            if node_id == "openspec_implement_first":
                return "Implemented feature A.\nNo JSON line."
            return '{"pass": true, "verified": true}'

        with runtime_harness(raw_output_for_call=raw_output_for_call) as (_tmp_path, run):
            summary = run("openspec_implement")

        self.assertEqual(summary["status"], "completed")
        self.assertEqual(
            summary["outputs"]["openspec_implement_first"],
            "Implemented feature A.\nNo JSON line.",
        )

    def test_parse_output_json_failure_stops_flow(self):
        called_nodes: list[str] = []

        def raw_output_for_call(*, node_id: str, step: int, attempt: int, prompt: str):
            called_nodes.append(node_id)
            return "NOT_JSON"

        with runtime_harness(raw_output_for_call=raw_output_for_call) as (_tmp_path, run):
            with self.assertRaisesRegex(RuntimeError, "Invalid JSON on last line"):
                run("bug_review_loop")

        self.assertEqual(called_nodes, ["bug_review"])
