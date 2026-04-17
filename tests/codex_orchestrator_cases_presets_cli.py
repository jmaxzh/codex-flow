import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.codex_orchestrator_test_support import ROOT, module

class BuiltinPresetWiringTests(unittest.TestCase):
    def assert_review_only_preset(
        self,
        *,
        preset_file: str,
        start_node: str,
        history_key: str,
        forbid_input_key: str | None = None,
        assert_default_missing: str | None = None,
    ) -> None:
        config = module.load_config(str(ROOT / "presets" / preset_file), {})
        nodes = {node["id"]: node for node in config["workflow"]["nodes"]}

        self.assertEqual(config["workflow"]["start"], start_node)
        self.assertIn(start_node, nodes)
        self.assertEqual(set(nodes.keys()), {start_node})
        self.assertNotIn("bootstrap", nodes)
        self.assertNotIn("fix", nodes)
        if assert_default_missing is not None:
            self.assertNotIn(assert_default_missing, config["context"]["defaults"])

        review = nodes[start_node]
        history_path = f"context.runtime.{history_key}"
        self.assertEqual(review["collect_history_to"], history_path)
        self.assertEqual(review["on_failure"], start_node)
        self.assertEqual(review["on_success"], "END")
        if forbid_input_key is not None:
            self.assertNotIn(forbid_input_key, review["input_map"])
        self.assertEqual(review["input_map"][history_key], history_path)
        self.assertEqual(review["route_bindings"], {"success": {}, "failure": {}})

    def test_reviewer_loop_is_review_only_and_tracks_all_history(self):
        self.assert_review_only_preset(
            preset_file="reviewer_loop.yaml",
            start_node="bug_reviwer",
            history_key="bug_review_history",
        )

    def test_implement_loop_marks_implement_nodes_as_plain_text_output(self):
        config = module.load_config(str(ROOT / "presets" / "implement_loop.yaml"), {})
        nodes = {node["id"]: node for node in config["workflow"]["nodes"]}

        self.assertFalse(nodes["implement_first"]["parse_output_json"])
        self.assertFalse(nodes["implement_loop"]["parse_output_json"])
        self.assertTrue(nodes["check"]["parse_output_json"])
        self.assertEqual(
            nodes["check"]["route_bindings"]["failure"]["context.runtime.latest_check"],
            "outputs.check.control",
        )

    def test_refactor_loop_uses_arch_reviwer_and_refactor_only(self):
        self.assert_review_only_preset(
            preset_file="refactor_loop.yaml",
            start_node="arch_reviwer",
            history_key="arch_review_history",
            forbid_input_key="latest_refactor",
            assert_default_missing="latest_refactor",
        )

    def test_doc_reviewer_loop_is_review_only_and_tracks_all_history(self):
        self.assert_review_only_preset(
            preset_file="doc_reviewer_loop.yaml",
            start_node="doc_reviwer",
            history_key="doc_review_history",
        )


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

    def test_resolve_preset_path_resolves_builtin_identifier_in_repo_presets_dir(self):
        resolved = module.resolve_preset_path("implement_loop")
        expected = (ROOT / "presets" / "implement_loop.yaml").resolve()
        self.assertEqual(resolved, expected)

    def test_resolve_preset_path_is_cwd_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = Path.cwd()
            cwd_a = Path(tmp) / "a"
            cwd_b = Path(tmp) / "b"
            cwd_a.mkdir(parents=True, exist_ok=True)
            cwd_b.mkdir(parents=True, exist_ok=True)
            try:
                os.chdir(cwd_a)
                resolved_a = module.resolve_preset_path("implement_loop")
                os.chdir(cwd_b)
                resolved_b = module.resolve_preset_path("implement_loop")
            finally:
                os.chdir(original_cwd)
        self.assertEqual(resolved_a, resolved_b)
        self.assertEqual(resolved_a, (ROOT / "presets" / "implement_loop.yaml").resolve())

    def test_resolve_preset_path_rejects_path_like_value(self):
        with self.assertRaisesRegex(RuntimeError, "expects a preset identifier"):
            module.resolve_preset_path("presets/implement_loop.yaml")

    def test_resolve_preset_path_rejects_empty_or_whitespace_value(self):
        with self.assertRaisesRegex(RuntimeError, "non-empty preset identifier"):
            module.resolve_preset_path("   ")

    def test_resolve_preset_path_rejects_yaml_suffix_with_migration_hint(self):
        with self.assertRaisesRegex(RuntimeError, "Use 'implement_loop' instead of 'implement_loop.yaml'"):
            module.resolve_preset_path("implement_loop.yaml")

    def test_resolve_preset_path_reports_available_presets_for_unknown_identifier(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "Unknown preset identifier: 'missing'.*Available built-in presets: "
            "doc_reviewer_loop, implement_loop, refactor_loop, reviewer_loop",
        ):
            module.resolve_preset_path("missing")


class MainCliContractTests(unittest.TestCase):
    def test_main_dependency_error_uses_unified_stderr_path(self):
        args = type("Args", (), {"preset": "implement_loop", "context": None})()
        with patch.object(module, "parse_args", return_value=args):
            with patch.object(module, "PREFECT_IMPORT_ERROR", RuntimeError("prefect missing")):
                with patch("sys.stderr") as fake_stderr:
                    exit_code = module.main()
        self.assertEqual(exit_code, 2)
        written = "".join(call.args[0] for call in fake_stderr.write.call_args_list)
        self.assertIn("Missing dependency: prefect (prefect missing)", written)
