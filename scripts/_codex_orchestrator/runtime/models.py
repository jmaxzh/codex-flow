from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple


class RunExecutionContext(NamedTuple):
    config: dict[str, Any]
    project_root: Path
    run_state_dir: Path
    run_log_dir: Path
    max_steps: int
    runtime_state: dict[str, Any]
    attempt_counter: dict[str, int]
    node_ids: set[str]


class WorkflowStepContext(NamedTuple):
    node: dict[str, Any]
    node_id: str
    step: int
    attempt: int


class StepExecutionResult(NamedTuple):
    rendered_prompt: str
    raw_output_path: Path
    codex_log_path: str
    node_output: Any
    pass_flag: bool
    next_node: str
    applied_route_bindings: dict[str, str]


def create_runtime_state(default_context: dict[str, Any]) -> dict[str, Any]:
    return {
        "context": {"defaults": default_context, "runtime": {}},
        "outputs": {},
    }


def next_attempt(attempt_counter: dict[str, int], node_id: str) -> int:
    attempt = attempt_counter.get(node_id, 0) + 1
    attempt_counter[node_id] = attempt
    return attempt


def build_step_context(
    *,
    node: dict[str, Any],
    node_id: str,
    step: int,
    attempt_counter: dict[str, int],
) -> WorkflowStepContext:
    return WorkflowStepContext(
        node=node,
        node_id=node_id,
        step=step,
        attempt=next_attempt(attempt_counter, node_id),
    )
