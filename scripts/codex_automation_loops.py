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

from _codex_orchestrator.dotted_paths import (
    resolve_dotted_parts,
    resolve_dotted_path,
)
from _codex_orchestrator.executor import CodexExecRequest
from _codex_orchestrator.executor import run_codex_exec as _run_codex_exec_impl
from _codex_orchestrator.fileio import read_text
from _codex_orchestrator.naming import (
    build_step_prefix as _build_step_prefix_impl,
)
from _codex_orchestrator.naming import (
    make_codex_log_path as _make_codex_log_path_impl,
)
from _codex_orchestrator.native_workflows.registry import (
    get_flow_runner,
    list_builtin_preset_identifiers,
)
from _codex_orchestrator.native_workflows.runtime import (
    validate_stages as _validate_stages_impl,
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
from _codex_orchestrator.paths import resolve_path, validate_preset_identifier
from _codex_orchestrator.prompting import PromptRenderDeps
from _codex_orchestrator.prompting import render_prompt as _render_prompt_impl
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
def build_prompt_inputs(node: dict[str, Any], runtime_state: dict[str, Any]) -> dict[str, Any]:
    prompt_inputs: dict[str, Any] = {}
    input_map_raw = node.get("input_map", {})
    if not isinstance(input_map_raw, dict):
        raise RuntimeError(f"Node '{node.get('id', '<unknown>')}' input_map must be object")

    for input_key_raw, source_path_raw in cast(dict[str, Any], input_map_raw).items():
        input_key = input_key_raw
        source_path = source_path_raw
        source_parts = tuple(source_path.split("."))
        prompt_inputs[input_key] = resolve_dotted_parts(runtime_state, source_parts, source_path)
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


def validate_stages(start_node: str, nodes_by_id: dict[str, dict[str, Any]]) -> None:
    _validate_stages_impl(start_node, cast(Any, nodes_by_id))


@flow(name="codex_orchestrator")
def run_workflow(
    preset_id: str,
    context_overrides: dict[str, str],
    launch_cwd: str | None = None,
) -> dict[str, Any]:
    launch_cwd_resolved = str(Path(launch_cwd).resolve()) if launch_cwd else str(Path.cwd().resolve())
    runner = get_flow_runner(preset_id)
    return runner(context_overrides, launch_cwd_resolved)


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
    parser = argparse.ArgumentParser(description="Run codex workflow orchestrator from built-in preset")
    parser.add_argument(
        "--preset",
        required=True,
        help="Built-in preset identifier, e.g. implement_loop",
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
        ("jinja2", JINJA_IMPORT_ERROR),
    )
    for dep_name, dep_error in dependency_errors:
        if dep_error is not None:
            return f"Missing dependency: {dep_name} ({dep_error})"
    return None


def fail_with_stderr(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def resolve_main_config(preset: str, context_pairs: list[list[str]] | None) -> tuple[str, dict[str, str]]:
    context_overrides = parse_context_overrides(context_pairs)
    preset_id = validate_preset_identifier(preset)
    # Validate against built-ins early for actionable CLI diagnostics.
    if preset_id not in set(list_builtin_preset_identifiers()):
        available = ", ".join(list_builtin_preset_identifiers()) or "(none found)"
        raise RuntimeError(f"Unknown preset identifier: '{preset_id}'. Available built-in presets: {available}.")
    return preset_id, context_overrides


def main() -> int:
    args = parse_args()

    missing_dependency = format_missing_dependency_error()
    if missing_dependency is not None:
        return fail_with_stderr(missing_dependency)

    try:
        preset_id, context_overrides = resolve_main_config(args.preset, args.context)
    except Exception as exc:
        return fail_with_stderr(str(exc))

    try:
        launch_cwd = str(Path.cwd().resolve())
        run_workflow(preset_id, context_overrides, launch_cwd)
    except Exception as exc:
        return fail_with_stderr(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
