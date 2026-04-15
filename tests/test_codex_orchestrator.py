import importlib.util
import json
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "codex_automation_loops.py"
TEST_CONFIG_RELATIVE_PATH = Path("presets") / "test_preset.yaml"


spec = importlib.util.spec_from_file_location("codex_orchestrator", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class PatchedYamlMixin:
    def patch_yaml(self):
        return patch.multiple(
            module,
            YAML_IMPORT_ERROR=None,
            yaml=types.SimpleNamespace(safe_load=json.loads),
        )


class WorkflowTestFactoryMixin:
    def write_workflow_config(
        self,
        base_dir: Path,
        *,
        project_root: Path,
        max_steps: int,
        defaults: dict[str, object],
        start: str,
        nodes: list[dict[str, object]],
    ) -> Path:
        payload = {
            "version": 1,
            "run": {
                "project_root": str(project_root),
                "state_dir": ".codex-loop-state",
                "max_steps": max_steps,
            },
            "executor": {"cmd": ["codex", "exec", "--skip-git-repo-check"]},
            "context": {"defaults": defaults},
            "workflow": {"start": start, "nodes": nodes},
        }
        config_path = base_dir / TEST_CONFIG_RELATIVE_PATH
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(payload), encoding="utf-8")
        return config_path

    def make_fake_codex_exec(self, payload_for_call):
        def fake_codex_exec(
            project_root: str,
            executor_cmd: list[str],
            prompt: str,
            out_file: str,
            task_log_dir: str,
            node_id: str,
            step: int,
            attempt: int,
        ) -> str:
            payload = payload_for_call(node_id=node_id, step=step, attempt=attempt, prompt=prompt)
            Path(out_file).write_text(json.dumps(payload), encoding="utf-8")
            log_path = Path(task_log_dir) / f"fake_{step}_{attempt}.log"
            log_path.write_text("ok", encoding="utf-8")
            return str(log_path)

        return fake_codex_exec


class ConfigValidationTests(PatchedYamlMixin, unittest.TestCase):
    def _write_config(self, base_dir: Path, payload: dict) -> Path:
        config_path = base_dir / TEST_CONFIG_RELATIVE_PATH
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(payload), encoding="utf-8")
        return config_path

    def _minimal_valid_config(self, project_root: str) -> dict:
        return {
            "version": 1,
            "run": {
                "project_root": project_root,
                "state_dir": ".codex-loop-state",
                "max_steps": 3,
            },
            "executor": {"cmd": ["codex", "exec", "--skip-git-repo-check"]},
            "context": {"defaults": {"spec": "ok"}},
            "workflow": {
                "start": "n1",
                "nodes": [
                    {
                        "id": "n1",
                        "prompt": "x",
                        "input_map": {"spec": "context.defaults.spec"},
                        "on_success": "END",
                        "on_failure": "END",
                    }
                ],
            },
        }

    def test_load_config_fails_when_route_target_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            payload["workflow"]["nodes"][0]["on_success"] = "missing_node"
            config_path = self._write_config(tmp_path, payload)

            with self.patch_yaml(), self.assertRaisesRegex(RuntimeError, "invalid on_success"):
                module.load_config(str(config_path), {})

    def test_load_config_fails_when_on_failure_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            del payload["workflow"]["nodes"][0]["on_failure"]
            config_path = self._write_config(tmp_path, payload)

            with self.patch_yaml(), self.assertRaisesRegex(RuntimeError, "on_failure"):
                module.load_config(str(config_path), {})

    def test_load_config_fails_when_node_id_is_reserved_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            payload["workflow"]["nodes"][0]["id"] = "END"
            payload["workflow"]["start"] = "END"
            config_path = self._write_config(tmp_path, payload)

            with self.patch_yaml(), self.assertRaisesRegex(RuntimeError, "reserved id: END"):
                module.load_config(str(config_path), {})

    def test_load_config_fails_when_route_binding_target_not_runtime_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            payload["workflow"]["nodes"][0]["route_bindings"] = {
                "success": {"outputs.latest_impl": "outputs.n1"}
            }
            config_path = self._write_config(tmp_path, payload)

            with self.patch_yaml(), self.assertRaisesRegex(RuntimeError, "must start with context.runtime."):
                module.load_config(str(config_path), {})

    def test_load_config_applies_context_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            payload["context"]["defaults"]["user_instruction"] = "from preset"
            config_path = self._write_config(tmp_path, payload)

            with self.patch_yaml():
                config = module.load_config(
                    str(config_path),
                    {"spec": "from cli", "user_instruction": "override", "extra": "new"},
                )

            self.assertEqual(config["context"]["defaults"]["spec"], "from cli")
            self.assertEqual(config["context"]["defaults"]["user_instruction"], "override")
            self.assertEqual(config["context"]["defaults"]["extra"], "new")

    def test_load_config_rejects_nested_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            payload["context"]["defaults"] = {"spec": {"path": "bad"}}
            config_path = self._write_config(tmp_path, payload)

            with self.patch_yaml(), self.assertRaisesRegex(RuntimeError, "cannot be object or array"):
                module.load_config(str(config_path), {})

    def test_load_config_rejects_non_string_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            payload["workflow"]["nodes"][0]["prompt"] = {"bad": "type"}
            config_path = self._write_config(tmp_path, payload)

            with self.patch_yaml(), self.assertRaisesRegex(RuntimeError, "workflow.nodes\\[1\\]\\.prompt"):
                module.load_config(str(config_path), {})

    def test_load_config_rejects_empty_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            payload["workflow"]["nodes"][0]["prompt"] = "   "
            config_path = self._write_config(tmp_path, payload)

            with self.patch_yaml(), self.assertRaisesRegex(RuntimeError, "workflow.nodes\\[1\\]\\.prompt"):
                module.load_config(str(config_path), {})

    def test_load_config_rejects_collect_history_to_outside_runtime_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            payload["workflow"]["nodes"][0]["collect_history_to"] = "outputs.review_history"
            config_path = self._write_config(tmp_path, payload)

            with self.patch_yaml(), self.assertRaisesRegex(RuntimeError, "collect_history_to must start"):
                module.load_config(str(config_path), {})

    def test_load_config_compiles_input_and_route_binding_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            payload["workflow"]["nodes"][0]["route_bindings"] = {
                "success": {"context.runtime.latest_impl": "outputs.n1"}
            }
            config_path = self._write_config(tmp_path, payload)

            with self.patch_yaml():
                config = module.load_config(str(config_path), {})

            node = config["workflow"]["nodes"][0]
            self.assertEqual(node["input_map_parts"]["spec"], ("context", "defaults", "spec"))
            self.assertEqual(
                node["route_bindings_parts"]["success"][0]["source_parts"],
                ("outputs", "n1"),
            )


