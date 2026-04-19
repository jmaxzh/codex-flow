from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from .dotted_paths import compile_runtime_target, compile_source_binding
from .fileio import read_text
from .paths import resolve_path, resolve_preset_path, validate_preset_identifier
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
WORKFLOW_ALLOWED_ROOT_FIELDS = ("start", "imports", "node_overrides", "nodes")
WORKFLOW_IMPORT_ALLOWED_FIELDS = ("preset",)
WORKFLOW_OVERRIDE_ALLOWED_FIELDS = ("on_success", "on_failure", "route_bindings", "success_next_node_from")


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


def compile_success_next_node_source(
    success_next_node_from_raw: Any,
    node_field_prefix: str,
) -> dict[str, Any] | None:
    if success_next_node_from_raw is None:
        return None
    success_next_node_from = ensure_string(
        success_next_node_from_raw,
        f"{node_field_prefix}.success_next_node_from",
    )
    return compile_source_binding(
        success_next_node_from,
        f"{node_field_prefix}.success_next_node_from",
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


def compile_partial_route_bindings(
    route_bindings_raw: Any,
    node_field_prefix: str,
) -> dict[str, dict[str, Any]]:
    if not isinstance(route_bindings_raw, dict):
        raise RuntimeError(f"{node_field_prefix}.route_bindings must be object")
    route_bindings_map = cast(dict[str, Any], route_bindings_raw)

    unknown_routes = set(route_bindings_map) - {"success", "failure"}
    if unknown_routes:
        bad = format_sorted_keys(unknown_routes)
        raise RuntimeError(f"{node_field_prefix}.route_bindings has unsupported keys: {bad} (allowed: success,failure)")

    compiled_bindings: dict[str, dict[str, Any]] = {}
    for route_name, route_map_raw in route_bindings_map.items():
        route_field = f"{node_field_prefix}.route_bindings.{route_name}"
        route_map = ensure_string_map(route_map_raw, route_field)
        compiled_route: list[dict[str, Any]] = []
        for target_path, source_path in route_map.items():
            source_field = f"{route_field}.{target_path}"
            compiled_route.append(
                {
                    **compile_runtime_target(target_path, f"{source_field}.target"),
                    **compile_source_binding(source_path, source_field),
                }
            )
        compiled_bindings[route_name] = {
            "compiled": compiled_route,
            "normalized": {binding["target"]: binding["source"] for binding in compiled_route},
        }
    return compiled_bindings


def compile_workflow_node(node_raw: Any, node_field_prefix: str) -> dict[str, Any]:
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
    success_next_node_source = compile_success_next_node_source(
        node.get("success_next_node_from"),
        node_field_prefix,
    )
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
        "success_next_node_from": (success_next_node_source["source"] if success_next_node_source is not None else None),
        "route_bindings": normalize_route_bindings(route_bindings_compiled),
        "compiled": {
            "input_bindings": input_bindings,
            "collect_history_target": history_target,
            "success_next_node_source": success_next_node_source,
            "route_bindings": route_bindings_compiled,
        },
    }


def ensure_allowed_fields(
    payload: dict[str, Any],
    *,
    field_name: str,
    allowed_fields: tuple[str, ...],
) -> None:
    unknown_fields = set(payload) - set(allowed_fields)
    if not unknown_fields:
        return
    bad = format_sorted_keys(unknown_fields)
    allowed = ",".join(allowed_fields)
    raise RuntimeError(f"{field_name} has unsupported keys: {bad} (allowed: {allowed})")


def parse_workflow_imports(
    imports_raw: Any,
) -> list[str]:
    if imports_raw is None:
        return []
    if not isinstance(imports_raw, list):
        raise RuntimeError("workflow.imports must be array")

    imports: list[str] = []
    for idx, entry_raw in enumerate(cast(list[Any], imports_raw), start=1):
        entry_prefix = f"workflow.imports[{idx}]"
        entry = ensure_dict(entry_raw, entry_prefix)
        ensure_allowed_fields(
            entry,
            field_name=entry_prefix,
            allowed_fields=WORKFLOW_IMPORT_ALLOWED_FIELDS,
        )

        preset_value = ensure_string(entry.get("preset"), f"{entry_prefix}.preset")
        try:
            preset_id = validate_preset_identifier(preset_value)
        except RuntimeError as exc:
            raise RuntimeError(f"{entry_prefix}.preset invalid: {exc}") from exc
        imports.append(preset_id)
    return imports


