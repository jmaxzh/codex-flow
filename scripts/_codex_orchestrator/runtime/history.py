from __future__ import annotations

import copy
from typing import Any, cast

from _codex_orchestrator.dotted_paths import parse_dotted_path, resolve_dotted_parts, set_dotted_parts


def ensure_history_list(
    runtime_state: dict[str, Any],
    target_path: str,
    target_parts: tuple[str, ...] | None = None,
) -> list[Any]:
    if target_parts is None:
        raise RuntimeError(f"History target missing compiled path: {target_path}")
    parts = target_parts
    current_any: Any
    try:
        current_any = resolve_dotted_parts(runtime_state, parts, target_path)
    except RuntimeError:
        current_any = cast(list[Any], [])
        set_dotted_parts(runtime_state, parts, target_path, current_any)
    if not isinstance(current_any, list):
        raise RuntimeError(f"History target must be array at path: {target_path}")
    current_list: list[Any] = cast(list[Any], current_any)
    return current_list


def collect_output_history(
    node: dict[str, Any],
    node_output: Any,
    runtime_state: dict[str, Any],
) -> str | None:
    history_target = node.get("collect_history_to")
    if history_target is None:
        return None
    if not isinstance(history_target, str):
        raise RuntimeError(f"Node '{node.get('id', '<unknown>')}' collect_history_to must be string")
    target_parts = parse_dotted_path(history_target, f"{node.get('id', '<unknown>')}.collect_history_to")
    current = ensure_history_list(runtime_state, history_target, target_parts)
    current.append(copy.deepcopy(node_output))
    return history_target


def initialize_history_targets(workflow_nodes: list[dict[str, Any]], runtime_state: dict[str, Any]) -> None:
    for node in workflow_nodes:
        history_target = node.get("collect_history_to")
        if history_target is None:
            continue
        if not isinstance(history_target, str):
            raise RuntimeError(f"Node '{node.get('id', '<unknown>')}' collect_history_to must be string")
        ensure_history_list(
            runtime_state,
            history_target,
            parse_dotted_path(history_target, f"{node.get('id', '<unknown>')}.collect_history_to"),
        )
