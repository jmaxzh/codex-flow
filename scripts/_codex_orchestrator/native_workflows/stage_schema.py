from __future__ import annotations

from collections.abc import Callable
from typing import Any, NotRequired, TypedDict

from _codex_orchestrator.native_workflows.constants import END_NODE


class StageSpec(TypedDict, total=False):
    id: str
    prompt: str
    prompt_field: str
    input_map: dict[str, str]
    parse_output_json: bool
    on_success: str
    on_failure: str
    collect_history_to: str
    route_bindings: dict[str, dict[str, str]]


class NormalizedStageSpec(TypedDict):
    id: str
    prompt: str
    prompt_field: str
    input_map: dict[str, str]
    parse_output_json: bool
    on_success: str
    on_failure: str
    collect_history_to: str | None
    route_bindings: dict[str, dict[str, str]]


NextNodeResolver = Callable[[dict[str, Any], bool, str, dict[str, Any], set[str]], str]


class LoopFlowConfig(TypedDict):
    launch_cwd: str
    context_overrides: dict[str, str]
    defaults: dict[str, Any]
    max_steps: int
    max_steps_override: NotRequired[int | None]
    start_node: str
    stages: dict[str, StageSpec]
    next_node_resolver: NotRequired[NextNodeResolver]


def normalize_stage(node_id: str, stage: StageSpec) -> NormalizedStageSpec:
    if "prompt" not in stage or "on_success" not in stage or "on_failure" not in stage:
        raise RuntimeError(f"Invalid stage definition: {node_id}")
    normalized: NormalizedStageSpec = {
        "id": stage.get("id", node_id),
        "prompt": stage["prompt"],
        "prompt_field": stage.get("prompt_field", f"native_workflow.{node_id}.prompt"),
        "input_map": dict(stage.get("input_map", {})),
        "parse_output_json": stage.get("parse_output_json", True),
        "on_success": stage["on_success"],
        "on_failure": stage["on_failure"],
        "collect_history_to": stage.get("collect_history_to"),
        "route_bindings": {
            "success": dict(stage.get("route_bindings", {}).get("success", {})),
            "failure": dict(stage.get("route_bindings", {}).get("failure", {})),
        },
    }
    return normalized


def validate_stages(start_node: str, nodes_by_id: dict[str, NormalizedStageSpec]) -> None:
    if start_node not in nodes_by_id:
        raise RuntimeError(f"workflow.start target not found: {start_node}")

    node_ids = set(nodes_by_id)
    for node in nodes_by_id.values():
        for edge in ("on_success", "on_failure"):
            target = node[edge]
            if target != END_NODE and target not in node_ids:
                raise RuntimeError(f"Node '{node['id']}' has invalid {edge}: {target}")
