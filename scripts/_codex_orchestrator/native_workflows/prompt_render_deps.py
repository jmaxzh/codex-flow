from __future__ import annotations

from typing import Any, cast

from jinja2 import Environment, StrictUndefined
from jinja2.runtime import Undefined

from _codex_orchestrator.dotted_paths import parse_dotted_path, resolve_dotted_parts
from _codex_orchestrator.fileio import read_text
from _codex_orchestrator.paths import resolve_path
from _codex_orchestrator.prompt.rendering import PromptRenderDeps


def _resolve_dotted_path(data: dict[str, Any], dotted_path: str) -> Any:
    return resolve_dotted_parts(
        data,
        parse_dotted_path(dotted_path, dotted_path),
        dotted_path,
    )


def prompt_render_deps(*, read_text_func: Any = read_text) -> PromptRenderDeps:
    return PromptRenderDeps(
        environment_cls=Environment,
        strict_undefined_cls=StrictUndefined,
        undefined_type=cast(type[Any], Undefined),
        resolve_dotted_path_func=_resolve_dotted_path,
        resolve_path_func=resolve_path,
        read_text_func=read_text_func,
    )
