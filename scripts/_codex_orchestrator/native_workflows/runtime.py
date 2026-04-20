from __future__ import annotations

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any, NotRequired, TypedDict, cast

from ..dotted_paths import parse_dotted_path, resolve_dotted_parts
from ..executor import CodexExecRequest, run_codex_exec
from ..fileio import read_text
from ..output_processing import resolve_next_node, resolve_node_output
from ..paths import resolve_path
from ..prompting import PromptRenderDeps, render_prompt
from ..runtime import (
    END_NODE,
    RunExecutionContext,
    StepExecutionResult,
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

DEFAULT_EXECUTOR_CMD: list[str] = ["codex", "exec", "--skip-git-repo-check"]

try:
    from jinja2 import Environment, StrictUndefined
    from jinja2.runtime import Undefined
except Exception as exc:  # pragma: no cover - runtime dependency guard
    Environment = None
    StrictUndefined = None
    Undefined = object
    _jinja_import_error: Exception | None = exc
else:
    _jinja_import_error = None
JINJA_IMPORT_ERROR = _jinja_import_error


class StageSpec(TypedDict, total=False):
    id: str
    prompt: str
    prompt_field: str
    input_map: dict[str, str]
    parse_output_json: bool
    on_success: str
    on_failure: str
    collect_history_to: str
    route_bindings: dict[str, dict[str, str]]


def _resolve_dotted_path(data: dict[str, Any], dotted_path: str) -> Any:
    return resolve_dotted_parts(
        data,
        parse_dotted_path(dotted_path, dotted_path),
        dotted_path,
    )


class NormalizedStageSpec(TypedDict):
    id: str
    prompt: str
    prompt_field: str
    input_map: dict[str, str]
    parse_output_json: bool
    on_success: str
    on_failure: str
    collect_history_to: str | None
    route_bindings: dict[str, dict[str, str]]


NextNodeResolver = Callable[[dict[str, Any], bool, str, dict[str, Any], set[str]], str]


class LoopFlowConfig(TypedDict):
    launch_cwd: str
    context_overrides: dict[str, str]
    defaults: dict[str, Any]
    max_steps: int
    start_node: str
    stages: dict[str, StageSpec]
    next_node_resolver: NotRequired[NextNodeResolver]


def _prompt_deps() -> PromptRenderDeps:
    return PromptRenderDeps(
        jinja_import_error=JINJA_IMPORT_ERROR,
        environment_cls=Environment,
        strict_undefined_cls=StrictUndefined,
        undefined_type=cast(type[Any], Undefined),
        resolve_dotted_path_func=_resolve_dotted_path,
        resolve_path_func=resolve_path,
        read_text_func=read_text,
    )


def normalize_stage(node_id: str, stage: StageSpec) -> NormalizedStageSpec:
    if "prompt" not in stage or "on_success" not in stage or "on_failure" not in stage:
        raise RuntimeError(f"Invalid stage definition: {node_id}")
    normalized: NormalizedStageSpec = {
        "id": stage.get("id", node_id),
        "prompt": stage["prompt"],
        "prompt_field": stage.get("prompt_field", f"native_workflow.{node_id}.prompt"),
        "input_map": dict(stage.get("input_map", {})),
        "parse_output_json": stage.get("parse_output_json", True),
        "on_success": stage["on_success"],
        "on_failure": stage["on_failure"],
        "collect_history_to": stage.get("collect_history_to"),
        "route_bindings": {
            "success": dict(stage.get("route_bindings", {}).get("success", {})),
            "failure": dict(stage.get("route_bindings", {}).get("failure", {})),
        },
    }
    return normalized


def validate_stages(start_node: str, nodes_by_id: dict[str, NormalizedStageSpec]) -> None:
    if start_node not in nodes_by_id:
        raise RuntimeError(f"workflow.start target not found: {start_node}")

    node_ids = set(nodes_by_id)
    for node in nodes_by_id.values():
        for edge in ("on_success", "on_failure"):
            target = node[edge]
            if target != END_NODE and target not in node_ids:
                raise RuntimeError(f"Node '{node['id']}' has invalid {edge}: {target}")


def build_prompt_inputs(node: NormalizedStageSpec, runtime_state: dict[str, Any]) -> dict[str, Any]:
    prompt_inputs: dict[str, Any] = {}
    for input_key_raw, source_path_raw in cast(dict[str, Any], node["input_map"]).items():
        input_key = input_key_raw
        source_path = source_path_raw
        source_parts = parse_dotted_path(source_path, f"{node['id']}.input_map.{input_key}")
        prompt_inputs[input_key] = resolve_dotted_parts(runtime_state, source_parts, source_path)
    return prompt_inputs


def execute_step_node(
    *,
    run_ctx: RunExecutionContext,
    step_ctx: Any,
    artifacts: Any,
    prompt_base_dir: Path,
    next_node_resolver: NextNodeResolver | None,
) -> StepExecutionResult:
    node = step_ctx.node

    prompt_inputs = build_prompt_inputs(node, run_ctx.runtime_state)
    rendered = render_prompt(
        node_prompt=node["prompt"],
        prompt_inputs=prompt_inputs,
        config_path=str(prompt_base_dir / "native_workflow.yaml"),
        node_id=node["id"],
        prompt_field=node["prompt_field"],
        deps=_prompt_deps(),
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

    from ..runtime import apply_route_bindings

    next_node = resolve_next_node(node, pass_flag)
    applied_route_bindings = apply_route_bindings(node, pass_flag, run_ctx.runtime_state)
    if next_node_resolver is not None:
        next_node = next_node_resolver(
            node,
            pass_flag,
            next_node,
            run_ctx.runtime_state,
            run_ctx.node_ids,
        )
    if not next_node.strip():
        raise RuntimeError(f"Node '{node['id']}' resolved invalid next node: {next_node}")
    if next_node != END_NODE and next_node not in run_ctx.node_ids:
        raise RuntimeError(f"Node '{node['id']}' resolved invalid next node target: {next_node}")

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
    step_ctx: Any,
    prompt_base_dir: Path,
    next_node_resolver: NextNodeResolver | None = None,
) -> str:
    artifacts = plan_step_artifacts(run_ctx.run_state_dir, step_ctx)
    step_result = execute_step_node(
        run_ctx=run_ctx,
        step_ctx=step_ctx,
        artifacts=artifacts,
        prompt_base_dir=prompt_base_dir,
        next_node_resolver=next_node_resolver,
    )
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


def execute_loop_flow(*, flow_cfg: LoopFlowConfig) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[3]
    project_root = resolve_path(".", Path(flow_cfg["launch_cwd"]).resolve())
    state_dir = resolve_path(".codex-loop-state", project_root)
    workspace = prepare_run_workspace({"project_root": str(project_root), "state_dir": str(state_dir)})

    max_steps = flow_cfg["max_steps"]
    context_data = dict(flow_cfg["context_overrides"])
    max_steps_override = context_data.pop("__max_steps", None)
    if max_steps_override is not None:
        try:
            max_steps = int(max_steps_override)
        except ValueError as exc:
            raise RuntimeError(f"Invalid __max_steps override: {max_steps_override}") from exc
        if max_steps <= 0:
            raise RuntimeError(f"Invalid __max_steps override: {max_steps_override}")

    normalized_defaults = {**flow_cfg["defaults"], **context_data}
    normalized_nodes: dict[str, NormalizedStageSpec] = {
        node_id: normalize_stage(node_id, stage) for node_id, stage in flow_cfg["stages"].items()
    }
    validate_stages(flow_cfg["start_node"], normalized_nodes)

    config = {
        "executor": {"cmd": DEFAULT_EXECUTOR_CMD},
        "context": {"defaults": normalized_defaults},
    }

    runtime_state = create_runtime_state(normalized_defaults)
    initialize_history_targets(cast(list[dict[str, Any]], list(normalized_nodes.values())), runtime_state)
    attempt_counter: dict[str, int] = {}
    steps_executed = 0
    run_ctx = RunExecutionContext(
        config=config,
        project_root=workspace["project_root"],
        run_state_dir=workspace["run_state_dir"],
        run_log_dir=workspace["run_log_dir"],
        max_steps=max_steps,
        runtime_state=runtime_state,
        attempt_counter=attempt_counter,
        node_ids=set(normalized_nodes),
    )

    current_node_id = flow_cfg["start_node"]
    next_node_resolver = flow_cfg.get("next_node_resolver")
    prompt_base_dir = repo_root / "presets" / "prompts"

    while steps_executed < max_steps and current_node_id != END_NODE:
        step = steps_executed + 1
        node = normalized_nodes[current_node_id]
        step_ctx = build_step_context(
            node=cast(dict[str, Any], node),
            node_id=current_node_id,
            step=step,
            attempt_counter=attempt_counter,
        )
        current_node_id = execute_workflow_step(
            run_ctx=run_ctx,
            step_ctx=step_ctx,
            prompt_base_dir=prompt_base_dir,
            next_node_resolver=next_node_resolver,
        )
        steps_executed += 1

    if current_node_id != END_NODE:
        raise RuntimeError(f"Reached max_steps without END: {max_steps}")

    return finalize_run_outputs(
        run_id=workspace["run_id"],
        run_state_dir=workspace["run_state_dir"],
        state_dir=workspace["state_dir"],
        final_node=current_node_id,
        steps_executed=steps_executed,
        outputs=copy.deepcopy(runtime_state["outputs"]),
    )
