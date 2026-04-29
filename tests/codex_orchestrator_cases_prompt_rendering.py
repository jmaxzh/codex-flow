import tempfile
import unittest
from pathlib import Path
from typing import Any

from tests.codex_orchestrator_module_loader import module


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
            config_path or str(Path.cwd() / "presets" / "openspec_implement.yaml"),
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

    def test_render_prompt_renders_inputs_inside_included_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = base / "preset.yaml"
            outer = base / "prompts" / "outer.md"
            inner = base / "prompts" / "inner.md"

            outer.parent.mkdir(parents=True, exist_ok=True)
            outer.write_text(
                'A={{ inputs.a }} / {{ prompt_file("./prompts/inner.md") }}',
                encoding="utf-8",
            )
            inner.write_text("B={{ inputs.b }}", encoding="utf-8")
            cfg.write_text("{}", encoding="utf-8")

            rendered = self._render(
                '{{ prompt_file("./prompts/outer.md") }}',
                {"a": "x", "b": "y"},
                str(cfg),
            )

        self.assertEqual(rendered, "A=x / B=y")

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