class OutputContractTests(unittest.TestCase):
    def test_parse_and_validate_uses_last_non_empty_line(self):
        payload, pass_flag = module.parse_and_validate_output(
            "本轮实现已完成。\n{\"pass\": true, \"change_summary\": \"ok\"}\n"
        )
        self.assertTrue(pass_flag)
        self.assertEqual(payload["change_summary"], "ok")

    def test_parse_and_validate_fails_when_last_non_empty_line_not_json(self):
        with self.assertRaisesRegex(RuntimeError, "Invalid JSON on last line"):
            module.parse_and_validate_output("{\"pass\": true}\nDONE")

    def test_parse_and_validate_requires_pass_field(self):
        with self.assertRaisesRegex(RuntimeError, "must contain 'pass'"):
            module.parse_and_validate_output('{"result":"ok"}')

    def test_parse_and_validate_requires_boolean_pass(self):
        with self.assertRaisesRegex(RuntimeError, "must be boolean"):
            module.parse_and_validate_output('{"pass":"yes"}')


class RoutingTests(unittest.TestCase):
    def test_resolve_next_node_uses_success_and_failure_routes(self):
        node = {"id": "verify", "on_success": "done", "on_failure": "fix"}
        existing = ["verify", "done", "fix"]

        self.assertEqual(module.resolve_next_node(node, True, existing), "done")
        self.assertEqual(module.resolve_next_node(node, False, existing), "fix")


