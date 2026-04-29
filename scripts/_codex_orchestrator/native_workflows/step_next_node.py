from __future__ import annotations

from typing import Any, cast

from _codex_orchestrator.native_workflows.constants import END_NODE
from _codex_orchestrator.native_workflows.stage_schema import NextNodeResolver, NormalizedStageSpec
from _codex_orchestrator.runtime.route_bindings import apply_route_bindings


def resolve_default_next_node(
    *,
    node: NormalizedStageSpec,
    pass_flag: bool,
) -> str:
    typed_node = cast(dict[str, Any], node)
    return typed_node["on_success"] if pass_flag else typed_node["on_failure"]


def resolve_next_node_with_resolver(
    *,
    node: NormalizedStageSpec,
    pass_flag: bool,
    default_next_node: str,
    runtime_state: dict[str, Any],
    node_ids: set[str],
    next_node_resolver: NextNodeResolver | None,
) -> str:
    if next_node_resolver is None:
        return default_next_node
    return next_node_resolver(cast(dict[str, Any], node), pass_flag, default_next_node, runtime_state, node_ids)


def apply_route_bindings_for_result(
    *,
    node: NormalizedStageSpec,
    pass_flag: bool,
    runtime_state: dict[str, Any],
) -> dict[str, str]:
    return apply_route_bindings(cast(dict[str, Any], node), pass_flag, runtime_state)


def validate_next_node_target(*, node: NormalizedStageSpec, next_node: str, node_ids: set[str]) -> None:
    if not next_node.strip():
        raise RuntimeError(f"Node '{node['id']}' resolved invalid next node: {next_node}")
    if next_node != END_NODE and next_node not in node_ids:
        raise RuntimeError(f"Node '{node['id']}' resolved invalid next node target: {next_node}")
