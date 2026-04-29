from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple

from _codex_orchestrator.fileio import write_json
from _codex_orchestrator.naming import build_step_prefix
from _codex_orchestrator.runtime.models import StepExecutionResult, WorkflowStepContext


class StepArtifactsPlan(NamedTuple):
    prefix: str
    raw_output_path: Path
    prompt_path: Path
    parsed_path: Path
    meta_path: Path
    history_path: Path


def plan_step_artifacts(run_state_dir: Path, step_ctx: WorkflowStepContext) -> StepArtifactsPlan:
    prefix = build_step_prefix(step_ctx.step, step_ctx.node_id, step_ctx.attempt)
    return StepArtifactsPlan(
        prefix=prefix,
        raw_output_path=run_state_dir / f"{prefix}__raw.txt",
        prompt_path=run_state_dir / f"{prefix}__prompt.txt",
        parsed_path=run_state_dir / f"{prefix}__parsed.json",
        meta_path=run_state_dir / f"{prefix}__meta.json",
        history_path=run_state_dir / "history.jsonl",
    )


def build_meta_payload(
    *,
    step_ctx: WorkflowStepContext,
    step_result: StepExecutionResult,
    artifacts: StepArtifactsPlan,
) -> dict[str, Any]:
    return {
        "step": step_ctx.step,
        "node_id": step_ctx.node_id,
        "attempt": step_ctx.attempt,
        "pass": step_result.pass_flag,
        "next_node": step_result.next_node,
        "prompt_path": str(artifacts.prompt_path),
        "raw_output_path": str(step_result.raw_output_path),
        "parsed_output_path": str(artifacts.parsed_path),
        "codex_log_path": step_result.codex_log_path,
        "applied_route_bindings": step_result.applied_route_bindings,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }


def write_runtime_snapshot(run_state_dir: Path, runtime_snapshot: dict[str, Any]) -> None:
    write_json(run_state_dir / "runtime_state.json", runtime_snapshot)
