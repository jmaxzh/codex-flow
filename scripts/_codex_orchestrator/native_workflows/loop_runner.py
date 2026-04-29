from __future__ import annotations

import copy
from collections.abc import Mapping
from pathlib import Path
from typing import Any, NamedTuple, cast

from _codex_orchestrator.native_workflows.constants import END_NODE
from _codex_orchestrator.native_workflows.prompt_paths import prompt_base_dir
from _codex_orchestrator.native_workflows.runtime_io import NativeWorkflowIO, default_runtime_io
from _codex_orchestrator.native_workflows.stage_schema import (
    LoopFlowConfig,
    NextNodeResolver,
    NormalizedStageSpec,
    normalize_stage,
    validate_stages,
)
from _codex_orchestrator.native_workflows.step_executor import execute_workflow_step
from _codex_orchestrator.paths import resolve_path
from _codex_orchestrator.runtime.history import initialize_history_targets
from _codex_orchestrator.runtime.models import RunExecutionContext, build_step_context, create_runtime_state
from _codex_orchestrator.runtime.workspace import finalize_run_outputs, prepare_run_workspace


class PreparedFlowConfig(NamedTuple):
    max_steps: int
    normalized_defaults: dict[str, Any]
    normalized_nodes: dict[str, NormalizedStageSpec]
    start_node: str
    next_node_resolver: NextNodeResolver | None


def _resolve_max_steps(base_max_steps: int, max_steps_override: int | None) -> int:
    max_steps = base_max_steps
    if max_steps_override is None:
        return base_max_steps
    try:
        max_steps = int(cast(Any, max_steps_override))
    except ValueError as exc:
        raise RuntimeError(f"Invalid __max_steps override: {max_steps_override}") from exc
    if max_steps <= 0:
        raise RuntimeError(f"Invalid __max_steps override: {max_steps_override}")
    return max_steps


def prepare_flow_config(flow_cfg: LoopFlowConfig) -> PreparedFlowConfig:
    context_data = dict(flow_cfg["context_overrides"])
    max_steps = _resolve_max_steps(flow_cfg["max_steps"], flow_cfg.get("max_steps_override"))
    normalized_defaults = {**flow_cfg["defaults"], **context_data}
    normalized_nodes: dict[str, NormalizedStageSpec] = {
        node_id: normalize_stage(node_id, stage) for node_id, stage in flow_cfg["stages"].items()
    }
    validate_stages(flow_cfg["start_node"], normalized_nodes)
    return PreparedFlowConfig(
        max_steps=max_steps,
        normalized_defaults=normalized_defaults,
        normalized_nodes=normalized_nodes,
        start_node=flow_cfg["start_node"],
        next_node_resolver=flow_cfg.get("next_node_resolver"),
    )


def build_run_context(
    *,
    workspace: Mapping[str, Any],
    prepared_cfg: PreparedFlowConfig,
    runtime_io: NativeWorkflowIO,
) -> RunExecutionContext:
    runtime_state = create_runtime_state(prepared_cfg.normalized_defaults)
    initialize_history_targets([dict(stage) for stage in prepared_cfg.normalized_nodes.values()], runtime_state)
    attempt_counter: dict[str, int] = {}
    config = {
        "executor": {"cmd": list(runtime_io.executor_cmd)},
        "context": {"defaults": prepared_cfg.normalized_defaults},
    }
    return RunExecutionContext(
        config=config,
        project_root=workspace["project_root"],
        run_state_dir=workspace["run_state_dir"],
        run_log_dir=workspace["run_log_dir"],
        max_steps=prepared_cfg.max_steps,
        runtime_state=runtime_state,
        attempt_counter=attempt_counter,
        node_ids=set(prepared_cfg.normalized_nodes),
    )


def run_loop(
    *,
    run_ctx: RunExecutionContext,
    prepared_cfg: PreparedFlowConfig,
    runtime_io: NativeWorkflowIO,
    prompt_dir: Path,
) -> tuple[str, int]:
    current_node_id = prepared_cfg.start_node
    steps_executed = 0
    while steps_executed < run_ctx.max_steps and current_node_id != END_NODE:
        step = steps_executed + 1
        step_ctx = build_step_context(
            node=dict(prepared_cfg.normalized_nodes[current_node_id]),
            node_id=current_node_id,
            step=step,
            attempt_counter=run_ctx.attempt_counter,
        )
        current_node_id = execute_workflow_step(
            run_ctx=run_ctx,
            step_ctx=step_ctx,
            prompt_base_dir=prompt_dir,
            next_node_resolver=prepared_cfg.next_node_resolver,
            read_text_func=runtime_io.read_text_func,
            run_codex_exec_func=runtime_io.run_codex_exec_func,
        )
        steps_executed += 1
    return current_node_id, steps_executed


def finalize_flow_result(
    *,
    workspace: Mapping[str, Any],
    run_ctx: RunExecutionContext,
    final_node: str,
    steps_executed: int,
) -> dict[str, Any]:
    if final_node != END_NODE:
        raise RuntimeError(f"Reached max_steps without END: {run_ctx.max_steps}")
    return finalize_run_outputs(
        run_id=workspace["run_id"],
        run_state_dir=workspace["run_state_dir"],
        state_dir=workspace["state_dir"],
        final_node=final_node,
        steps_executed=steps_executed,
        outputs=copy.deepcopy(run_ctx.runtime_state["outputs"]),
    )


def execute_loop_flow(*, flow_cfg: LoopFlowConfig, runtime_io: NativeWorkflowIO | None = None) -> dict[str, Any]:
    project_root = resolve_path(".", Path(flow_cfg["launch_cwd"]).resolve())
    state_dir = resolve_path(".codex-loop-state", project_root)
    workspace = prepare_run_workspace(
        {
            "project_root": str(project_root),
            "state_dir": str(state_dir),
        }
    )
    io = runtime_io or default_runtime_io()
    prepared_cfg = prepare_flow_config(flow_cfg)
    run_ctx = build_run_context(
        workspace=workspace,
        prepared_cfg=prepared_cfg,
        runtime_io=io,
    )
    final_node, steps_executed = run_loop(
        run_ctx=run_ctx,
        prepared_cfg=prepared_cfg,
        runtime_io=io,
        prompt_dir=prompt_base_dir(),
    )
    return finalize_flow_result(
        workspace=workspace,
        run_ctx=run_ctx,
        final_node=final_node,
        steps_executed=steps_executed,
    )
