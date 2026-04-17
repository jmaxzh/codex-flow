import os
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from tests.codex_orchestrator_test_support import (
    ROOT,
    PatchedYamlMixin,
    WorkflowTestFactoryMixin,
    module,
)


class PromptRenderingTests(PatchedYamlMixin, unittest.TestCase):
    def _render(
        self,
        prompt: str,
        prompt_inputs: dict[str, Any] | None = None,
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
        WorkflowTestFactoryMixin().write_workflow_config_at(
            config_path,
            project_root=project_root,
            max_steps=1,
            defaults={"k": "v"},
            start="n1",
            nodes=[
                {
                    "id": "n1",
                    "prompt": '{{ prompt_file("./prompts/x.md") }} {{ inputs.k }}',
                    "input_map": {"k": "context.defaults.k"},
                    "on_success": "END",
                    "on_failure": "END",
                }
            ],
        )

    def _fake_json_success_exec(self, captured_prompts: list[str] | None = None):
        def _raw_output_for_call(**_kwargs: Any) -> str:
            return '{"pass": true}'

        return WorkflowTestFactoryMixin().make_fake_codex_exec(
            raw_output_for_call=cast(Callable[..., str], _raw_output_for_call),
            captured_prompts=captured_prompts,
        )

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
            fake_codex_exec = self._fake_json_success_exec(captured_prompts)

            original_cwd = Path.cwd()
            cwd_a = root / "cwd_a"
            cwd_b = root / "cwd_b"
            cwd_a.mkdir(parents=True, exist_ok=True)
            cwd_b.mkdir(parents=True, exist_ok=True)
            try:
                with (
                    self.patch_yaml(),
                    patch.object(module, "run_codex_exec", side_effect=fake_codex_exec),
                ):
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
            fake_codex_exec = self._fake_json_success_exec(prompts)

            with (
                self.patch_yaml(),
                patch.object(module, "run_codex_exec", side_effect=fake_codex_exec),
            ):
                module.run_workflow(str(config_path), {})

            self.assertEqual(len(prompts), 1)
            self.assertIn("CFG_DIR_CONTENT", prompts[0])

    def test_run_workflow_passes_launch_cwd_to_load_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "configs" / "wf.yaml"
            include = root / "configs" / "prompts" / "x.md"
            project_root = root / "project"
            include.parent.mkdir(parents=True, exist_ok=True)
            project_root.mkdir(parents=True, exist_ok=True)
            include.write_text("FROM_INCLUDE", encoding="utf-8")
            self._write_workflow_config(config_path, project_root)

            load_config_calls: list[str | None] = []
            original_load_config = module.load_config

            def wrapped_load_config(
                config_path: str,
                context_overrides: dict[str, str],
                launch_cwd: str | None = None,
            ) -> dict[str, object]:
                load_config_calls.append(launch_cwd)
                return original_load_config(config_path, context_overrides, launch_cwd)

            fake_codex_exec = self._fake_json_success_exec()

            launch_cwd = root / "caller-worktree"
            launch_cwd.mkdir(parents=True, exist_ok=True)
            with (
                self.patch_yaml(),
                patch.object(module, "load_config", side_effect=wrapped_load_config),
                patch.object(module, "run_codex_exec", side_effect=fake_codex_exec),
            ):
                module.run_workflow(str(config_path), {}, str(launch_cwd))

            self.assertEqual(load_config_calls, [str(launch_cwd)])
