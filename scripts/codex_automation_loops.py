#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast, overload

if __package__ in (None, "") or __package__ == "scripts":
    SCRIPT_DIR = Path(__file__).resolve().parent
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))

from _codex_orchestrator.config_compiler import END_NODE, get_compiled_input_bindings
from _codex_orchestrator.config_compiler import load_config as _load_config_impl
from _codex_orchestrator.dotted_paths import resolve_dotted_parts, resolve_dotted_path
from _codex_orchestrator.executor import CodexExecRequest
from _codex_orchestrator.executor import run_codex_exec as _run_codex_exec_impl
from _codex_orchestrator.fileio import read_text
from _codex_orchestrator.naming import (
    build_step_prefix as _build_step_prefix_impl,
)
from _codex_orchestrator.naming import (
    make_codex_log_path as _make_codex_log_path_impl,
)
from _codex_orchestrator.output_processing import (
    extract_last_non_empty_line as _extract_last_non_empty_line_impl,
)
from _codex_orchestrator.output_processing import (
    parse_and_validate_output as _parse_and_validate_output_impl,
)
from _codex_orchestrator.output_processing import (
    resolve_next_node as _resolve_next_node_impl,
)
from _codex_orchestrator.output_processing import (
    resolve_node_output as _resolve_node_output_impl,
)
from _codex_orchestrator.paths import resolve_path, resolve_preset_path
from _codex_orchestrator.prompting import PromptRenderDeps
from _codex_orchestrator.prompting import render_prompt as _render_prompt_impl
from _codex_orchestrator.runtime import (
    RunExecutionContext,
    StepExecutionResult,
    WorkflowStepContext,
    build_meta_payload,
    build_runtime_snapshot,
    build_step_context,
    collect_output_history,
    create_runtime_state,
    finalize_run_outputs,
    initialize_history_targets,
    persist_step_artifacts,
    plan_step_artifacts,
    prepare_run_workspace,
)
from _codex_orchestrator.runtime import (
    apply_route_bindings as _apply_route_bindings_impl,
)
from _codex_orchestrator.runtime import (
    ensure_history_list as _ensure_history_list_impl,
)


@overload
def _identity_decorator[**P, R](func: Callable[P, R]) -> Callable[P, R]: ...


@overload
def _identity_decorator[**P, R](*, name: str | None = None) -> Callable[[Callable[P, R]], Callable[P, R]]: ...


def _identity_decorator[**P, R](func: Callable[P, R] | None = None, **_kwargs: Any) -> Any:
    if func is None:

        def _wrap(inner: Callable[P, R]) -> Callable[P, R]:
            return inner

        return _wrap
    return func


class _DecoratorLike(Protocol):
    @overload
    def __call__[**P, R](self, __fn: Callable[P, R], /) -> Callable[P, R]: ...

    @overload
    def __call__[**P, R](self, *args: Any, **kwargs: Any) -> Callable[[Callable[P, R]], Callable[P, R]]: ...


if TYPE_CHECKING:
    flow: _DecoratorLike = _identity_decorator
    task: _DecoratorLike = _identity_decorator
    PREFECT_IMPORT_ERROR: Exception | None = None
else:
    _prefect_import_error: Exception | None = None
    try:
        from prefect import flow as _flow_impl
        from prefect import task as _task_impl
    except Exception as exc:  # pragma: no cover - runtime dependency guard
        _prefect_import_error = exc
        _flow_impl = _identity_decorator
        _task_impl = _identity_decorator

    flow = cast(_DecoratorLike, _flow_impl)
    task = cast(_DecoratorLike, _task_impl)
    PREFECT_IMPORT_ERROR = _prefect_import_error

_yaml_import_error: Exception | None = None
try:
    import yaml as _yaml_impl
except Exception as exc:  # pragma: no cover - runtime dependency guard
    _yaml_import_error = exc
    _yaml_impl = None
yaml = _yaml_impl
YAML_IMPORT_ERROR = _yaml_import_error

_jinja_import_error: Exception | None = None
try:
    from jinja2 import Environment as _Environment
    from jinja2 import StrictUndefined as _StrictUndefined
    from jinja2.runtime import Undefined as _Undefined
