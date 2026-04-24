from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple, cast


class PromptInputsProxy(dict[str, Any]):
    """Dict-like Jinja context where key lookup wins over dict attributes."""

    def __getattribute__(self, name: str) -> Any:
        if name.startswith("_"):
            return object.__getattribute__(self, name)
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def to_plain_prompt_value(value: Any) -> Any:
    if isinstance(value, PromptInputsProxy):
        plain: dict[str, Any] = {}
        for key in value:
            plain[key] = to_plain_prompt_value(value[key])
        return plain
    if isinstance(value, list):
        plain_list: list[Any] = []
        for item in cast(list[Any], value):
            plain_list.append(to_plain_prompt_value(item))
        return plain_list
    return value


def stringify_prompt_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(to_plain_prompt_value(value), ensure_ascii=False, indent=2)


def to_prompt_inputs_proxy(value: Any) -> Any:
    if isinstance(value, dict):
        value_dict = cast(dict[str, Any], value)
        return PromptInputsProxy({k: to_prompt_inputs_proxy(v) for k, v in value_dict.items()})
    if isinstance(value, list):
        proxied_list: list[Any] = []
        for item in cast(list[Any], value):
            proxied_list.append(to_prompt_inputs_proxy(item))
        return proxied_list
    return value


def finalize_prompt_value(value: Any, undefined_type: type[Any]) -> Any:
    if isinstance(value, undefined_type):
        return value
    return stringify_prompt_value(value)


def prompt_render_error(node_id: str, prompt_field: str, message: str) -> RuntimeError:
    return RuntimeError(f"{prompt_field} (node_id={node_id}) render failed: {message}")


class PromptRenderDeps(NamedTuple):
    jinja_import_error: Exception | None
    environment_cls: type[Any] | None
    strict_undefined_cls: type[Any] | None
    undefined_type: type[Any]
    resolve_dotted_path_func: Any
    resolve_path_func: Any
    read_text_func: Any


def _resolve_prompt_input(path_value: Any, prompt_inputs: dict[str, Any], resolve_dotted_path_func: Any) -> Any:
    if not isinstance(path_value, str):
        raise RuntimeError(f"prompt_input(path) expects string path, got {type(path_value).__name__}")
    input_path = path_value.strip()
    if not input_path:
        raise RuntimeError("prompt_input(path) expects non-empty path, got empty string")
    return resolve_dotted_path_func({"inputs": prompt_inputs}, f"inputs.{input_path}")


def _resolve_include_path(path_value: Any, config_dir: Path, resolve_path_func: Any) -> tuple[str, Path]:
    if not isinstance(path_value, str):
        raise RuntimeError(f"prompt_file(path) expects string path, got {type(path_value).__name__}")
    include_raw = path_value.strip()
    if not include_raw:
        raise RuntimeError("prompt_file(path) expects non-empty relative path, got empty string")

    path_obj = Path(include_raw).expanduser()
    if path_obj.is_absolute():
        raise RuntimeError(
            f"prompt_file(path) only supports relative path, got absolute path: {include_raw}. "
            "Use a path relative to the workflow config file."
        )
    return include_raw, resolve_path_func(path_obj, config_dir)


def _build_prompt_helpers(
    *,
    prompt_inputs: dict[str, Any],
    config_dir: Path,
    resolve_dotted_path_func: Any,
    resolve_path_func: Any,
    read_text_func: Any,
    render_included_text: Callable[[str, Path], str],
) -> tuple[Callable[[Any], Any], Callable[[Any], str]]:
    render_stack: list[Path] = []

    def prompt_input(path_value: Any) -> Any:
        return _resolve_prompt_input(path_value, prompt_inputs, resolve_dotted_path_func)

    def prompt_file(path_value: Any) -> str:
        include_raw, include_path = _resolve_include_path(path_value, config_dir, resolve_path_func)
        if include_path in render_stack:
            cycle = " -> ".join([*map(str, render_stack), str(include_path)])
            raise RuntimeError(f"prompt_file(path) recursive include detected: {cycle}")
        try:
            render_stack.append(include_path)
            include_text = read_text_func(include_path)
            return render_included_text(include_text, include_path)
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"prompt_file(path) file not found: {include_raw}. Check the path relative to the workflow config file."
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                f"prompt_file(path) cannot read file: {include_raw} ({exc}). Check file permissions and UTF-8 content."
            ) from exc
        finally:
            if render_stack and render_stack[-1] == include_path:
                render_stack.pop()

    return prompt_input, prompt_file


def _build_finalize_func(undefined_type: type[Any]) -> Callable[[Any], Any]:
    def _finalize(value: Any) -> Any:
        return finalize_prompt_value(value, undefined_type)

    return _finalize


def render_prompt(
    *,
    node_prompt: str,
    prompt_inputs: dict[str, Any],
    config_path: str,
    node_id: str,
    prompt_field: str,
    deps: PromptRenderDeps,
) -> str:
    if deps.jinja_import_error is not None or deps.environment_cls is None or deps.strict_undefined_cls is None:
        raise RuntimeError(f"Missing dependency: jinja2 ({deps.jinja_import_error})")

    config_dir = Path(config_path).resolve().parent
    try:
        finalize_func = _build_finalize_func(deps.undefined_type)
        env = deps.environment_cls(
            undefined=cast(Any, deps.strict_undefined_cls),
            autoescape=False,
            finalize=finalize_func,
        )

        prompt_input: Callable[[Any], Any]
        prompt_file: Callable[[Any], str]

        def _render_template_text(template_text: str, _source_path: Path | None = None) -> str:
            template = env.from_string(template_text)
            return template.render(
                inputs=to_prompt_inputs_proxy(prompt_inputs),
                prompt_file=prompt_file,
                prompt_input=prompt_input,
            )

        prompt_input, prompt_file = _build_prompt_helpers(
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
