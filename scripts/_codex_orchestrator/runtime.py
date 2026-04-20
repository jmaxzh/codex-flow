from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple, cast

from .dotted_paths import parse_dotted_path, resolve_dotted_parts, set_dotted_parts
from .fileio import write_json, write_text
from .naming import build_step_prefix, make_run_id

END_NODE = "END"


class RunExecutionContext(NamedTuple):
    config: dict[str, Any]
    project_root: Path
    run_state_dir: Path
    run_log_dir: Path
    max_steps: int
    runtime_state: dict[str, Any]
    attempt_counter: dict[str, int]
    node_ids: set[str]


class WorkflowStepContext(NamedTuple):
    node: dict[str, Any]
    node_id: str
    step: int
    attempt: int


class StepArtifactsPlan(NamedTuple):
    prefix: str
    raw_output_path: Path
    prompt_path: Path
    parsed_path: Path
    meta_path: Path
    history_path: Path


class StepExecutionResult(NamedTuple):
    rendered_prompt: str
    raw_output_path: Path
    codex_log_path: str
    node_output: Any
    pass_flag: bool
    next_node: str
    applied_route_bindings: dict[str, str]


def apply_route_bindings(node: dict[str, Any], pass_flag: bool, runtime_state: dict[str, Any]) -> dict[str, str]:
    route_name = "success" if pass_flag else "failure"
    applied: dict[str, str] = {}
    route_bindings_raw = node.get("route_bindings", {})
    if not isinstance(route_bindings_raw, dict):
        raise RuntimeError(f"Node '{node.get('id', '<unknown>')}' route_bindings must be object")
    route_bindings = cast(dict[str, Any], route_bindings_raw)
    selected_bindings_raw = route_bindings.get(route_name, {})
    if not isinstance(selected_bindings_raw, dict):
        raise RuntimeError(f"Node '{node.get('id', '<unknown>')}' route_bindings.{route_name} must be object")

    for target_path_raw, source_path_raw in cast(dict[str, Any], selected_bindings_raw).items():
        target_path = target_path_raw
        source_path = source_path_raw
        source_parts = parse_dotted_path(source_path, f"route_bindings.{route_name}.{target_path}")
        target_parts = parse_dotted_path(target_path, f"route_bindings.{route_name}.{target_path}.target")
        value: Any = resolve_dotted_parts(runtime_state, source_parts, source_path)
        if isinstance(value, dict):
            value = copy.deepcopy(cast(dict[str, Any], value))
        elif isinstance(value, list):
            value = copy.deepcopy(cast(list[Any], value))
        set_dotted_parts(runtime_state, target_parts, target_path, value)
        applied[target_path] = source_path
    return applied


def ensure_history_list(
    runtime_state: dict[str, Any],
    target_path: str,
    target_parts: tuple[str, ...] | None = None,
) -> list[Any]:
    if target_parts is None:
        raise RuntimeError(f"History target missing compiled path: {target_path}")
    parts = target_parts
    current_any: Any
    try:
        current_any = resolve_dotted_parts(runtime_state, parts, target_path)
    except RuntimeError:
        current_any = cast(list[Any], [])
        set_dotted_parts(runtime_state, parts, target_path, current_any)
    if not isinstance(current_any, list):
        raise RuntimeError(f"History target must be array at path: {target_path}")
    current_list: list[Any] = cast(list[Any], current_any)
    return current_list


def collect_output_history(
    node: dict[str, Any],
    node_output: Any,
    runtime_state: dict[str, Any],
) -> str | None:
    history_target = node.get("collect_history_to")
    if history_target is None:
        return None
    if not isinstance(history_target, str):
        raise RuntimeError(f"Node '{node.get('id', '<unknown>')}' collect_history_to must be string")
    target_parts = parse_dotted_path(history_target, f"{node.get('id', '<unknown>')}.collect_history_to")
    current = ensure_history_list(runtime_state, history_target, target_parts)
    current.append(copy.deepcopy(node_output))
    return history_target


