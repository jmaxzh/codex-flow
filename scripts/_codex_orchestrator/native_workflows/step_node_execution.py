from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple

from _codex_orchestrator.executor import CodexExecRequest
from _codex_orchestrator.native_workflows.stage_schema import NextNodeResolver
from _codex_orchestrator.native_workflows.step_execution_io import execute_step_command
from _codex_orchestrator.native_workflows.step_next_node import (
    apply_route_bindings_for_result,
    resolve_default_next_node,
    resolve_next_node_with_resolver,
    validate_next_node_target,
)
from _codex_orchestrator.native_workflows.step_output_parser import apply_step_output_to_state
from _codex_orchestrator.native_workflows.step_prompt_renderer import render_step_prompt
from _codex_orchestrator.runtime.models import RunExecutionContext, StepExecutionResult


class StepNodeDeps(NamedTuple):
    next_node_resolver: NextNodeResolver | None
    read_text_func: Callable[[Path], str]
    run_codex_exec_func: Callable[[CodexExecRequest], str]


def execute_step_node(
    *,
    run_ctx: RunExecutionContext,
    step_ctx: Any,
    artifacts: Any,
    prompt_base_dir: Path,
    deps: StepNodeDeps,
) -> StepExecutionResult:
    node = step_ctx.node
    rendered = render_step_prompt(
        node=node,
        runtime_state=run_ctx.runtime_state,
        prompt_base_dir=prompt_base_dir,
        read_text_func=deps.read_text_func,
    )
    io_result = execute_step_command(
        run_ctx=run_ctx,
        step_ctx=step_ctx,
        artifacts=artifacts,
        rendered_prompt=rendered,
        run_codex_exec_func=deps.run_codex_exec_func,
        read_text_func=deps.read_text_func,
    )
    apply_result = apply_step_output_to_state(
        node=node,
        step_ctx=step_ctx,
        runtime_state=run_ctx.runtime_state,
        raw_output=io_result.raw_output,
    )
    default_next_node = resolve_default_next_node(
        node=node,
        pass_flag=apply_result.pass_flag,
    )
    next_node = resolve_next_node_with_resolver(
        node=node,
        pass_flag=apply_result.pass_flag,
        default_next_node=default_next_node,
        runtime_state=run_ctx.runtime_state,
        node_ids=run_ctx.node_ids,
        next_node_resolver=deps.next_node_resolver,
    )
    validate_next_node_target(node=node, next_node=next_node, node_ids=run_ctx.node_ids)
    applied_route_bindings = apply_route_bindings_for_result(
        node=node,
        pass_flag=apply_result.pass_flag,
        runtime_state=run_ctx.runtime_state,
    )
    return StepExecutionResult(
        rendered_prompt=rendered,
        raw_output_path=artifacts.raw_output_path,
        codex_log_path=io_result.codex_log_path,
        node_output=apply_result.node_output,
        pass_flag=apply_result.pass_flag,
        next_node=next_node,
        applied_route_bindings=applied_route_bindings,
    )
