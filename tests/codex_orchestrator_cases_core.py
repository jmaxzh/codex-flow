import unittest
from typing import Any, cast

from tests.codex_orchestrator_module_loader import ROOT, module


class OutputContractTests(unittest.TestCase):
    def test_parse_and_validate_uses_last_non_empty_line(self):
        payload, pass_flag = module.parse_and_validate_output('本轮实现已完成。\n{"pass": true, "change_summary": "ok"}\n')
        self.assertTrue(pass_flag)
        self.assertEqual(payload["result"], "本轮实现已完成。\n")
        self.assertEqual(payload["control"]["change_summary"], "ok")

    def test_parse_and_validate_preserves_trailing_whitespace_in_result(self):
        payload, pass_flag = module.parse_and_validate_output('结论文本末尾含空格   \n\n{"pass": true}\n')
        self.assertTrue(pass_flag)
        self.assertEqual(payload["result"], "结论文本末尾含空格   \n\n")

    def test_parse_and_validate_preserves_whitespace_only_prefix(self):
        payload, pass_flag = module.parse_and_validate_output(' \n\t\n{"pass": false}\n')
        self.assertFalse(pass_flag)
        self.assertEqual(payload["result"], " \n\t\n")
        self.assertEqual(payload["control"], {"pass": False})

    def test_parse_and_validate_supports_control_only_output(self):
        payload, pass_flag = module.parse_and_validate_output('{"pass": true}')
        self.assertTrue(pass_flag)
        self.assertEqual(payload["result"], "")
        self.assertEqual(payload["control"], {"pass": True})

    def test_parse_and_validate_fails_when_last_non_empty_line_not_json(self):
        with self.assertRaisesRegex(RuntimeError, "Invalid JSON on last line"):
            module.parse_and_validate_output('{"pass": true}\nDONE')

    def test_parse_and_validate_requires_pass_field(self):
        with self.assertRaisesRegex(RuntimeError, "must contain 'pass'"):
            module.parse_and_validate_output('{"result":"ok"}')

    def test_parse_and_validate_requires_boolean_pass(self):
        with self.assertRaisesRegex(RuntimeError, "must be boolean"):
            module.parse_and_validate_output('{"pass":"yes"}')

    def test_parse_and_validate_requires_last_line_json_object(self):
        with self.assertRaisesRegex(RuntimeError, "must be an object"):
            module.parse_and_validate_output("[1,2,3]")

    def test_resolve_node_output_skips_json_parse_when_disabled(self):
        output, pass_flag = module.resolve_node_output("implementation done\nnotes\n", False)
        self.assertTrue(pass_flag)
        self.assertEqual(output, "implementation done\nnotes")


class RoutingTests(unittest.TestCase):
    def test_resolve_next_node_uses_success_and_failure_routes(self):
        node = {"id": "verify", "on_success": "done", "on_failure": "fix"}
        self.assertEqual(module.resolve_next_node(node, True), "done")
        self.assertEqual(module.resolve_next_node(node, False), "fix")

    def test_apply_route_bindings_copies_mutable_values_before_write(self):
        node = {
            "id": "n1",
            "route_bindings": {
                "success": {"context.runtime.latest_impl": "outputs.n1"},
                "failure": {},
            },
        }
        runtime_state: dict[str, Any] = {
            "context": {"defaults": {}, "runtime": {}},
            "outputs": {"n1": {"nested": {"k": 1}, "arr": [1]}},
        }

        module.apply_route_bindings(node, True, runtime_state)
        latest_impl = cast(dict[str, Any], runtime_state["context"]["runtime"]["latest_impl"])
        latest_nested = cast(dict[str, Any], latest_impl["nested"])
        latest_arr = cast(list[int], latest_impl["arr"])
        outputs_n1 = cast(dict[str, Any], runtime_state["outputs"]["n1"])
        outputs_nested = cast(dict[str, Any], outputs_n1["nested"])
        outputs_arr = cast(list[int], outputs_n1["arr"])

        latest_nested["k"] = 99
        latest_arr.append(2)
        self.assertEqual(outputs_nested["k"], 1)
        self.assertEqual(outputs_arr, [1])


class DataPassthroughTests(unittest.TestCase):
    def test_build_prompt_inputs_reads_paths(self):
        node = {
            "id": "implement",
            "input_map": {
                "plan_result": "outputs.plan.result",
                "plan_control": "outputs.plan.control",
            },
        }
        runtime_state: dict[str, Any] = {
            "context": {"defaults": {}, "runtime": {}},
            "outputs": {
                "plan": {
                    "result": "结论 A\n",
                    "control": {"pass": True, "plan_summary": "summary", "tasks": ["a", "b"]},
                }
            },
        }

        prompt_inputs = module.build_prompt_inputs(node, runtime_state)
        self.assertEqual(prompt_inputs["plan_result"], runtime_state["outputs"]["plan"]["result"])
        self.assertEqual(prompt_inputs["plan_control"], runtime_state["outputs"]["plan"]["control"])

        rendered = module.render_prompt(
            "Plan: {{ inputs.plan_result }} | Control: {{ inputs.plan_control }}",
            prompt_inputs,
            str(ROOT / "presets" / "openspec_implement.yaml"),
            "implement",
            "workflow.nodes[1].prompt",
        )
        self.assertIn("Plan: 结论 A", rendered)
        self.assertIn('"plan_summary": "summary"', rendered)

    def test_build_prompt_inputs_requires_existing_source_path(self):
        node = {
            "id": "implement",
            "input_map": {"plan_output": "outputs.plan"},
        }
        runtime_state: dict[str, Any] = {
            "context": {"defaults": {}, "runtime": {}},
            "outputs": {},
        }
        with self.assertRaisesRegex(RuntimeError, "Path not found"):
            module.build_prompt_inputs(node, runtime_state)


class HistoryTargetTests(unittest.TestCase):
    def test_ensure_history_list_creates_missing_path_and_returns_list(self):
        runtime_state: dict[str, Any] = {"context": {"defaults": {}, "runtime": {}}, "outputs": {}}
        history = module.ensure_history_list(
            runtime_state,
            "context.runtime.review_history",
            ("context", "runtime", "review_history"),
        )
        review_history = cast(list[Any], runtime_state["context"]["runtime"]["review_history"])
        self.assertEqual(history, [])
        self.assertIs(history, review_history)

    def test_ensure_history_list_rejects_non_list_target(self):
        runtime_state: dict[str, Any] = {
            "context": {"defaults": {}, "runtime": {"review_history": {}}},
            "outputs": {},
        }
        with self.assertRaisesRegex(RuntimeError, "History target must be array"):
            module.ensure_history_list(
                runtime_state,
                "context.runtime.review_history",
                ("context", "runtime", "review_history"),
            )
