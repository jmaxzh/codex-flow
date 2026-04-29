from __future__ import annotations

from typing import Any, cast

from prefect import task

from _codex_orchestrator.executor import CodexExecRequest
from _codex_orchestrator.executor import run_codex_exec as _run_codex_exec_impl
from _codex_orchestrator.native_workflows.prompt_inputs import build_prompt_inputs as _build_prompt_inputs_impl
from _codex_orchestrator.native_workflows.prompt_render_deps import prompt_render_deps
from _codex_orchestrator.output_processing import parse_and_validate_output as _parse_and_validate_output_impl
from _codex_orchestrator.output_processing import resolve_node_output as _resolve_node_output_impl
from _codex_orchestrator.prompt import render_prompt as _render_prompt_impl
from _codex_orchestrator.routing import resolve_next_node as _resolve_next_node_impl
from _codex_orchestrator.runtime import apply_route_bindings as _apply_route_bindings_impl
from _codex_orchestrator.runtime import ensure_history_list as _ensure_history_list_impl


@task
def build_prompt_inputs(node: dict[str, Any], runtime_state: dict[str, Any]) -> dict[str, Any]:
    return _build_prompt_inputs_impl(cast(Any, node), runtime_state)


@task
def render_prompt(
    node_prompt: str,
    prompt_inputs: dict[str, Any],
    config_path: str,
    node_id: str,
    prompt_field: str,
) -> str:
    return _render_prompt_impl(
        node_prompt=node_prompt,
        prompt_inputs=prompt_inputs,
        config_path=config_path,
        node_id=node_id,
        prompt_field=prompt_field,
        deps=prompt_render_deps(),
    )


@task
def run_codex_exec(request: CodexExecRequest) -> str:
    return _run_codex_exec_impl(request)


@task
def parse_and_validate_output(raw_output: str) -> tuple[dict[str, Any], bool]:
    return _parse_and_validate_output_impl(raw_output)


@task
def resolve_node_output(raw_output: str, parse_output_json: bool) -> tuple[Any, bool]:
    return _resolve_node_output_impl(raw_output, parse_output_json)


@task
def resolve_next_node(node: dict[str, Any], pass_flag: bool) -> str:
    return _resolve_next_node_impl(node, pass_flag)


@task
def apply_route_bindings(node: dict[str, Any], pass_flag: bool, runtime_state: dict[str, Any]) -> dict[str, str]:
    return _apply_route_bindings_impl(node, pass_flag, runtime_state)


@task
def ensure_history_list(
    runtime_state: dict[str, Any],
    target_path: str,
    target_parts: tuple[str, ...] | None = None,
) -> list[Any]:
    return _ensure_history_list_impl(runtime_state, target_path, target_parts)