def parse_workflow_node_overrides(
    node_overrides_raw: Any,
) -> dict[str, dict[str, Any]]:
    overrides = ensure_optional_dict(node_overrides_raw, "workflow.node_overrides")

    compiled_overrides: dict[str, dict[str, Any]] = {}
    for node_id_raw, override_raw in overrides.items():
        try:
            node_id = node_id_raw.strip()
        except AttributeError as exc:
            raise RuntimeError("workflow.node_overrides keys must be non-empty strings") from exc
        if not node_id:
            raise RuntimeError("workflow.node_overrides keys must be non-empty strings")
        override_prefix = f"workflow.node_overrides.{node_id}"
        override = ensure_dict(override_raw, override_prefix)
        ensure_allowed_fields(
            override,
            field_name=override_prefix,
            allowed_fields=WORKFLOW_OVERRIDE_ALLOWED_FIELDS,
        )

        compiled_override: dict[str, Any] = {}
        if "on_success" in override:
            compiled_override["on_success"] = ensure_string(
                override["on_success"],
                f"{override_prefix}.on_success",
            )
        if "on_failure" in override:
            compiled_override["on_failure"] = ensure_string(
                override["on_failure"],
                f"{override_prefix}.on_failure",
            )
        if "route_bindings" in override:
            compiled_override["route_bindings"] = compile_partial_route_bindings(
                override["route_bindings"],
                override_prefix,
            )
        if "success_next_node_from" in override:
            compiled_override["success_next_node_source"] = compile_source_binding(
                ensure_string(
                    override["success_next_node_from"],
                    f"{override_prefix}.success_next_node_from",
                ),
                f"{override_prefix}.success_next_node_from",
            )

        compiled_overrides[node_id] = compiled_override
    return compiled_overrides


def compile_imported_nodes(
    *,
    import_idx: int,
    preset_id: str,
    yaml_module: Any,
) -> list[dict[str, Any]]:
    import_prefix = f"workflow.imports[{import_idx}]"
    try:
        preset_path = resolve_preset_path(preset_id)
    except RuntimeError as exc:
        raise RuntimeError(f"{import_prefix}.preset invalid: {exc}") from exc

    imported_raw = yaml_module.safe_load(read_text(preset_path))
    if not isinstance(imported_raw, dict):
        raise RuntimeError(f"{import_prefix}.preset '{preset_id}' root must be object")
    imported_obj = cast(dict[str, Any], imported_raw)

    workflow_cfg = ensure_dict(imported_obj.get("workflow"), f"{import_prefix}.preset '{preset_id}'.workflow")
    ensure_allowed_fields(
        workflow_cfg,
        field_name=f"{import_prefix}.preset '{preset_id}'.workflow",
        allowed_fields=WORKFLOW_ALLOWED_ROOT_FIELDS,
    )
    if "imports" in workflow_cfg:
        raise RuntimeError(f"{import_prefix}.preset '{preset_id}' declares workflow.imports; nested imports are not supported")

    nodes_raw = workflow_cfg.get("nodes")
    if not isinstance(nodes_raw, list):
        raise RuntimeError(f"{import_prefix}.preset '{preset_id}'.workflow.nodes must be array")

    imported_nodes: list[dict[str, Any]] = []
    for node_idx, node_raw in enumerate(cast(list[Any], nodes_raw), start=1):
        imported_nodes.append(
            compile_workflow_node(
                node_raw,
                f"{import_prefix}.preset '{preset_id}'.workflow.nodes[{node_idx}]",
            )
        )
    return imported_nodes


def apply_node_overrides(
    *,
    nodes_by_id: dict[str, dict[str, Any]],
    imported_node_ids: set[str],
    node_overrides: dict[str, dict[str, Any]],
) -> None:
    for node_id, override in node_overrides.items():
        if node_id not in imported_node_ids:
            raise RuntimeError(f"workflow.node_overrides.{node_id} target must be imported node id")

        node = nodes_by_id[node_id]
        if "on_success" in override:
            node["on_success"] = override["on_success"]
        if "on_failure" in override:
            node["on_failure"] = override["on_failure"]
        if "success_next_node_source" in override:
            success_source = cast(dict[str, Any], override["success_next_node_source"])
            node["success_next_node_from"] = success_source["source"]
            get_node_compiled(node)["success_next_node_source"] = success_source
        if "route_bindings" not in override:
            continue

        override_route_bindings = cast(dict[str, dict[str, Any]], override["route_bindings"])
        compiled_route_bindings = cast(dict[str, list[dict[str, Any]]], get_node_compiled(node)["route_bindings"])
        normalized_route_bindings = cast(dict[str, dict[str, str]], node["route_bindings"])
        for route_name, payload in override_route_bindings.items():
            normalized_route_bindings[route_name] = cast(dict[str, str], payload["normalized"])
            compiled_route_bindings[route_name] = cast(list[dict[str, Any]], payload["compiled"])