except Exception as exc:  # pragma: no cover - runtime dependency guard
    _jinja_import_error = exc
    _Environment = None
    _StrictUndefined = None
    _Undefined = object
Environment = _Environment
StrictUndefined = _StrictUndefined
Undefined = _Undefined
JINJA_IMPORT_ERROR = _jinja_import_error


def build_step_prefix(step: int, node_id: str, attempt: int) -> str:
    return _build_step_prefix_impl(step, node_id, attempt)


def make_codex_log_path(task_log_dir: Path, node_id: str, step: int, attempt: int) -> Path:
    return _make_codex_log_path_impl(task_log_dir, node_id, step, attempt)


def extract_last_non_empty_line(raw_output: str) -> tuple[str, str]:
    return _extract_last_non_empty_line_impl(raw_output)


@task
def load_config(
    config_path: str,
    context_overrides: dict[str, str],
    launch_cwd: str | None = None,
) -> dict[str, Any]:
    return _load_config_impl(
        config_path=config_path,
        context_overrides=context_overrides,
        launch_cwd=launch_cwd,
        yaml_module=yaml,
        yaml_import_error=YAML_IMPORT_ERROR,
    )


@task
def build_prompt_inputs(node: dict[str, Any], runtime_state: dict[str, Any]) -> dict[str, Any]:
    prompt_inputs: dict[str, Any] = {}
    for binding in get_compiled_input_bindings(node):
        prompt_inputs[binding["input_key"]] = resolve_dotted_parts(
            runtime_state,
            binding["source_parts"],
            binding["source"],
        )
    return prompt_inputs


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
        deps=PromptRenderDeps(
            jinja_import_error=JINJA_IMPORT_ERROR,
            environment_cls=Environment,
            strict_undefined_cls=StrictUndefined,
            undefined_type=cast(type[Any], Undefined),
            resolve_dotted_path_func=resolve_dotted_path,
            resolve_path_func=resolve_path,
            read_text_func=read_text,
        ),
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


def execute_step_node(
    *,
    run_ctx: RunExecutionContext,
    step_ctx: WorkflowStepContext,
    artifacts: Any,
) -> StepExecutionResult:
    node = step_ctx.node

    prompt_inputs = build_prompt_inputs(node, run_ctx.runtime_state)
    rendered = render_prompt(
        node["prompt"],
        prompt_inputs,
        run_ctx.config["config_path"],
        node["id"],
        node["prompt_field"],
    )

    codex_log_path = run_codex_exec(
        CodexExecRequest(
            project_root=str(run_ctx.project_root),
            executor_cmd=run_ctx.config["executor"]["cmd"],
            prompt=rendered,
            out_file=str(artifacts.raw_output_path),
            task_log_dir=str(run_ctx.run_log_dir),
            node_id=step_ctx.node_id,
            step=step_ctx.step,
            attempt=step_ctx.attempt,
        )
    )

    raw_output = read_text(artifacts.raw_output_path)
    node_output, pass_flag = resolve_node_output(raw_output, node["parse_output_json"])
    run_ctx.runtime_state["outputs"][step_ctx.node_id] = node_output
    collect_output_history(node, node_output, run_ctx.runtime_state)

    next_node = resolve_next_node(node, pass_flag)
    applied_route_bindings = apply_route_bindings(node, pass_flag, run_ctx.runtime_state)
    return StepExecutionResult(
        rendered_prompt=rendered,
        raw_output_path=artifacts.raw_output_path,
        codex_log_path=codex_log_path,
        node_output=node_output,
        pass_flag=pass_flag,
        next_node=next_node,
        applied_route_bindings=applied_route_bindings,
    )


def execute_workflow_step(
    *,
    run_ctx: RunExecutionContext,
    step_ctx: WorkflowStepContext,
) -> str:
    artifacts = plan_step_artifacts(run_ctx.run_state_dir, step_ctx)
    step_result = execute_step_node(
        run_ctx=run_ctx,
        step_ctx=step_ctx,
        artifacts=artifacts,
    )
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
            step_result.next_node,
            step_ctx.step,
            run_ctx.max_steps,
        ),
    )
    return step_result.next_node


