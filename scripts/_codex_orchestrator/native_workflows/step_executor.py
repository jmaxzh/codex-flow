from __future__ import annotations

from pathlib import Path
from typing import Any

from _codex_orchestrator.executor import run_codex_exec
from _codex_orchestrator.fileio import read_text
from _codex_orchestrator.native_workflows.stage_schema import NextNodeResolver
from _codex_orchestrator.native_workflows.step_node_execution import StepNodeDeps, execute_step_node
from _codex_orchestrator.native_workflows.step_persistence import persist_step_result, plan_step_state_artifacts
from _codex_orchestrator.runtime.models import RunExecutionContext


def execute_workflow_step(
    *,
    run_ctx: RunExecutionContext,
    step_ctx: Any,
    prompt_base_dir: Path,
    next_node_resolver: NextNodeResolver | None = None,
    read_text_func: Any = read_text,
    run_codex_exec_func: Any = run_codex_exec,
) -> str:
    artifacts = plan_step_state_artifacts(run_ctx=run_ctx, step_ctx=step_ctx)
    step_result = execute_step_node(
        run_ctx=run_ctx,
        step_ctx=step_ctx,
        artifacts=artifacts,
        prompt_base_dir=prompt_base_dir,
        deps=StepNodeDeps(
            next_node_resolver=next_node_resolver,
            read_text_func=read_text_func,
            run_codex_exec_func=run_codex_exec_func,
        ),
    )
    return persist_step_result(
        run_ctx=run_ctx,
        step_ctx=step_ctx,
        artifacts=artifacts,
        step_result=step_result,
    )
