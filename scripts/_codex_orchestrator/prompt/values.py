from __future__ import annotations

import json
from typing import Any, cast


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
