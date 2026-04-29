from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from _codex_orchestrator.executor import CodexExecRequest
from _codex_orchestrator.runtime.artifacts import StepArtifactsPlan
from _codex_orchestrator.runtime.models import RunExecutionContext, WorkflowStepContext


class StepExecutionIO(NamedTuple):
    codex_log_path: str
    raw_output: str


def execute_step_command(
    *,
    run_ctx: RunExecutionContext,
    step_ctx: WorkflowStepContext,
    artifacts: StepArtifactsPlan,
    rendered_prompt: str,
    run_codex_exec_func: Callable[[CodexExecRequest], str],
    read_text_func: Callable[[Path], str],
) -> StepExecutionIO:
    codex_log_path = run_codex_exec_func(
        CodexExecRequest(
            project_root=str(run_ctx.project_root),
            executor_cmd=run_ctx.config["executor"]["cmd"],
            prompt=rendered_prompt,
            out_file=str(artifacts.raw_output_path),
            task_log_dir=str(run_ctx.run_log_dir),
            node_id=step_ctx.node_id,
            step=step_ctx.step,
            attempt=step_ctx.attempt,
        )
    )
    raw_output = read_text_func(artifacts.raw_output_path)
    return StepExecutionIO(codex_log_path=codex_log_path, raw_output=raw_output)
