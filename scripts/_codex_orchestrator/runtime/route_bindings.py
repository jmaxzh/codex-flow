from __future__ import annotations

import copy
from typing import Any, cast

from _codex_orchestrator.dotted_paths import parse_dotted_path, resolve_dotted_parts, set_dotted_parts


def apply_route_bindings(node: dict[str, Any], pass_flag: bool, runtime_state: dict[str, Any]) -> dict[str, str]:
    route_name = "success" if pass_flag else "failure"
    applied: dict[str, str] = {}
    route_bindings_raw = node.get("route_bindings", {})
    if not isinstance(route_bindings_raw, dict):
        raise RuntimeError(f"Node '{node.get('id', '<unknown>')}' route_bindings must be object")
    route_bindings = cast(dict[str, Any], route_bindings_raw)
    selected_bindings_raw = route_bindings.get(route_name, {})
    if not isinstance(selected_bindings_raw, dict):
        raise RuntimeError(f"Node '{node.get('id', '<unknown>')}' route_bindings.{route_name} must be object")

    for target_path_raw, source_path_raw in cast(dict[str, Any], selected_bindings_raw).items():
        target_path = target_path_raw
        source_path = source_path_raw
        source_parts = parse_dotted_path(source_path, f"route_bindings.{route_name}.{target_path}")
        target_parts = parse_dotted_path(target_path, f"route_bindings.{route_name}.{target_path}.target")
        value: Any = resolve_dotted_parts(runtime_state, source_parts, source_path)
        if isinstance(value, dict):
            value = copy.deepcopy(cast(dict[str, Any], value))
        elif isinstance(value, list):
            value = copy.deepcopy(cast(list[Any], value))
        set_dotted_parts(runtime_state, target_parts, target_path, value)
        applied[target_path] = source_path
    return applied