class DataPassthroughTests(unittest.TestCase):
    def test_downstream_can_read_upstream_full_json(self):
        node = {
            "id": "implement",
            "input_map": {
                "plan_output": "outputs.plan",
            },
        }
        runtime_state = {
            "context": {"defaults": {}, "runtime": {}},
            "outputs": {
                "plan": {
                    "pass": True,
                    "plan_summary": "summary",
                    "tasks": ["a", "b"],
                    "nested": {"k": 1},
                }
            },
        }

        prompt_inputs = module.build_prompt_inputs(node, runtime_state)
        self.assertEqual(prompt_inputs["plan_output"], runtime_state["outputs"]["plan"])

        rendered = module.render_prompt(
            "Plan: {{ inputs.plan_output }}",
            prompt_inputs,
            str(ROOT / "presets" / "implement_loop.yaml"),
            "implement",
            "workflow.nodes[1].prompt",
        )
        self.assertIn('"plan_summary": "summary"', rendered)
        self.assertIn('"nested": {', rendered)

    def test_downstream_can_read_runtime_context(self):
        node = {
            "id": "check",
            "input_map": {"latest_impl": "context.runtime.latest_impl"},
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
            "input_map_parts": {"plan_output": ("outputs", "plan")},
        }
        runtime_state = {
            "context": {"defaults": {}, "runtime": {}},
            "outputs": {"plan": {"pass": True, "plan_summary": "summary"}},
        }

        prompt_inputs = module.build_prompt_inputs(node, runtime_state)
        self.assertEqual(prompt_inputs["plan_output"], runtime_state["outputs"]["plan"])


class HistoryTargetTests(unittest.TestCase):
    def test_ensure_history_list_creates_missing_path_and_returns_list(self):
        runtime_state = {"context": {"defaults": {}, "runtime": {}}, "outputs": {}}
        history = module.ensure_history_list(runtime_state, "context.runtime.review_history")
        self.assertEqual(history, [])
        self.assertIs(history, runtime_state["context"]["runtime"]["review_history"])

    def test_ensure_history_list_rejects_non_list_target(self):
        runtime_state = {"context": {"defaults": {}, "runtime": {"review_history": {}}}, "outputs": {}}
        with self.assertRaisesRegex(RuntimeError, "History target must be array"):
            module.ensure_history_list(runtime_state, "context.runtime.review_history")


