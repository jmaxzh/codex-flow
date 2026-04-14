import importlib.util
import json
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


class OutputContractTests(unittest.TestCase):
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

        rendered = module.render_prompt("Plan: {{inputs.plan_output}}", prompt_inputs)
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


class RouteBindingRuntimeTests(PatchedYamlMixin, unittest.TestCase):
    def test_run_workflow_applies_route_bindings_and_keeps_outputs_by_node_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config = {
                "version": 1,
                "run": {
                    "project_root": str(tmp_path),
                    "state_dir": ".codex-loop-state",
                    "max_steps": 6,
                },
                "executor": {"cmd": ["codex", "exec", "--skip-git-repo-check"]},
                "context": {"defaults": {"user_instruction": "first pass", "spec": "s"}},
                "workflow": {
                    "start": "implement_first",
                    "nodes": [
                        {
                            "id": "implement_first",
                            "prompt": "implement_first",
                            "input_map": {"instruction": "context.defaults.user_instruction"},
                            "on_success": "check",
                            "on_failure": "END",
                            "route_bindings": {
                                "success": {
                                    "context.runtime.latest_impl": "outputs.implement_first"
                                }
                            },
                        },
                        {
                            "id": "check",
                            "prompt": "check",
                            "input_map": {"latest_impl": "context.runtime.latest_impl"},
                            "on_success": "END",
                            "on_failure": "implement_loop",
                            "route_bindings": {
                                "failure": {
                                    "context.runtime.latest_check": "outputs.check"
                                }
                            },
                        },
                        {
                            "id": "implement_loop",
                            "prompt": "implement_loop",
                            "input_map": {"latest_check": "context.runtime.latest_check"},
                            "on_success": "check",
                            "on_failure": "END",
                            "route_bindings": {
                                "success": {
                                    "context.runtime.latest_impl": "outputs.implement_loop"
                                }
                            },
                        },
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
                Path(out_file).write_text(json.dumps(payload), encoding="utf-8")
                log_path = Path(task_log_dir) / f"fake_{step}_{attempt}.log"
                log_path.write_text("ok", encoding="utf-8")
                return str(log_path)

            with (
                self.patch_yaml(),
                patch.object(module, "run_codex_exec", side_effect=fake_codex_exec),
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
