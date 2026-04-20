import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from tests.codex_orchestrator_test_support import make_fake_codex_exec, module, patch_native_exec, run_workflow_direct


class PromptRenderingTests(unittest.TestCase):
    def _render(
        self,
        prompt: str,
        prompt_inputs: dict[str, Any] | None = None,
        config_path: str | None = None,
        node_id: str = "node_a",
        prompt_field: str = "native_workflow.node_a.prompt",
    ) -> str:
        return module.render_prompt(
            prompt,
            prompt_inputs or {},
            config_path or str(Path.cwd() / "presets" / "implement_loop.yaml"),
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

    def test_render_prompt_keeps_json_text_semantics_for_non_string_inputs(self):
        rendered = self._render(
            "obj={{ inputs.obj }} arr={{ inputs.arr }} flag={{ inputs.flag }}",
            {"obj": {"k": 1}, "arr": [1, 2], "flag": True},
        )
        self.assertIn('"k": 1', rendered)
        self.assertIn("[\n  1,\n  2\n]", rendered)
        self.assertIn("flag=true", rendered)


class PromptPathResolutionWorkflowTests(unittest.TestCase):
    def _run_with_include(self, launch_cwd: Path, captured_prompts: list[str]) -> None:
        call_counter = {"check": 0}

        def raw_output_for_call(*, node_id: str, **_kwargs: Any) -> str:
            if node_id == "implement_first":
                return "implemented"
            if node_id == "check":
                call_counter["check"] += 1
                if call_counter["check"] == 1:
                    return '{"pass": true}'
                return '{"pass": false}'
            return '{"pass": true}'

        fake_exec = make_fake_codex_exec(
            raw_output_for_call=cast(Callable[..., str], raw_output_for_call),
            captured_prompts=captured_prompts,
        )
        with patch_native_exec(fake_exec):
            run_workflow_direct("implement_loop", {"spec": "x", "user_instruction": "u", "__max_steps": "2"}, str(launch_cwd))

    def test_include_resolution_is_consistent_across_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd_a = root / "cwd_a"
            cwd_b = root / "cwd_b"
            cwd_a.mkdir(parents=True, exist_ok=True)
            cwd_b.mkdir(parents=True, exist_ok=True)

            captured_prompts: list[str] = []
            self._run_with_include(cwd_a, captured_prompts)
            self._run_with_include(cwd_b, captured_prompts)

            self.assertEqual(len(captured_prompts), 4)
            self.assertEqual(captured_prompts[0], captured_prompts[2])
            self.assertEqual(captured_prompts[1], captured_prompts[3])

    def test_include_resolution_is_independent_of_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launch_cwd = root / "caller"
            launch_cwd.mkdir(parents=True, exist_ok=True)
            prompts: list[str] = []
            self._run_with_include(launch_cwd, prompts)
            self.assertEqual(len(prompts), 2)
            self.assertIn("任务: x", prompts[0])