class PromptRenderingTests(PatchedYamlMixin, unittest.TestCase):
    def _render(
        self,
        prompt: str,
        prompt_inputs: dict | None = None,
        config_path: str | None = None,
        node_id: str = "node_a",
        prompt_field: str = "workflow.nodes[1].prompt",
    ) -> str:
        return module.render_prompt(
            prompt,
            prompt_inputs or {},
            config_path or str(ROOT / "presets" / "implement_loop.yaml"),
            node_id,
            prompt_field,
        )

    def test_render_prompt_without_include_keeps_inputs_behavior(self):
        rendered = self._render(
            "Spec={{ inputs.spec }}, User={{ inputs.user_instruction }}",
            {"spec": "s", "user_instruction": "u"},
        )
        self.assertEqual(rendered, "Spec=s, User=u")

    def test_render_prompt_supports_bracket_lookup_for_non_identifier_input_keys(self):
        rendered = self._render(
            'items={{ inputs.items }} foo_bar={{ inputs["foo-bar"] }}',
            {"items": ["x"], "foo-bar": "ok"},
        )
        self.assertIn('items=[\n  "x"\n]', rendered)
        self.assertIn("foo_bar=ok", rendered)

    def test_render_prompt_keeps_raw_block_content_literal(self):
        rendered = self._render(
            "{% raw %}{{ inputs.example }}{% endraw %}",
            {"example": "value"},
        )
        self.assertEqual(rendered, "{{ inputs.example }}")

    def test_render_prompt_supports_inputs_expressions_with_filters(self):
        rendered = self._render(
            "{{ inputs.name | default('fallback') }}",
            {},
        )
        self.assertEqual(rendered, "fallback")

    def test_render_prompt_default_handles_missing_key_named_like_dict_attribute(self):
        rendered = self._render(
            "{{ inputs.items | default([]) }}",
            {},
        )
        self.assertEqual(rendered, "[]")

    def test_render_prompt_renders_multiple_includes_and_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = base / "presets" / "flow.yaml"
            p1 = base / "presets" / "prompts" / "a.md"
            p2 = base / "presets" / "prompts" / "b.md"
            cfg.parent.mkdir(parents=True, exist_ok=True)
            p1.parent.mkdir(parents=True, exist_ok=True)
            p1.write_text("A", encoding="utf-8")
            p2.write_text("B", encoding="utf-8")
            cfg.write_text("{}", encoding="utf-8")

            rendered = self._render(
                '{{ prompt_file("./prompts/a.md") }} / {{ prompt_file("./prompts/b.md") }} / {{ inputs.k }}',
                {"k": "V"},
                str(cfg),
            )

        self.assertEqual(rendered, "A / B / V")

    def test_render_prompt_repeated_include_path_is_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = base / "preset.yaml"
            include = base / "prompts" / "same.md"
            include.parent.mkdir(parents=True, exist_ok=True)
            include.write_text("SAME", encoding="utf-8")
            cfg.write_text("{}", encoding="utf-8")

            rendered = self._render(
                '{{ prompt_file("./prompts/same.md") }} + {{ prompt_file("./prompts/same.md") }}',
                {},
                str(cfg),
            )

        self.assertEqual(rendered, "SAME + SAME")

    def test_render_prompt_fails_for_invalid_helper_calls(self):
        with self.assertRaisesRegex(RuntimeError, "missing 1 required positional argument"):
            self._render("{{ prompt_file() }}")

        with self.assertRaisesRegex(RuntimeError, "non-empty relative path"):
            self._render('{{ prompt_file("") }}')

        with self.assertRaisesRegex(RuntimeError, "expects string path, got int"):
            self._render("{{ prompt_file(123) }}")

    def test_render_prompt_fails_for_absolute_and_missing_include_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            abs_path = Path(tmp) / "x.md"
            abs_path.write_text("x", encoding="utf-8")
            config_path = str(Path(tmp) / "flow.yaml")
            Path(config_path).write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "only supports relative path"):
                self._render('{{ prompt_file("' + str(abs_path) + '") }}', {}, config_path)

            with self.assertRaisesRegex(RuntimeError, "file not found: ./missing.md"):
                self._render('{{ prompt_file("./missing.md") }}', {}, config_path)

    def test_render_prompt_fails_when_include_unreadable(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = str(Path(tmp) / "flow.yaml")
            Path(config_path).write_text("{}", encoding="utf-8")
            with patch.object(module, "read_text", side_effect=PermissionError("denied")):
                with self.assertRaisesRegex(RuntimeError, "cannot read file: ./x.md"):
                    self._render('{{ prompt_file("./x.md") }}', {}, config_path)

    def test_render_prompt_allows_parent_segment_relative_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = root / "presets" / "workflow" / "flow.yaml"
            include = root / "presets" / "shared" / "snippet.md"
            cfg.parent.mkdir(parents=True, exist_ok=True)
            include.parent.mkdir(parents=True, exist_ok=True)
            include.write_text("ok", encoding="utf-8")
            cfg.write_text("{}", encoding="utf-8")

            rendered = self._render(
                '{{ prompt_file("../shared/snippet.md") }}',
                {},
                str(cfg),
            )

        self.assertEqual(rendered, "ok")

    def test_render_prompt_keeps_json_text_semantics_for_non_string_inputs(self):
        rendered = self._render(
            "obj={{ inputs.obj }} arr={{ inputs.arr }} flag={{ inputs.flag }}",
            {"obj": {"k": 1}, "arr": [1, 2], "flag": True},
        )
        self.assertIn('"k": 1', rendered)
        self.assertIn("[\n  1,\n  2\n]", rendered)
        self.assertIn("flag=true", rendered)
        self.assertNotIn("'k': 1", rendered)

    def test_render_prompt_fails_for_missing_inputs_path_with_location(self):
        with self.assertRaisesRegex(RuntimeError, "workflow.nodes\\[1\\]\\.prompt"):
            self._render(
                "{{ inputs.missing }}",
                {},
                str(ROOT / "presets" / "implement_loop.yaml"),
                "n_missing",
                "workflow.nodes[1].prompt",
            )

    def test_render_prompt_fails_for_syntax_and_undefined_with_location(self):
        with self.assertRaisesRegex(RuntimeError, "workflow.nodes\\[1\\]\\.prompt"):
            self._render("{{ inputs.a ", {"a": "x"}, node_id="n1")
        with self.assertRaisesRegex(RuntimeError, "node_id=n2"):
            self._render("{{ not_defined }}", {}, node_id="n2")

    def test_render_prompt_does_not_second_pass_render_included_template_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = root / "flow.yaml"
            include = root / "prompts" / "tmpl.md"
            include.parent.mkdir(parents=True, exist_ok=True)
            include.write_text("{{ inputs.name }}", encoding="utf-8")
            cfg.write_text("{}", encoding="utf-8")

            rendered = self._render(
                '{{ prompt_file("./prompts/tmpl.md") }}',
                {"name": "Alice"},
                str(cfg),
            )

        self.assertEqual(rendered, "{{ inputs.name }}")


class PromptPathResolutionWorkflowTests(PatchedYamlMixin, unittest.TestCase):
    def _write_workflow_config(self, config_path: Path, project_root: Path) -> None:
        payload = {
            "version": 1,
            "run": {
                "project_root": str(project_root),
                "state_dir": ".codex-loop-state",
                "max_steps": 1,
            },
            "executor": {"cmd": ["codex", "exec", "--skip-git-repo-check"]},
            "context": {"defaults": {"k": "v"}},
            "workflow": {
                "start": "n1",
                "nodes": [
                    {
                        "id": "n1",
                        "prompt": '{{ prompt_file("./prompts/x.md") }} {{ inputs.k }}',
                        "input_map": {"k": "context.defaults.k"},
                        "on_success": "END",
                        "on_failure": "END",
                    }
                ],
            },
        }
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(payload), encoding="utf-8")

    def test_include_resolution_is_consistent_across_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "configs" / "wf.yaml"
            include = root / "configs" / "prompts" / "x.md"
            project_root = root / "project"
            include.parent.mkdir(parents=True, exist_ok=True)
            project_root.mkdir(parents=True, exist_ok=True)
            include.write_text("FROM_INCLUDE", encoding="utf-8")
            self._write_workflow_config(config_path, project_root)

            captured_prompts: list[str] = []

            def fake_codex_exec(
                project_root: str,
                executor_cmd: list[str],
                prompt: str,
                out_file: str,
                task_log_dir: str,
                node_id: str,
                step: int,
                attempt: int,
            ) -> str:
                captured_prompts.append(prompt)
                Path(out_file).write_text('{"pass": true}', encoding="utf-8")
                log_path = Path(task_log_dir) / "ok.log"
                log_path.write_text("ok", encoding="utf-8")
                return str(log_path)

            original_cwd = Path.cwd()
            cwd_a = root / "cwd_a"
            cwd_b = root / "cwd_b"
            cwd_a.mkdir(parents=True, exist_ok=True)
            cwd_b.mkdir(parents=True, exist_ok=True)
            try:
                with self.patch_yaml(), patch.object(module, "run_codex_exec", side_effect=fake_codex_exec):
                    os.chdir(cwd_a)
                    module.run_workflow(str(config_path), {})
                    os.chdir(cwd_b)
                    module.run_workflow(str(config_path), {})
            finally:
                os.chdir(original_cwd)

            self.assertEqual(len(captured_prompts), 2)
            self.assertEqual(captured_prompts[0], captured_prompts[1])

    def test_include_resolution_uses_config_dir_not_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "configs" / "wf.yaml"
            include = root / "configs" / "prompts" / "x.md"
            include.parent.mkdir(parents=True, exist_ok=True)
            include.write_text("CFG_DIR_CONTENT", encoding="utf-8")

            project_root = root / "different_project_root"
            project_root.mkdir(parents=True, exist_ok=True)
            self._write_workflow_config(config_path, project_root)

            prompts: list[str] = []

            def fake_codex_exec(
                project_root: str,
                executor_cmd: list[str],
                prompt: str,
                out_file: str,
                task_log_dir: str,
                node_id: str,
                step: int,
                attempt: int,
            ) -> str:
                prompts.append(prompt)
                Path(out_file).write_text('{"pass": true}', encoding="utf-8")
                log_path = Path(task_log_dir) / "ok.log"
                log_path.write_text("ok", encoding="utf-8")
                return str(log_path)

            with self.patch_yaml(), patch.object(module, "run_codex_exec", side_effect=fake_codex_exec):
                module.run_workflow(str(config_path), {})

            self.assertEqual(len(prompts), 1)
            self.assertIn("CFG_DIR_CONTENT", prompts[0])


