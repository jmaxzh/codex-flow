import unittest

from tests.codex_orchestrator_test_support import ROOT, module

class OutputContractTests(unittest.TestCase):
    def test_parse_and_validate_uses_last_non_empty_line(self):
        payload, pass_flag = module.parse_and_validate_output(
            "本轮实现已完成。\n{\"pass\": true, \"change_summary\": \"ok\"}\n"
        )
        self.assertTrue(pass_flag)
        self.assertEqual(payload["result"], "本轮实现已完成。\n")
        self.assertEqual(payload["control"]["change_summary"], "ok")

    def test_parse_and_validate_preserves_trailing_whitespace_in_result(self):
        payload, pass_flag = module.parse_and_validate_output(
            "结论文本末尾含空格   \n\n{\"pass\": true}\n"
        )
        self.assertTrue(pass_flag)
        self.assertEqual(payload["result"], "结论文本末尾含空格   \n\n")

    def test_parse_and_validate_preserves_whitespace_only_prefix(self):
        payload, pass_flag = module.parse_and_validate_output(" \n\t\n{\"pass\": false}\n")
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
            module.parse_and_validate_output("{\"pass\": true}\nDONE")

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
            "compiled": {
                "route_bindings": {
                    "success": [
                        {
                            "target": "context.runtime.latest_impl",
                            "source": "outputs.n1",
                            "target_parts": ("context", "runtime", "latest_impl"),
                            "source_parts": ("outputs", "n1"),
                        }
                    ],
                    "failure": [],
                }
            },
        }
        runtime_state = {
            "context": {"defaults": {}, "runtime": {}},
            "outputs": {"n1": {"nested": {"k": 1}, "arr": [1]}},
        }

        module.apply_route_bindings(node, True, runtime_state)

        runtime_state["context"]["runtime"]["latest_impl"]["nested"]["k"] = 99
        runtime_state["context"]["runtime"]["latest_impl"]["arr"].append(2)
        self.assertEqual(runtime_state["outputs"]["n1"]["nested"]["k"], 1)
        self.assertEqual(runtime_state["outputs"]["n1"]["arr"], [1])

    def test_apply_route_bindings_requires_compiled_parts(self):
        node = {
            "id": "n1",
            "route_bindings": {"success": {"context.runtime.latest_impl": "outputs.n1"}},
        }
        runtime_state = {
            "context": {"defaults": {}, "runtime": {}},
            "outputs": {"n1": {"result": "", "control": {"pass": True}}},
        }
        with self.assertRaisesRegex(RuntimeError, "missing compiled config"):
            module.apply_route_bindings(node, True, runtime_state)


class DataPassthroughTests(unittest.TestCase):
    def test_downstream_can_read_upstream_split_output(self):
        node = {
            "id": "implement",
            "input_map": {
                "plan_result": "outputs.plan.result",
                "plan_control": "outputs.plan.control",
            },
            "compiled": {
                "input_bindings": [
                    {
                        "input_key": "plan_result",
                        "source": "outputs.plan.result",
                        "source_parts": ("outputs", "plan", "result"),
                    },
                    {
                        "input_key": "plan_control",
                        "source": "outputs.plan.control",
                        "source_parts": ("outputs", "plan", "control"),
                    },
                ]
            },
        }
        runtime_state = {
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
            str(ROOT / "presets" / "implement_loop.yaml"),
            "implement",
            "workflow.nodes[1].prompt",
        )
        self.assertIn("Plan: 结论 A", rendered)
        self.assertIn('"plan_summary": "summary"', rendered)

    def test_downstream_can_read_runtime_context(self):
        node = {
            "id": "check",
            "input_map": {"latest_impl": "context.runtime.latest_impl"},
            "compiled": {
                "input_bindings": [
                    {
                        "input_key": "latest_impl",
                        "source": "context.runtime.latest_impl",
                        "source_parts": ("context", "runtime", "latest_impl"),
                    }
                ]
            },
        }
        runtime_state = {
            "context": {
                "defaults": {},
                "runtime": {"latest_impl": {"pass": True, "change_summary": "done"}},
            },
            "outputs": {},
        }

        prompt_inputs = module.build_prompt_inputs(node, runtime_state)
        self.assertEqual(prompt_inputs["latest_impl"], runtime_state["context"]["runtime"]["latest_impl"])

    def test_build_prompt_inputs_reads_compiled_paths_without_revalidating_runtime(self):
        node = {
            "id": "implement",
            "input_map": {"plan_output": "invalid.source.path"},
            "compiled": {
                "input_bindings": [
                    {
                        "input_key": "plan_output",
                        "source": "invalid.source.path",
                        "source_parts": ("outputs", "plan"),
                    }
                ]
            },
        }
        runtime_state = {
            "context": {"defaults": {}, "runtime": {}},
            "outputs": {"plan": {"result": "", "control": {"pass": True, "plan_summary": "summary"}}},
        }

        prompt_inputs = module.build_prompt_inputs(node, runtime_state)
        self.assertEqual(prompt_inputs["plan_output"], runtime_state["outputs"]["plan"])

    def test_build_prompt_inputs_requires_compiled_parts(self):
        node = {
            "id": "implement",
            "input_map": {"plan_output": "outputs.plan"},
        }
        runtime_state = {
            "context": {"defaults": {}, "runtime": {}},
            "outputs": {"plan": {"result": "", "control": {"pass": True}}},
        }
        with self.assertRaisesRegex(RuntimeError, "missing compiled config"):
            module.build_prompt_inputs(node, runtime_state)


class HistoryTargetTests(unittest.TestCase):
    def test_ensure_history_list_creates_missing_path_and_returns_list(self):
        runtime_state = {"context": {"defaults": {}, "runtime": {}}, "outputs": {}}
        history = module.ensure_history_list(
            runtime_state,
            "context.runtime.review_history",
            ("context", "runtime", "review_history"),
        )
        self.assertEqual(history, [])
        self.assertIs(history, runtime_state["context"]["runtime"]["review_history"])

    def test_ensure_history_list_rejects_non_list_target(self):
        runtime_state = {"context": {"defaults": {}, "runtime": {"review_history": {}}}, "outputs": {}}
        with self.assertRaisesRegex(RuntimeError, "History target must be array"):
            module.ensure_history_list(
                runtime_state,
                "context.runtime.review_history",
                ("context", "runtime", "review_history"),
            )

