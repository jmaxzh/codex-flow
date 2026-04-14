import importlib.util
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "codex_automation_loops.py"


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
    def _write_config(self, base_dir: Path, payload: dict):
        config_path = base_dir / module.CONFIG_FILE
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
            "context": {"static": {"spec": "ok"}},
            "workflow": {
                "start": "n1",
                "nodes": [
                    {
                        "id": "n1",
                        "prompt": "x",
                        "input_map": {"spec": "context.static.spec"},
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
                module.load_config(str(config_path))

    def test_load_config_fails_when_on_failure_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            del payload["workflow"]["nodes"][0]["on_failure"]
            config_path = self._write_config(tmp_path, payload)

            with self.patch_yaml(), self.assertRaisesRegex(RuntimeError, "on_failure"):
                module.load_config(str(config_path))

    def test_load_config_fails_when_node_id_is_reserved_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            payload["workflow"]["nodes"][0]["id"] = "END"
            payload["workflow"]["start"] = "END"
            config_path = self._write_config(tmp_path, payload)

            with self.patch_yaml(), self.assertRaisesRegex(RuntimeError, "reserved id: END"):
                module.load_config(str(config_path))


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
            "context": {"static": {}},
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
                "context": {"static": {}},
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
            config_path = tmp_path / module.CONFIG_FILE
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
                patch("pathlib.Path.cwd", return_value=tmp_path),
                self.assertRaisesRegex(RuntimeError, "Reached max_steps without END: 2"),
            ):
                module.run_workflow()


if __name__ == "__main__":
    unittest.main()