def append_compiled_node(
    *,
    nodes: list[dict[str, Any]],
    node_ids: set[str],
    nodes_by_id: dict[str, dict[str, Any]],
    node: dict[str, Any],
) -> None:
    node_id = node["id"]
    if node_id in node_ids:
        raise RuntimeError(f"Duplicate node id: {node_id}")
    node_ids.add(node_id)
    nodes_by_id[node_id] = node
    nodes.append(node)


def compose_workflow_nodes(
    *,
    imports: list[str],
    local_nodes_raw_list: list[Any],
    node_overrides: dict[str, dict[str, Any]],
    yaml_module: Any,
) -> tuple[list[dict[str, Any]], set[str]]:
    nodes: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    imported_node_ids: set[str] = set()
    nodes_by_id: dict[str, dict[str, Any]] = {}

    for idx, preset_id in enumerate(imports, start=1):
        imported_nodes = compile_imported_nodes(
            import_idx=idx,
            preset_id=preset_id,
            yaml_module=yaml_module,
        )
        for imported_node in imported_nodes:
            append_compiled_node(
                nodes=nodes,
                node_ids=node_ids,
                nodes_by_id=nodes_by_id,
                node=imported_node,
            )
            imported_node_ids.add(imported_node["id"])

    apply_node_overrides(
        nodes_by_id=nodes_by_id,
        imported_node_ids=imported_node_ids,
        node_overrides=node_overrides,
    )

    for idx, node_raw in enumerate(local_nodes_raw_list, start=1):
        compiled_node = compile_workflow_node(node_raw, f"workflow.nodes[{idx}]")
        append_compiled_node(
            nodes=nodes,
            node_ids=node_ids,
            nodes_by_id=nodes_by_id,
            node=compiled_node,
        )

    return nodes, node_ids


def compile_workflow_config(
    workflow_cfg_raw: Any,
    *,
    yaml_module: Any,
) -> dict[str, Any]:
    workflow_cfg = ensure_dict(workflow_cfg_raw, "workflow")
    ensure_allowed_fields(
        workflow_cfg,
        field_name="workflow",
        allowed_fields=WORKFLOW_ALLOWED_ROOT_FIELDS,
    )

    start_node = ensure_string(workflow_cfg.get("start"), "workflow.start")
    imports = parse_workflow_imports(workflow_cfg.get("imports"))
    node_overrides = parse_workflow_node_overrides(workflow_cfg.get("node_overrides"))

    local_nodes_raw = workflow_cfg.get("nodes", [])
    if not isinstance(local_nodes_raw, list):
        raise RuntimeError("workflow.nodes must be array")
    local_nodes_raw_list = cast(list[Any], local_nodes_raw)

    nodes, node_ids = compose_workflow_nodes(
        imports=imports,
        local_nodes_raw_list=local_nodes_raw_list,
        node_overrides=node_overrides,
        yaml_module=yaml_module,
    )
    if not nodes:
        raise RuntimeError("workflow composition produced empty node set")
    if start_node not in node_ids:
        raise RuntimeError(f"workflow.start target not found: {start_node}")
    validate_workflow_transitions(nodes, node_ids)
    return {"start": start_node, "nodes": nodes}


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


def get_compiled_success_next_node_source(node: dict[str, Any]) -> dict[str, Any] | None:
    compiled = get_node_compiled(node)
    if "success_next_node_source" not in compiled:
        raise RuntimeError(f"Node '{node.get('id', '<unknown>')}' missing compiled success_next_node_source")
    source = compiled["success_next_node_source"]
    if source is None or isinstance(source, dict):
        return cast(dict[str, Any] | None, source)
    raise RuntimeError(f"Node '{node.get('id', '<unknown>')}' has invalid compiled success_next_node_source")


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
    workflow_cfg = compile_workflow_config(
        raw_obj.get("workflow"),
        yaml_module=yaml_module,
    )

    return {
        "version": 1,
        "config_path": str(Path(config_path).resolve()),
        "run": run_cfg,
        "executor": executor_cfg,
        "context": {"defaults": context_defaults},
        "workflow": workflow_cfg,
    }
