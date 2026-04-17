import tempfile
import unittest
from pathlib import Path

from tests.codex_orchestrator_test_support import (
    PatchedYamlMixin,
    ROOT,
    TEST_CONFIG_RELATIVE_PATH,
    WorkflowTestFactoryMixin,
    module,
    write_json_config,
)

class ConfigValidationTests(PatchedYamlMixin, WorkflowTestFactoryMixin, unittest.TestCase):
    def _write_config(self, base_dir: Path, payload: dict) -> Path:
        return write_json_config(base_dir / TEST_CONFIG_RELATIVE_PATH, payload)

    def _minimal_valid_config(self, project_root: str) -> dict:
        return self.build_workflow_payload(
            project_root=project_root,
            max_steps=3,
            defaults={"spec": "ok"},
            start="n1",
            nodes=[
                {
                    "id": "n1",
                    "prompt": "x",
                    "input_map": {"spec": "context.defaults.spec"},
                    "on_success": "END",
                    "on_failure": "END",
                }
            ],
        )

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
            self.assertEqual(
                node["compiled"]["input_bindings"][0]["source_parts"],
                ("context", "defaults", "spec"),
            )
            self.assertEqual(
                node["compiled"]["route_bindings"]["success"][0]["source_parts"],
                ("outputs", "n1"),
            )

    def test_load_config_rejects_non_boolean_parse_output_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            payload["workflow"]["nodes"][0]["parse_output_json"] = "false"
            config_path = self._write_config(tmp_path, payload)

            with self.patch_yaml(), self.assertRaisesRegex(RuntimeError, "parse_output_json"):
                module.load_config(str(config_path), {})

    def test_load_config_resolves_relative_project_root_from_launch_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            launch_cwd = tmp_path / "worktree"
            launch_cwd.mkdir(parents=True, exist_ok=True)
            project_dir = launch_cwd / "target-project"
            project_dir.mkdir(parents=True, exist_ok=True)

            payload = self._minimal_valid_config(project_root="./target-project")
            config_path = self._write_config(tmp_path, payload)

            with self.patch_yaml():
                config = module.load_config(
                    str(config_path),
                    {},
                    str(launch_cwd),
                )

            self.assertEqual(config["run"]["project_root"], str(project_dir.resolve()))

    def test_load_config_rejects_boolean_max_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            payload["run"]["max_steps"] = True
            config_path = self._write_config(tmp_path, payload)

            with self.patch_yaml(), self.assertRaisesRegex(RuntimeError, "run.max_steps must be positive integer"):
                module.load_config(str(config_path), {})

    def test_load_config_reports_invalid_route_binding_keys_with_mixed_key_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            payload["workflow"]["nodes"][0]["route_bindings"] = {
                "success": {},
                1: {},
            }
            config_path = self._write_config(tmp_path, payload)

            with self.patch_yaml(), self.assertRaisesRegex(
                RuntimeError,
                "route_bindings has unsupported keys: 1",
            ):
                module.load_config(str(config_path), {})

    def test_load_config_rejects_non_object_context_even_if_falsey(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            payload["context"] = []
            config_path = self._write_config(tmp_path, payload)

            with self.patch_yaml(), self.assertRaisesRegex(RuntimeError, "'context' must be object"):
                module.load_config(str(config_path), {})

    def test_load_config_rejects_non_object_executor_even_if_falsey(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            payload["executor"] = ""
            config_path = self._write_config(tmp_path, payload)

            with self.patch_yaml(), self.assertRaisesRegex(RuntimeError, "'executor' must be object"):
                module.load_config(str(config_path), {})
