from __future__ import annotations

from typing import Any

from _codex_orchestrator.runtime.artifact_store import persist_step_artifacts
from _codex_orchestrator.runtime.artifacts import build_meta_payload, plan_step_artifacts
from _codex_orchestrator.runtime.models import RunExecutionContext, StepExecutionResult
from _codex_orchestrator.runtime.snapshot import build_runtime_snapshot


def plan_step_state_artifacts(*, run_ctx: RunExecutionContext, step_ctx: Any) -> Any:
    return plan_step_artifacts(run_ctx.run_state_dir, step_ctx)


def persist_step_result(
    *,
    run_ctx: RunExecutionContext,
    step_ctx: Any,
    artifacts: Any,
    step_result: StepExecutionResult,
) -> str:
    next_node = step_result.next_node
    meta_payload = build_meta_payload(
        step_ctx=step_ctx,
        step_result=step_result,
        artifacts=artifacts,
    )
    persist_step_artifacts(
        artifacts=artifacts,
        rendered_prompt=step_result.rendered_prompt,
        node_output=step_result.node_output,
        meta_payload=meta_payload,
        runtime_snapshot=build_runtime_snapshot(
            run_ctx.runtime_state,
            run_ctx.attempt_counter,
            next_node,
            step_ctx.step,
            run_ctx.max_steps,
        ),
    )
    return next_node
