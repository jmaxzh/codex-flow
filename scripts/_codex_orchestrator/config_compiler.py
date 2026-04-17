from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from .dotted_paths import compile_runtime_target, compile_source_binding
from .fileio import read_text
from .paths import resolve_path
from .type_guards import (
    ensure_bool,
    ensure_dict,
    ensure_flat_context_map,
    ensure_optional_dict,
    ensure_string,
    ensure_string_list,
    ensure_string_map,
)

DEFAULT_EXECUTOR_CMD = ["codex", "exec", "--skip-git-repo-check"]
END_NODE = "END"


def format_sorted_keys(keys: set[Any]) -> str:
    key_labels = [key if isinstance(key, str) else repr(key) for key in keys]
    return ", ".join(sorted(key_labels))


def parse_run_config(run_cfg: dict[str, Any], launch_cwd: str | None) -> dict[str, Any]:
    project_root_raw = ensure_string(run_cfg.get("project_root"), "run.project_root")
    # Keep behavior: if launch_cwd provided resolve from it; otherwise from process cwd.
    project_root_base = Path(launch_cwd).resolve() if launch_cwd else Path.cwd().resolve()
    project_root = resolve_path(project_root_raw, project_root_base)
    if not project_root.is_dir():
        raise RuntimeError(f"run.project_root not found: {project_root}")

    state_dir_raw = ensure_string(run_cfg.get("state_dir", ".codex-loop-state"), "run.state_dir")
    state_dir = resolve_path(state_dir_raw, project_root)

    max_steps = run_cfg.get("max_steps")
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps <= 0:
        raise RuntimeError("run.max_steps must be positive integer")

    return {
        "project_root": str(project_root),
        "state_dir": str(state_dir),
        "max_steps": max_steps,
    }


def parse_executor_config(executor_cfg: dict[str, Any]) -> dict[str, Any]:
    executor_cmd_raw = executor_cfg.get("cmd", DEFAULT_EXECUTOR_CMD)
    executor_cmd = ensure_string_list(executor_cmd_raw, "executor.cmd")
    return {"cmd": executor_cmd}


def parse_context_defaults(
    context_cfg: dict[str, Any],
    context_overrides: dict[str, str],
) -> dict[str, Any]:
    defaults_context = ensure_flat_context_map(context_cfg.get("defaults", {}), "context.defaults")
    return {**defaults_context, **context_overrides}


def parse_optional_section(raw_root: dict[str, Any], field_name: str) -> dict[str, Any]:
    return ensure_optional_dict(raw_root.get(field_name), field_name)


def compile_input_bindings(
    input_map_raw: Any,
    node_field_prefix: str,
) -> list[dict[str, Any]]:
    input_map_raw = ensure_string_map(input_map_raw, f"{node_field_prefix}.input_map")

    input_bindings: list[dict[str, Any]] = []
    for input_key, source_path in input_map_raw.items():
        field_name = f"{node_field_prefix}.input_map.{input_key}"
        input_bindings.append(
            {
                "input_key": input_key,
                **compile_source_binding(source_path, field_name),
            }
        )
    return input_bindings


def normalize_input_bindings(input_bindings: list[dict[str, Any]]) -> dict[str, str]:
    return {binding["input_key"]: binding["source"] for binding in input_bindings}


def compile_history_target(
    collect_history_to_raw: Any,
    node_field_prefix: str,
) -> dict[str, Any] | None:
    if collect_history_to_raw is None:
        return None

    collect_history_to = ensure_string(
        collect_history_to_raw,
        f"{node_field_prefix}.collect_history_to",
    )
    return compile_runtime_target(
        collect_history_to,
        f"{node_field_prefix}.collect_history_to",
    )


def compile_route_bindings(
    route_bindings_raw: Any,
    node_field_prefix: str,
) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(route_bindings_raw, dict):
        raise RuntimeError(f"{node_field_prefix}.route_bindings must be object")
    route_bindings_map = cast(dict[str, Any], route_bindings_raw)

    unknown_routes = set(route_bindings_map) - {"success", "failure"}
    if unknown_routes:
        bad = format_sorted_keys(unknown_routes)
        raise RuntimeError(f"{node_field_prefix}.route_bindings has unsupported keys: {bad} (allowed: success,failure)")

    compiled_bindings: dict[str, list[dict[str, Any]]] = {}
    for route_name in ("success", "failure"):
        route_map_raw = route_bindings_map.get(route_name, {})
        route_map_raw = ensure_string_map(
            route_map_raw,
            f"{node_field_prefix}.route_bindings.{route_name}",
        )

        compiled_route: list[dict[str, Any]] = []
        for target_path, source_path in route_map_raw.items():
            source_field = f"{node_field_prefix}.route_bindings.{route_name}.{target_path}"
            compiled_route.append(
                {
                    **compile_runtime_target(target_path, f"{source_field}.target"),
                    **compile_source_binding(source_path, source_field),
                }
            )

        compiled_bindings[route_name] = compiled_route

    return compiled_bindings


def normalize_route_bindings(
    compiled_bindings: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, str]]:
    return {
        route_name: {binding["target"]: binding["source"] for binding in bindings}
        for route_name, bindings in compiled_bindings.items()
    }


