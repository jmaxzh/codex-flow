from __future__ import annotations

from typing import Any, NamedTuple, cast

from _codex_orchestrator.native_workflows.stage_schema import NormalizedStageSpec
from _codex_orchestrator.output_processing import resolve_node_output
from _codex_orchestrator.runtime.history import collect_output_history
from _codex_orchestrator.runtime.models import WorkflowStepContext


class StepOutputApplyResult(NamedTuple):
    node_output: Any
    pass_flag: bool


def apply_step_output_to_state(
    *,
    node: NormalizedStageSpec,
    step_ctx: WorkflowStepContext,
    runtime_state: dict[str, Any],
    raw_output: str,
) -> StepOutputApplyResult:
    node_output, pass_flag = resolve_node_output(raw_output, node["parse_output_json"])
    runtime_state["outputs"][step_ctx.node_id] = node_output
    collect_output_history(cast(dict[str, Any], node), node_output, runtime_state)
    return StepOutputApplyResult(node_output=node_output, pass_flag=pass_flag)
