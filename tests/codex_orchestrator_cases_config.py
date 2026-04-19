import tempfile
import unittest
from pathlib import Path
from typing import Any

from tests.codex_orchestrator_test_support import (
    ROOT,
    TEST_CONFIG_RELATIVE_PATH,
    PatchedYamlMixin,
    WorkflowTestFactoryMixin,
    module,
    write_json_config,
)


class ConfigValidationTests(PatchedYamlMixin, WorkflowTestFactoryMixin, unittest.TestCase):
    def _write_config(self, base_dir: Path, payload: dict[str, Any]) -> Path:
        return write_json_config(base_dir / TEST_CONFIG_RELATIVE_PATH, payload)

    def _minimal_valid_config(self, project_root: str) -> dict[str, Any]:
        return self.build_workflow_payload(
            run_args={"project_root": project_root, "max_steps": 3},
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
            payload["workflow"]["nodes"][0]["route_bindings"] = {"success": {"outputs.latest_impl": "outputs.n1"}}
            config_path = self._write_config(tmp_path, payload)

            with (
                self.patch_yaml(),
                self.assertRaisesRegex(RuntimeError, "must start with context.runtime."),
            ):
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

            with (
                self.patch_yaml(),
                self.assertRaisesRegex(RuntimeError, "cannot be object or array"),
            ):
                module.load_config(str(config_path), {})

    def test_load_config_rejects_non_string_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            payload["workflow"]["nodes"][0]["prompt"] = {"bad": "type"}
            config_path = self._write_config(tmp_path, payload)

            with (
                self.patch_yaml(),
                self.assertRaisesRegex(RuntimeError, "workflow.nodes\\[1\\]\\.prompt"),
            ):
                module.load_config(str(config_path), {})

    def test_load_config_rejects_empty_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            payload["workflow"]["nodes"][0]["prompt"] = "   "
            config_path = self._write_config(tmp_path, payload)

            with (
                self.patch_yaml(),
                self.assertRaisesRegex(RuntimeError, "workflow.nodes\\[1\\]\\.prompt"),
            ):
                module.load_config(str(config_path), {})

    def test_load_config_rejects_collect_history_to_outside_runtime_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            payload["workflow"]["nodes"][0]["collect_history_to"] = "outputs.review_history"
            config_path = self._write_config(tmp_path, payload)

            with (
                self.patch_yaml(),
                self.assertRaisesRegex(RuntimeError, "collect_history_to must start"),
            ):
                module.load_config(str(config_path), {})

    def test_load_config_compiles_input_and_route_binding_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            payload["workflow"]["nodes"][0]["route_bindings"] = {"success": {"context.runtime.latest_impl": "outputs.n1"}}
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

    def test_load_config_compiles_success_next_node_from_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            payload["workflow"]["nodes"][0]["success_next_node_from"] = "context.runtime.next_node"
            config_path = self._write_config(tmp_path, payload)

            with self.patch_yaml():
                config = module.load_config(str(config_path), {})

            node = config["workflow"]["nodes"][0]
            self.assertEqual(node["success_next_node_from"], "context.runtime.next_node")
            self.assertEqual(
                node["compiled"]["success_next_node_source"]["source_parts"],
                ("context", "runtime", "next_node"),
            )

    def test_load_config_rejects_invalid_success_next_node_from_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            payload["workflow"]["nodes"][0]["success_next_node_from"] = "runtime.next_node"
            config_path = self._write_config(tmp_path, payload)

            with self.patch_yaml(), self.assertRaisesRegex(RuntimeError, "success_next_node_from"):
                module.load_config(str(config_path), {})

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

            with (
                self.patch_yaml(),
                self.assertRaisesRegex(RuntimeError, "run.max_steps must be positive integer"),
            ):
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

            with (
                self.patch_yaml(),
                self.assertRaisesRegex(
                    RuntimeError,
                    "route_bindings has unsupported keys: 1",
                ),
            ):
                module.load_config(str(config_path), {})

    def test_load_config_rejects_non_object_context_even_if_falsey(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            payload["context"] = []
            config_path = self._write_config(tmp_path, payload)

            with (
                self.patch_yaml(),
                self.assertRaisesRegex(RuntimeError, "'context' must be object"),
            ):
                module.load_config(str(config_path), {})

    def test_load_config_rejects_non_object_executor_even_if_falsey(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            payload["executor"] = ""
            config_path = self._write_config(tmp_path, payload)

            with (
                self.patch_yaml(),
                self.assertRaisesRegex(RuntimeError, "'executor' must be object"),
            ):
                module.load_config(str(config_path), {})

    def test_load_config_composes_imported_and_local_nodes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self.build_workflow_payload(
                run_args={"project_root": tmp, "max_steps": 3},
                defaults={"user_instruction": "local only"},
                start="doc_reviwer",
                nodes=[
                    {
                        "id": "doc_fix",
                        "prompt": "fix",
                        "input_map": {"history": "context.runtime.doc_review_history"},
                        "on_success": "doc_reviwer",
                        "on_failure": "END",
                    }
                ],
            )
            payload["workflow"]["imports"] = [{"preset": "doc_reviewer_loop"}]
            payload["workflow"]["node_overrides"] = {"doc_reviwer": {"on_failure": "doc_fix"}}
            config_path = self._write_config(tmp_path, payload)

            config = module.load_config(str(config_path), {})

            nodes = {node["id"]: node for node in config["workflow"]["nodes"]}
            self.assertEqual(config["workflow"]["start"], "doc_reviwer")
            self.assertEqual(set(nodes), {"doc_reviwer", "doc_fix"})
            self.assertEqual(nodes["doc_reviwer"]["on_failure"], "doc_fix")
            self.assertEqual(nodes["doc_fix"]["on_success"], "doc_reviwer")

    def test_load_config_processes_multiple_imports_in_declaration_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self.build_workflow_payload(
                run_args={"project_root": tmp, "max_steps": 3},
                defaults={"user_instruction": "local only"},
                start="bug_reviwer",
                nodes=[],
            )
            payload["workflow"]["imports"] = [
                {"preset": "reviewer_loop"},
                {"preset": "refactor_loop"},
            ]
            config_path = self._write_config(tmp_path, payload)

            config = module.load_config(str(config_path), {})
            node_ids = [node["id"] for node in config["workflow"]["nodes"]]
            self.assertEqual(node_ids, ["bug_reviwer", "arch_reviwer"])

    def test_load_config_treats_imports_only_and_empty_nodes_as_equivalent(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload_without_nodes = self.build_workflow_payload(
                run_args={"project_root": tmp, "max_steps": 3},
                defaults={"user_instruction": "local only"},
                start="doc_reviwer",
                nodes=[],
            )
            payload_without_nodes["workflow"] = {
                "start": "doc_reviwer",
                "imports": [{"preset": "doc_reviewer_loop"}],
            }
            config_path_a = self._write_config(tmp_path / "a", payload_without_nodes)

            payload_with_empty_nodes = self.build_workflow_payload(
                run_args={"project_root": tmp, "max_steps": 3},
                defaults={"user_instruction": "local only"},
                start="doc_reviwer",
                nodes=[],
            )
            payload_with_empty_nodes["workflow"]["imports"] = [{"preset": "doc_reviewer_loop"}]
            payload_with_empty_nodes["workflow"]["nodes"] = []
            config_path_b = self._write_config(tmp_path / "b", payload_with_empty_nodes)

            config_a = module.load_config(str(config_path_a), {})
            config_b = module.load_config(str(config_path_b), {})
            self.assertEqual(config_a["workflow"], config_b["workflow"])

    def test_load_config_rejects_composed_workflow_without_explicit_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self.build_workflow_payload(
                run_args={"project_root": tmp, "max_steps": 3},
                defaults={"user_instruction": "local only"},
                start="doc_reviwer",
                nodes=[],
            )
            payload["workflow"] = {
                "imports": [{"preset": "doc_reviewer_loop"}],
                "nodes": [],
            }
            config_path = self._write_config(tmp_path, payload)

            with self.assertRaisesRegex(RuntimeError, "workflow.start"):
                module.load_config(str(config_path), {})

    def test_load_config_rejects_empty_composed_node_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self.build_workflow_payload(
                run_args={"project_root": tmp, "max_steps": 3},
                defaults={"spec": "local"},
                start="n1",
                nodes=[],
            )
            config_path = self._write_config(tmp_path, payload)

            with self.assertRaisesRegex(RuntimeError, "workflow composition produced empty node set"):
                module.load_config(str(config_path), {})

    def test_load_config_override_updates_routes_with_route_level_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self.build_workflow_payload(
                run_args={"project_root": tmp, "max_steps": 3},
                defaults={"spec": "local"},
                start="check",
                nodes=[],
            )
            payload["workflow"]["imports"] = [{"preset": "implement_loop"}]
            payload["workflow"]["node_overrides"] = {
                "check": {
                    "on_success": "implement_loop",
                    "on_failure": "END",
                    "route_bindings": {
                        "success": {
                            "context.runtime.override_success": "outputs.check.control",
                        }
                    },
                }
            }
            config_path = self._write_config(tmp_path, payload)

            config = module.load_config(str(config_path), {})
            check = {node["id"]: node for node in config["workflow"]["nodes"]}["check"]
            self.assertEqual(check["on_success"], "implement_loop")
            self.assertEqual(check["on_failure"], "END")
            self.assertEqual(
                check["route_bindings"]["success"],
                {"context.runtime.override_success": "outputs.check.control"},
            )
            self.assertEqual(
                check["route_bindings"]["failure"],
                {"context.runtime.latest_check": "outputs.check.control"},
            )

    def test_load_config_override_updates_success_next_node_from_for_imported_node(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self.build_workflow_payload(
                run_args={"project_root": tmp, "max_steps": 3},
                defaults={"user_instruction": "local only"},
                start="doc_reviwer",
                nodes=[],
            )
            payload["workflow"]["imports"] = [{"preset": "doc_reviewer_loop"}]
            payload["workflow"]["node_overrides"] = {
                "doc_reviwer": {"success_next_node_from": "context.runtime.doc_review_next_node"}
            }
            config_path = self._write_config(tmp_path, payload)

            config = module.load_config(str(config_path), {})
            review = {node["id"]: node for node in config["workflow"]["nodes"]}["doc_reviwer"]
            self.assertEqual(review["success_next_node_from"], "context.runtime.doc_review_next_node")
            self.assertEqual(
                review["compiled"]["success_next_node_source"]["source_parts"],
                ("context", "runtime", "doc_review_next_node"),
            )

    def test_load_config_rejects_invalid_override_success_next_node_from_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self.build_workflow_payload(
                run_args={"project_root": tmp, "max_steps": 3},
                defaults={"user_instruction": "local only"},
                start="doc_reviwer",
                nodes=[],
            )
            payload["workflow"]["imports"] = [{"preset": "doc_reviewer_loop"}]
            payload["workflow"]["node_overrides"] = {"doc_reviwer": {"success_next_node_from": "runtime.next_node"}}
            config_path = self._write_config(tmp_path, payload)

            with self.assertRaisesRegex(RuntimeError, "success_next_node_from"):
                module.load_config(str(config_path), {})

    def test_load_config_rejects_unknown_workflow_root_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self._minimal_valid_config(project_root=tmp)
            payload["workflow"]["import"] = [{"preset": "doc_reviewer_loop"}]
            config_path = self._write_config(tmp_path, payload)

            with self.assertRaisesRegex(RuntimeError, "workflow has unsupported keys: import"):
                module.load_config(str(config_path), {})

    def test_load_config_rejects_unknown_import_entry_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self.build_workflow_payload(
                run_args={"project_root": tmp, "max_steps": 3},
                defaults={"user_instruction": "local only"},
                start="doc_reviwer",
                nodes=[],
            )
            payload["workflow"]["imports"] = [{"preset": "doc_reviewer_loop", "extra": "x"}]
            config_path = self._write_config(tmp_path, payload)

            with self.assertRaisesRegex(RuntimeError, "workflow.imports\\[1\\] has unsupported keys: extra"):
                module.load_config(str(config_path), {})

    def test_load_config_rejects_unknown_node_override_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self.build_workflow_payload(
                run_args={"project_root": tmp, "max_steps": 3},
                defaults={"user_instruction": "local only"},
                start="doc_reviwer",
                nodes=[],
            )
            payload["workflow"]["imports"] = [{"preset": "doc_reviewer_loop"}]
            payload["workflow"]["node_overrides"] = {"doc_reviwer": {"prompt": "not allowed"}}
            config_path = self._write_config(tmp_path, payload)

            with self.assertRaisesRegex(
                RuntimeError,
                "workflow.node_overrides.doc_reviwer has unsupported keys: prompt",
            ):
                module.load_config(str(config_path), {})

    def test_load_config_rejects_non_string_node_override_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = tmp_path / TEST_CONFIG_RELATIVE_PATH
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                """
version: 1
run:
  project_root: .
  state_dir: .codex-loop-state
  max_steps: 3
executor:
  cmd: ["codex", "exec", "--skip-git-repo-check"]
context:
  defaults:
    user_instruction: "local only"
workflow:
  start: doc_reviwer
  imports:
    - preset: doc_reviewer_loop
  node_overrides:
    1:
      on_success: END
  nodes: []
""".strip(),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "workflow.node_overrides keys must be non-empty strings"):
                module.load_config(str(config_path), {})

    def test_load_config_imports_only_workflow_nodes_without_inheriting_top_level_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self.build_workflow_payload(
                run_args={
                    "project_root": tmp,
                    "max_steps": 9,
                    "executor_cmd": ["custom", "exec"],
                },
                defaults={"local_only": "value"},
                start="doc_reviwer",
                nodes=[],
            )
            payload["workflow"]["imports"] = [{"preset": "doc_reviewer_loop"}]
            config_path = self._write_config(tmp_path, payload)

            config = module.load_config(str(config_path), {})
            self.assertEqual(config["run"]["max_steps"], 9)
            self.assertEqual(config["executor"]["cmd"], ["custom", "exec"])
            self.assertEqual(config["context"]["defaults"]["local_only"], "value")
            self.assertNotIn("user_instruction", config["context"]["defaults"])

    def test_load_config_rejects_unknown_import_preset_identifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self.build_workflow_payload(
                run_args={"project_root": tmp, "max_steps": 3},
                defaults={"user_instruction": "local only"},
                start="doc_reviwer",
                nodes=[],
            )
            payload["workflow"]["imports"] = [{"preset": "missing_preset"}]
            config_path = self._write_config(tmp_path, payload)

            with self.assertRaisesRegex(
                RuntimeError,
                "workflow.imports\\[1\\]\\.preset invalid: Unknown preset identifier: 'missing_preset'",
            ):
                module.load_config(str(config_path), {})

    def test_load_config_rejects_path_like_import_preset_identifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self.build_workflow_payload(
                run_args={"project_root": tmp, "max_steps": 3},
                defaults={"user_instruction": "local only"},
                start="doc_reviwer",
                nodes=[],
            )
            payload["workflow"]["imports"] = [{"preset": "presets/doc_reviewer_loop.yaml"}]
            config_path = self._write_config(tmp_path, payload)

            with self.assertRaisesRegex(RuntimeError, "expects a preset identifier"):
                module.load_config(str(config_path), {})

    def test_load_config_rejects_override_target_when_node_is_not_imported(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self.build_workflow_payload(
                run_args={"project_root": tmp, "max_steps": 3},
                defaults={"user_instruction": "local only"},
                start="doc_reviwer",
                nodes=[
                    {
                        "id": "local_only_node",
                        "prompt": "x",
                        "input_map": {},
                        "on_success": "END",
                        "on_failure": "END",
                    }
                ],
            )
            payload["workflow"]["imports"] = [{"preset": "doc_reviewer_loop"}]
            payload["workflow"]["node_overrides"] = {"local_only_node": {"on_success": "END"}}
            config_path = self._write_config(tmp_path, payload)

            with self.assertRaisesRegex(RuntimeError, "target must be imported node id"):
                module.load_config(str(config_path), {})

    def test_load_config_rejects_override_target_when_node_does_not_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self.build_workflow_payload(
                run_args={"project_root": tmp, "max_steps": 3},
                defaults={"user_instruction": "local only"},
                start="doc_reviwer",
                nodes=[],
            )
            payload["workflow"]["imports"] = [{"preset": "doc_reviewer_loop"}]
            payload["workflow"]["node_overrides"] = {"missing_node": {"on_success": "END"}}
            config_path = self._write_config(tmp_path, payload)

            with self.assertRaisesRegex(RuntimeError, "target must be imported node id"):
                module.load_config(str(config_path), {})

    def test_load_config_rejects_nested_imports_in_imported_preset(self):
        nested_preset_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=ROOT / "presets",
                suffix=".yaml",
                encoding="utf-8",
                delete=False,
            ) as handle:
                handle.write(
                    """
version: 1
run:
  project_root: .
  state_dir: .codex-loop-state
  max_steps: 3
executor:
  cmd: ["codex", "exec", "--skip-git-repo-check"]
context:
  defaults:
    user_instruction: "local only"
workflow:
  start: doc_reviwer
  imports:
    - preset: doc_reviewer_loop
  nodes: []
""".strip()
                )
                nested_preset_path = Path(handle.name)

            preset_id = nested_preset_path.stem
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                payload = self.build_workflow_payload(
                    run_args={"project_root": tmp, "max_steps": 3},
                    defaults={"user_instruction": "local only"},
                    start="doc_reviwer",
                    nodes=[],
                )
                payload["workflow"]["imports"] = [{"preset": preset_id}]
                config_path = self._write_config(tmp_path, payload)

                with self.assertRaisesRegex(RuntimeError, "nested imports are not supported"):
                    module.load_config(str(config_path), {})
        finally:
            if nested_preset_path is not None and nested_preset_path.exists():
                nested_preset_path.unlink()

    def test_load_config_rejects_unknown_workflow_keys_in_imported_preset(self):
        nested_preset_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=ROOT / "presets",
                suffix=".yaml",
                encoding="utf-8",
                delete=False,
            ) as handle:
                handle.write(
                    """
version: 1
run:
  project_root: .
  state_dir: .codex-loop-state
  max_steps: 3
executor:
  cmd: ["codex", "exec", "--skip-git-repo-check"]
context:
  defaults:
    user_instruction: "local only"
workflow:
  start: doc_reviwer
  import: []
  nodes:
    - id: doc_reviwer
      prompt: "review"
      input_map: {}
      on_success: END
      on_failure: END
""".strip()
                )
                nested_preset_path = Path(handle.name)

            preset_id = nested_preset_path.stem
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                payload = self.build_workflow_payload(
                    run_args={"project_root": tmp, "max_steps": 3},
                    defaults={"user_instruction": "local only"},
                    start="doc_reviwer",
                    nodes=[],
                )
                payload["workflow"]["imports"] = [{"preset": preset_id}]
                config_path = self._write_config(tmp_path, payload)

                with self.assertRaisesRegex(RuntimeError, "workflow has unsupported keys: import"):
                    module.load_config(str(config_path), {})
        finally:
            if nested_preset_path is not None and nested_preset_path.exists():
                nested_preset_path.unlink()

    def test_load_config_rejects_duplicate_node_id_across_imports(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self.build_workflow_payload(
                run_args={"project_root": tmp, "max_steps": 3},
                defaults={"user_instruction": "local only"},
                start="doc_reviwer",
                nodes=[],
            )
            payload["workflow"]["imports"] = [
                {"preset": "doc_reviewer_loop"},
                {"preset": "doc_reviewer_loop"},
            ]
            config_path = self._write_config(tmp_path, payload)

            with self.assertRaisesRegex(RuntimeError, "Duplicate node id: doc_reviwer"):
                module.load_config(str(config_path), {})

    def test_load_config_rejects_duplicate_node_id_between_imported_and_local_nodes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = self.build_workflow_payload(
                run_args={"project_root": tmp, "max_steps": 3},
                defaults={"user_instruction": "local only"},
                start="doc_reviwer",
                nodes=[
                    {
                        "id": "doc_reviwer",
                        "prompt": "local duplicate",
                        "input_map": {},
                        "on_success": "END",
                        "on_failure": "END",
                    }
                ],
            )
            payload["workflow"]["imports"] = [{"preset": "doc_reviewer_loop"}]
            config_path = self._write_config(tmp_path, payload)

            with self.assertRaisesRegex(RuntimeError, "Duplicate node id: doc_reviwer"):
                module.load_config(str(config_path), {})