def initialize_history_targets(workflow_nodes: list[dict[str, Any]], runtime_state: dict[str, Any]) -> None:
    for node in workflow_nodes:
        history_target = node.get("collect_history_to")
        if history_target is None:
            continue
        if not isinstance(history_target, str):
            raise RuntimeError(f"Node '{node.get('id', '<unknown>')}' collect_history_to must be string")
        ensure_history_list(
            runtime_state,
            history_target,
            parse_dotted_path(history_target, f"{node.get('id', '<unknown>')}.collect_history_to"),
        )


def build_runtime_snapshot(
    runtime_state: dict[str, Any],
    attempt_counter: dict[str, int],
    current_node: str,
    step: int,
    max_steps: int,
) -> dict[str, Any]:
    return {
        "current_node": current_node,
        "step": step,
        "max_steps": max_steps,
        "context": runtime_state["context"],
        "outputs": runtime_state["outputs"],
        "attempt_counter": attempt_counter,
    }


def write_runtime_snapshot(run_state_dir: Path, runtime_snapshot: dict[str, Any]) -> None:
    write_json(run_state_dir / "runtime_state.json", runtime_snapshot)


def prepare_run_workspace(run_cfg: dict[str, Any]) -> dict[str, Any]:
    project_root = Path(run_cfg["project_root"])
    state_dir = Path(run_cfg["state_dir"])
    state_dir.mkdir(parents=True, exist_ok=True)
    run_id = make_run_id()
    run_state_dir = state_dir / "runs" / run_id
    run_state_dir.mkdir(parents=True, exist_ok=True)
    run_log_dir = run_state_dir / "logs" / f"workflow__{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_log_dir.mkdir(parents=True, exist_ok=True)
    print(f"[logs] task log dir: {run_log_dir}", flush=True)
    return {
        "project_root": project_root,
        "state_dir": state_dir,
        "run_id": run_id,
        "run_state_dir": run_state_dir,
        "run_log_dir": run_log_dir,
    }


def create_runtime_state(default_context: dict[str, Any]) -> dict[str, Any]:
    return {
        "context": {"defaults": default_context, "runtime": {}},
        "outputs": {},
    }


def next_attempt(attempt_counter: dict[str, int], node_id: str) -> int:
    attempt = attempt_counter.get(node_id, 0) + 1
    attempt_counter[node_id] = attempt
    return attempt


def build_step_context(
    *,
    node: dict[str, Any],
    node_id: str,
    step: int,
    attempt_counter: dict[str, int],
) -> WorkflowStepContext:
    return WorkflowStepContext(
        node=node,
        node_id=node_id,
        step=step,
        attempt=next_attempt(attempt_counter, node_id),
    )


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


def persist_step_artifacts(
    *,
    artifacts: StepArtifactsPlan,
    rendered_prompt: str,
    node_output: Any,
    meta_payload: dict[str, Any],
    runtime_snapshot: dict[str, Any] | None = None,
) -> dict[str, str]:
    write_text(artifacts.prompt_path, rendered_prompt)
    write_json(artifacts.parsed_path, node_output)
    write_json(artifacts.meta_path, meta_payload)
    with artifacts.history_path.open("a", encoding="utf-8") as history:
        history.write(json.dumps(meta_payload, ensure_ascii=False) + "\n")
    if runtime_snapshot is not None:
        write_runtime_snapshot(artifacts.history_path.parent, runtime_snapshot)
    return {
        "prompt_path": str(artifacts.prompt_path),
        "parsed_path": str(artifacts.parsed_path),
        "meta_path": str(artifacts.meta_path),
    }


def finalize_run_outputs(
    *,
    run_id: str,
    run_state_dir: Path,
    state_dir: Path,
    final_node: str,
    steps_executed: int,
    outputs: dict[str, Any],
) -> dict[str, Any]:
    final_summary = {
        "status": "completed",
        "run_id": run_id,
        "run_state_dir": str(run_state_dir),
        "final_node": final_node,
        "steps_executed": steps_executed,
        "outputs": outputs,
    }
    write_json(run_state_dir / "run_summary.json", final_summary)
    write_json(state_dir / "latest_run.json", {"run_id": run_id, "run_state_dir": str(run_state_dir)})
    write_text(state_dir / "latest_run_id", f"{run_id}\n")
    return final_summary