@flow(name="codex_orchestrator")
def run_workflow(
    config_path: str,
    context_overrides: dict[str, str],
    launch_cwd: str | None = None,
) -> dict[str, Any]:
    config = load_config(config_path, context_overrides, launch_cwd)

    run_cfg = config["run"]
    run_workspace = prepare_run_workspace(run_cfg)
    project_root = run_workspace["project_root"]
    state_dir = run_workspace["state_dir"]
    run_id = run_workspace["run_id"]
    run_state_dir = run_workspace["run_state_dir"]
    run_log_dir = run_workspace["run_log_dir"]

    workflow = config["workflow"]
    nodes_by_id = {node["id"]: node for node in workflow["nodes"]}

    runtime_state = create_runtime_state(config["context"]["defaults"])
    initialize_history_targets(workflow["nodes"], runtime_state)
    attempt_counter: dict[str, int] = {}
    steps_executed = 0

    current_node_id = workflow["start"]
    max_steps = run_cfg["max_steps"]
    run_ctx = RunExecutionContext(
        config=config,
        project_root=project_root,
        run_state_dir=run_state_dir,
        run_log_dir=run_log_dir,
        max_steps=max_steps,
        runtime_state=runtime_state,
        attempt_counter=attempt_counter,
    )
    while steps_executed < max_steps and current_node_id != END_NODE:
        step = steps_executed + 1
        node = nodes_by_id[current_node_id]
        step_ctx = build_step_context(
            node=node,
            node_id=current_node_id,
            step=step,
            attempt_counter=attempt_counter,
        )
        current_node_id = execute_workflow_step(
            run_ctx=run_ctx,
            step_ctx=step_ctx,
        )
        steps_executed += 1
    if current_node_id != END_NODE:
        raise RuntimeError(f"Reached max_steps without END: {max_steps}")

    return finalize_run_outputs(
        run_id=run_id,
        run_state_dir=run_state_dir,
        state_dir=state_dir,
        final_node=current_node_id,
        steps_executed=steps_executed,
        outputs=runtime_state["outputs"],
    )


def parse_context_overrides(pairs: list[list[str]] | None) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for raw_key, raw_value in pairs or []:
        key = raw_key.strip()
        if not key:
            raise RuntimeError("context key cannot be empty")
        if "." in key:
            raise RuntimeError(f"context key '{key}' cannot contain '.'")
        overrides[key] = raw_value
    return overrides


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run codex workflow orchestrator from preset config")
    parser.add_argument(
        "--preset",
        required=True,
        help="Built-in preset identifier from repository presets/ (without .yaml), e.g. implement_loop",
    )
    parser.add_argument(
        "--context",
        action="append",
        nargs=2,
        metavar=("KEY", "VALUE"),
        help="Override context.defaults key/value. Repeatable. KEY cannot contain '.'",
    )
    return parser.parse_args()


def format_missing_dependency_error() -> str | None:
    dependency_errors = (
        ("prefect", PREFECT_IMPORT_ERROR),
        ("pyyaml", YAML_IMPORT_ERROR),
        ("jinja2", JINJA_IMPORT_ERROR),
    )
    for dep_name, dep_error in dependency_errors:
        if dep_error is not None:
            return f"Missing dependency: {dep_name} ({dep_error})"
    return None


def fail_with_stderr(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def resolve_main_config(preset: str, context_pairs: list[list[str]] | None) -> tuple[Path, dict[str, str]]:
    context_overrides = parse_context_overrides(context_pairs)
    config_path = resolve_preset_path(preset)
    if not config_path.is_file():
        raise RuntimeError(f"Config file not found: {config_path}")
    return config_path, context_overrides


def main() -> int:
    args = parse_args()

    missing_dependency = format_missing_dependency_error()
    if missing_dependency is not None:
        return fail_with_stderr(missing_dependency)

    try:
        config_path, context_overrides = resolve_main_config(args.preset, args.context)
    except Exception as exc:
        return fail_with_stderr(str(exc))

    try:
        launch_cwd = str(Path.cwd().resolve())
        run_workflow(str(config_path), context_overrides, launch_cwd)
    except Exception as exc:
        return fail_with_stderr(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
