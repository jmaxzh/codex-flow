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


def _build_prompt_helpers(
    *,
    prompt_inputs: dict[str, Any],
    config_dir: Path,
    resolve_dotted_path_func: Any,
    resolve_path_func: Any,
    read_text_func: Any,
) -> tuple[Callable[[Any], Any], Callable[[Any], str]]:
    def prompt_input(path_value: Any) -> Any:
        if not isinstance(path_value, str):
            raise RuntimeError(f"prompt_input(path) expects string path, got {type(path_value).__name__}")
        input_path = path_value.strip()
        if not input_path:
            raise RuntimeError("prompt_input(path) expects non-empty path, got empty string")
        return resolve_dotted_path_func({"inputs": prompt_inputs}, f"inputs.{input_path}")

    def prompt_file(path_value: Any) -> str:
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

        include_path = resolve_path_func(path_obj, config_dir)
        try:
            return read_text_func(include_path)
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"prompt_file(path) file not found: {include_raw}. Check the path relative to the workflow config file."
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                f"prompt_file(path) cannot read file: {include_raw} ({exc}). Check file permissions and UTF-8 content."
            ) from exc

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
    prompt_input, prompt_file = _build_prompt_helpers(
        prompt_inputs=prompt_inputs,
        config_dir=config_dir,
        resolve_dotted_path_func=deps.resolve_dotted_path_func,
        resolve_path_func=deps.resolve_path_func,
        read_text_func=deps.read_text_func,
    )
    finalize_func = _build_finalize_func(deps.undefined_type)

    try:
        env = deps.environment_cls(
            undefined=cast(Any, deps.strict_undefined_cls),
            autoescape=False,
            finalize=finalize_func,
        )
        template = env.from_string(node_prompt)
        return template.render(
            inputs=to_prompt_inputs_proxy(prompt_inputs),
            prompt_file=prompt_file,
            prompt_input=prompt_input,
        )
    except Exception as exc:
        raise prompt_render_error(node_id, prompt_field, str(exc)) from exc