def compile_workflow_node(node_raw: Any, idx: int) -> dict[str, Any]:
    node_field_prefix = f"workflow.nodes[{idx}]"
    node = ensure_dict(node_raw, node_field_prefix)
    node_id = ensure_string(node.get("id"), f"{node_field_prefix}.id")
    if node_id == END_NODE:
        raise RuntimeError(f"{node_field_prefix}.id cannot be reserved id: {END_NODE}")

    prompt = ensure_string(node.get("prompt"), f"{node_field_prefix}.prompt")
    input_bindings = compile_input_bindings(node.get("input_map", {}), node_field_prefix)
    on_success = ensure_string(node.get("on_success"), f"{node_field_prefix}.on_success")
    on_failure = ensure_string(node.get("on_failure"), f"{node_field_prefix}.on_failure")
    parse_output_json = ensure_bool(
        node.get("parse_output_json", True),
        f"{node_field_prefix}.parse_output_json",
    )
    history_target = compile_history_target(node.get("collect_history_to"), node_field_prefix)
    route_bindings_compiled = compile_route_bindings(
        node.get("route_bindings", {}),
        node_field_prefix,
    )

    return {
        "id": node_id,
        "prompt": prompt,
        "prompt_field": f"{node_field_prefix}.prompt",
        "input_map": normalize_input_bindings(input_bindings),
        "on_success": on_success,
        "on_failure": on_failure,
        "parse_output_json": parse_output_json,
        "collect_history_to": history_target["target"] if history_target is not None else None,
        "route_bindings": normalize_route_bindings(route_bindings_compiled),
        "compiled": {
            "input_bindings": input_bindings,
            "collect_history_target": history_target,
            "route_bindings": route_bindings_compiled,
        },
    }


def validate_workflow_transitions(nodes: list[dict[str, Any]], node_ids: set[str]) -> None:
    for node in nodes:
        for edge in ("on_success", "on_failure"):
            target = node[edge]
            if target != END_NODE and target not in node_ids:
                raise RuntimeError(f"Node '{node['id']}' has invalid {edge}: {target}")


def get_node_compiled(node: dict[str, Any]) -> dict[str, Any]:
    compiled = node.get("compiled")
    if not isinstance(compiled, dict):
        raise RuntimeError(f"Node '{node.get('id', '<unknown>')}' missing compiled config")
    return cast(dict[str, Any], compiled)


def get_compiled_input_bindings(node: dict[str, Any]) -> list[dict[str, Any]]:
    compiled = get_node_compiled(node)
    bindings = compiled.get("input_bindings")
    if not isinstance(bindings, list):
        raise RuntimeError(f"Node '{node.get('id', '<unknown>')}' missing compiled input_bindings")
    return cast(list[dict[str, Any]], bindings)


def get_compiled_history_target(node: dict[str, Any]) -> dict[str, Any] | None:
    compiled = get_node_compiled(node)
    if "collect_history_target" not in compiled:
        raise RuntimeError(f"Node '{node.get('id', '<unknown>')}' missing compiled collect_history_target")
    target = compiled["collect_history_target"]
    if target is None or isinstance(target, dict):
        return cast(dict[str, Any] | None, target)
    raise RuntimeError(f"Node '{node.get('id', '<unknown>')}' has invalid compiled collect_history_target")


def get_compiled_route_bindings(node: dict[str, Any], route_name: str) -> list[dict[str, Any]]:
    compiled = get_node_compiled(node)
    compiled_routes = compiled.get("route_bindings")
    if not isinstance(compiled_routes, dict):
        raise RuntimeError(f"Node '{node.get('id', '<unknown>')}' missing compiled route_bindings")
    bindings = cast(dict[str, Any], compiled_routes).get(route_name)
    if not isinstance(bindings, list):
        raise RuntimeError(f"Node '{node.get('id', '<unknown>')}' missing compiled route_bindings.{route_name}")
    return cast(list[dict[str, Any]], bindings)


def load_config(
    *,
    config_path: str,
    context_overrides: dict[str, str],
    launch_cwd: str | None,
    yaml_module: Any,
    yaml_import_error: Exception | None,
) -> dict[str, Any]:
    if yaml_import_error is not None or yaml_module is None:
        raise RuntimeError(f"Missing dependency: pyyaml ({yaml_import_error})")
    raw = yaml_module.safe_load(read_text(Path(config_path)))
    if not isinstance(raw, dict):
        raise RuntimeError("Config root must be object")
    raw_obj = cast(dict[str, Any], raw)

    version = raw_obj.get("version")
    if version != 1:
        raise RuntimeError("Config 'version' must be 1")

    run_cfg = parse_run_config(ensure_dict(raw_obj.get("run"), "run"), launch_cwd)
    executor_cfg = parse_executor_config(parse_optional_section(raw_obj, "executor"))
    context_defaults = parse_context_defaults(
        parse_optional_section(raw_obj, "context"),
        context_overrides,
    )
    workflow_cfg = ensure_dict(raw_obj.get("workflow"), "workflow")
    start_node = ensure_string(workflow_cfg.get("start"), "workflow.start")
    nodes_raw = workflow_cfg.get("nodes")
    if not isinstance(nodes_raw, list) or not nodes_raw:
        raise RuntimeError("workflow.nodes must be non-empty array")
    nodes_raw_list = cast(list[Any], nodes_raw)

    nodes: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    for idx, node_raw in enumerate(nodes_raw_list, start=1):
        compiled_node = compile_workflow_node(node_raw, idx)
        node_id = compiled_node["id"]
        if node_id in node_ids:
            raise RuntimeError(f"Duplicate node id: {node_id}")
        node_ids.add(node_id)
        nodes.append(compiled_node)

    if start_node not in node_ids:
        raise RuntimeError(f"workflow.start target not found: {start_node}")

    validate_workflow_transitions(nodes, node_ids)

    return {
        "version": 1,
        "config_path": str(Path(config_path).resolve()),
        "run": run_cfg,
        "executor": executor_cfg,
        "context": {"defaults": context_defaults},
        "workflow": {"start": start_node, "nodes": nodes},
    }
