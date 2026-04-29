from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple, cast

from _codex_orchestrator.prompt.helpers import build_finalize_func, build_prompt_helpers
from _codex_orchestrator.prompt.values import (
    PromptInputsProxy,
    finalize_prompt_value,
    prompt_render_error,
    stringify_prompt_value,
    to_plain_prompt_value,
    to_prompt_inputs_proxy,
)


class PromptRenderDeps(NamedTuple):
    environment_cls: type[Any]
    strict_undefined_cls: type[Any]
    undefined_type: type[Any]
    resolve_dotted_path_func: Any
    resolve_path_func: Any
    read_text_func: Any


def render_prompt(
    *,
    node_prompt: str,
    prompt_inputs: dict[str, Any],
    config_path: str,
    node_id: str,
    prompt_field: str,
    deps: PromptRenderDeps,
) -> str:
    config_dir = Path(config_path).resolve().parent
    try:
        finalize_func = build_finalize_func(deps.undefined_type)
        env = deps.environment_cls(
            undefined=cast(Any, deps.strict_undefined_cls),
            autoescape=False,
            finalize=finalize_func,
        )

        def _render_template_text(template_text: str, _source_path: Path | None = None) -> str:
            template = env.from_string(template_text)
            return template.render(
                inputs=to_prompt_inputs_proxy(prompt_inputs),
                prompt_file=prompt_file,
                prompt_input=prompt_input,
            )

        prompt_input, prompt_file = build_prompt_helpers(
            prompt_inputs=prompt_inputs,
            config_dir=config_dir,
            resolve_dotted_path_func=deps.resolve_dotted_path_func,
            resolve_path_func=deps.resolve_path_func,
            read_text_func=deps.read_text_func,
            render_included_text=lambda text, source_path: _render_template_text(text, source_path),
        )

        return _render_template_text(node_prompt)
    except Exception as exc:
        raise prompt_render_error(node_id, prompt_field, str(exc)) from exc


__all__ = [
    "PromptInputsProxy",
    "PromptRenderDeps",
    "finalize_prompt_value",
    "prompt_render_error",
    "render_prompt",
    "stringify_prompt_value",
    "to_plain_prompt_value",
    "to_prompt_inputs_proxy",
]