class RouteBindingRuntimeTests(PatchedYamlMixin, WorkflowTestFactoryMixin, unittest.TestCase):
    def test_run_workflow_applies_route_bindings_and_keeps_outputs_by_node_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = self.write_workflow_config(
                tmp_path,
                project_root=tmp_path,
                max_steps=6,
                defaults={"user_instruction": "first pass", "spec": "s"},
                start="implement_first",
                nodes=[
                    {
                        "id": "implement_first",
                        "prompt": "implement_first",
                        "input_map": {"instruction": "context.defaults.user_instruction"},
                        "on_success": "check",
                        "on_failure": "END",
                        "route_bindings": {
                            "success": {"context.runtime.latest_impl": "outputs.implement_first"}
                        },
                    },
                    {
                        "id": "check",
                        "prompt": "check",
                        "input_map": {"latest_impl": "context.runtime.latest_impl"},
                        "on_success": "END",
                        "on_failure": "implement_loop",
                        "route_bindings": {
                            "failure": {"context.runtime.latest_check": "outputs.check"}
                        },
                    },
                    {
                        "id": "implement_loop",
                        "prompt": "implement_loop",
                        "input_map": {"latest_check": "context.runtime.latest_check"},
                        "on_success": "check",
                        "on_failure": "END",
                        "route_bindings": {
                            "success": {"context.runtime.latest_impl": "outputs.implement_loop"}
                        },
                    },
                ],
            )

            def payload_for_call(*, node_id: str, step: int, attempt: int, prompt: str):
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

            with (
                self.patch_yaml(),
                patch.object(module, "run_codex_exec", side_effect=self.make_fake_codex_exec(payload_for_call)),
            ):
                summary = module.run_workflow(str(config_path), {})

            self.assertEqual(summary["status"], "completed")
            self.assertEqual(summary["final_node"], "END")
            self.assertIn("implement_first", summary["outputs"])
            self.assertIn("implement_loop", summary["outputs"])
            self.assertIn("check", summary["outputs"])

            runtime_state = json.loads(
                (tmp_path / ".codex-loop-state" / "runtime_state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                runtime_state["context"]["runtime"]["latest_impl"]["node"], "implement_loop"
            )
            self.assertEqual(
                runtime_state["context"]["runtime"]["latest_check"]["node"], "check"
            )

    def test_run_workflow_collects_output_history_for_node(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = self.write_workflow_config(
                tmp_path,
                project_root=tmp_path,
                max_steps=3,
                defaults={},
                start="review",
                nodes=[
                    {
                        "id": "review",
                        "prompt": "review",
                        "input_map": {},
                        "collect_history_to": "context.runtime.review_history",
                        "on_success": "END",
                        "on_failure": "review",
                    }
                ],
            )

            def payload_for_call(*, node_id: str, step: int, attempt: int, prompt: str):
                payloads = [
                    {"pass": False, "issues": ["a"]},
                    {"pass": False, "issues": ["a", "b"]},
                    {"pass": True, "issues": []},
                ]
                return payloads[attempt - 1]

            with (
                self.patch_yaml(),
                patch.object(module, "run_codex_exec", side_effect=self.make_fake_codex_exec(payload_for_call)),
            ):
                summary = module.run_workflow(str(config_path), {})

            self.assertEqual(summary["status"], "completed")
            runtime_state = json.loads(
                (tmp_path / ".codex-loop-state" / "runtime_state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                runtime_state["context"]["runtime"]["review_history"],
                [
                    {"pass": False, "issues": ["a"]},
                    {"pass": False, "issues": ["a", "b"]},
                    {"pass": True, "issues": []},
                ],
            )

    def test_run_workflow_initializes_history_before_first_prompt_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = self.write_workflow_config(
                tmp_path,
                project_root=tmp_path,
                max_steps=1,
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

            def payload_for_call(*, node_id: str, step: int, attempt: int, prompt: str):
                captured_prompts.append(prompt)
                return {"pass": True, "issues": []}

            with (
                self.patch_yaml(),
                patch.object(module, "run_codex_exec", side_effect=self.make_fake_codex_exec(payload_for_call)),
            ):
                summary = module.run_workflow(str(config_path), {})

            self.assertEqual(summary["status"], "completed")
            self.assertEqual(len(captured_prompts), 1)
            runtime_state = json.loads(
                (tmp_path / ".codex-loop-state" / "runtime_state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                runtime_state["context"]["runtime"]["review_history"],
                [{"pass": True, "issues": []}],
            )


class MaxStepsTests(PatchedYamlMixin, unittest.TestCase):
    def test_run_workflow_stops_when_reaching_max_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config = {
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

            def fake_codex_exec(
                project_root: str,
                executor_cmd: list[str],
                prompt: str,
                out_file: str,
                task_log_dir: str,
                node_id: str,
                step: int,
                attempt: int,
            ) -> str:
                Path(out_file).write_text('{"pass": true, "node": "loop"}', encoding="utf-8")
                log_path = Path(task_log_dir) / f"fake_{step}_{attempt}.log"
                log_path.write_text("ok", encoding="utf-8")
                return str(log_path)

            with (
                self.patch_yaml(),
                patch.object(module, "run_codex_exec", side_effect=fake_codex_exec),
                self.assertRaisesRegex(RuntimeError, "Reached max_steps without END: 2"),
            ):
                module.run_workflow(str(config_path), {})


class BuiltinPresetWiringTests(unittest.TestCase):
    def test_reviewer_loop_is_review_only_and_tracks_all_history(self):
        config = module.load_config(str(ROOT / "presets" / "reviewer_loop.yaml"), {})
        nodes = {node["id"]: node for node in config["workflow"]["nodes"]}

        self.assertEqual(config["workflow"]["start"], "bug_reviwer")
        self.assertIn("bug_reviwer", nodes)
        self.assertEqual(set(nodes.keys()), {"bug_reviwer"})
        self.assertNotIn("bootstrap", nodes)
        self.assertNotIn("fix", nodes)

        review = nodes["bug_reviwer"]
        self.assertEqual(review["collect_history_to"], "context.runtime.bug_review_history")
        self.assertEqual(review["on_failure"], "bug_reviwer")
        self.assertEqual(review["on_success"], "END")
        self.assertEqual(
            review["input_map"]["bug_review_history"],
            "context.runtime.bug_review_history",
        )
        self.assertEqual(review["route_bindings"], {"success": {}, "failure": {}})

    def test_implement_loop_wires_latest_impl_into_checker(self):
        config = module.load_config(str(ROOT / "presets" / "implement_loop.yaml"), {})
        nodes = {node["id"]: node for node in config["workflow"]["nodes"]}

        self.assertEqual(
            nodes["implement_first"]["route_bindings"]["success"]["context.runtime.latest_impl"],
            "outputs.implement_first",
        )
        self.assertEqual(
            nodes["check"]["input_map"]["latest_impl"],
            "context.runtime.latest_impl",
        )

    def test_refactor_loop_uses_arch_reviwer_and_refactor_only(self):
        config = module.load_config(str(ROOT / "presets" / "refactor_loop.yaml"), {})
        nodes = {node["id"]: node for node in config["workflow"]["nodes"]}

        self.assertEqual(config["workflow"]["start"], "arch_reviwer")
        self.assertIn("arch_reviwer", nodes)
        self.assertEqual(set(nodes.keys()), {"arch_reviwer"})
        self.assertNotIn("bootstrap", nodes)
        self.assertNotIn("fix", nodes)
        self.assertNotIn("latest_refactor", config["context"]["defaults"])

        arch_review = nodes["arch_reviwer"]
        self.assertEqual(arch_review["collect_history_to"], "context.runtime.arch_review_history")
        self.assertEqual(arch_review["on_failure"], "arch_reviwer")
        self.assertEqual(arch_review["on_success"], "END")
        self.assertNotIn("latest_refactor", arch_review["input_map"])
        self.assertEqual(
            arch_review["input_map"]["arch_review_history"],
            "context.runtime.arch_review_history",
        )
        self.assertEqual(arch_review["route_bindings"], {"success": {}, "failure": {}})


class CliHelperTests(unittest.TestCase):
    def test_parse_context_overrides_last_value_wins(self):
        overrides = module.parse_context_overrides(
            [["spec", "v1"], ["spec", "v2"], ["user_instruction", "do it"]]
        )
        self.assertEqual(overrides["spec"], "v2")
        self.assertEqual(overrides["user_instruction"], "do it")

    def test_parse_context_overrides_rejects_nested_key(self):
        with self.assertRaisesRegex(RuntimeError, "cannot contain"):
            module.parse_context_overrides([["a.b", "x"]])

    def test_resolve_preset_path_resolves_name_into_presets_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            resolved = module.resolve_preset_path(tmp_path, "implement_loop")
            self.assertEqual(resolved, (tmp_path / "presets" / "implement_loop.yaml").resolve())

    def test_resolve_preset_path_accepts_explicit_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            resolved = module.resolve_preset_path(tmp_path, "configs/x.yaml")
            self.assertEqual(resolved, (tmp_path / "configs" / "x.yaml").resolve())


if __name__ == "__main__":
    unittest.main()
