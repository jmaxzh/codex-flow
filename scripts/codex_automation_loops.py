#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple, Protocol, cast, overload


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


PRESETS_DIR = "presets"
PRESET_FILE_SUFFIX = ".yaml"
DEFAULT_EXECUTOR_CMD = ["codex", "exec", "--skip-git-repo-check"]
END_NODE = "END"
ALLOWED_SOURCE_PREFIXES = ("context.defaults.", "context.runtime.", "outputs.")
ROUTE_BINDING_TARGET_PREFIX = "context.runtime."


def resolve_path(path_value: str | Path, base_dir: Path) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_dotted_path(data: dict[str, Any], dotted_path: str) -> Any:
    return resolve_dotted_parts(data, parse_dotted_path(dotted_path, dotted_path), dotted_path)


def set_dotted_path(data: dict[str, Any], dotted_path: str, value: Any) -> None:
    set_dotted_parts(data, parse_dotted_path(dotted_path, dotted_path), dotted_path, value)


def sanitize_node_id(node_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", node_id)


def build_step_prefix(step: int, node_id: str, attempt: int) -> str:
    return f"step{step:03d}__{sanitize_node_id(node_id)}__attempt{attempt:02d}"


def make_run_id() -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    return f"run__{ts}"


def make_codex_log_path(task_log_dir: Path, node_id: str, step: int, attempt: int) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    prefix = build_step_prefix(step, node_id, attempt)
    return task_log_dir / f"{prefix}__{ts}.log"


def ensure_dict(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"'{field_name}' must be object")
    return cast(dict[str, Any], value)


def ensure_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"'{field_name}' must be non-empty string")
    return value


def ensure_string_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise RuntimeError(f"'{field_name}' must be non-empty string array")
    raw_items = cast(list[Any], value)
    items: list[str] = []
    for item in raw_items:
        if not isinstance(item, str) or not item:
            raise RuntimeError(f"'{field_name}' must be non-empty string array")
        items.append(item)
    return items


def ensure_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise RuntimeError(f"'{field_name}' must be boolean")
    return value


def ensure_flat_context_map(value: Any, field_name: str) -> dict[str, Any]:
    data = ensure_dict(value, field_name)
    for key, item in data.items():
        if not key:
            raise RuntimeError(f"'{field_name}' keys must be non-empty strings")
        if "." in key:
            raise RuntimeError(f"'{field_name}' key '{key}' cannot contain '.'")
        if isinstance(item, (dict, list)):
            raise RuntimeError(f"'{field_name}.{key}' cannot be object or array")
    return data


def ensure_optional_dict(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    return ensure_dict(value, field_name)


def ensure_string_map(value: Any, field_name: str) -> dict[str, str]:
    data = ensure_dict(value, field_name)
    if not all(isinstance(v, str) for v in data.values()):
        raise RuntimeError(f"{field_name} must be string->string map")
    return cast(dict[str, str], data)


def validate_source_path(path_value: str, field_name: str) -> None:
    if not any(path_value.startswith(prefix) for prefix in ALLOWED_SOURCE_PREFIXES):
        raise RuntimeError(f"'{field_name}' must start with context.defaults. or context.runtime. or outputs.")


def parse_dotted_path(path_value: str, field_name: str) -> tuple[str, ...]:
    parts = tuple(path_value.split("."))
    if not parts or any(not part for part in parts):
        raise RuntimeError(f"Invalid dotted path: {path_value} ({field_name})")
    return parts


def compile_source_binding(source_path: str, field_name: str) -> dict[str, Any]:
    validate_source_path(source_path, field_name)
    return {
        "source": source_path,
        "source_parts": parse_dotted_path(source_path, field_name),
    }


def compile_runtime_target(target_path: str, field_name: str) -> dict[str, Any]:
    if not target_path.startswith(ROUTE_BINDING_TARGET_PREFIX):
        raise RuntimeError(f"{field_name} must start with {ROUTE_BINDING_TARGET_PREFIX}")
    return {
        "target": target_path,
        "target_parts": parse_dotted_path(target_path, field_name),
    }


def format_sorted_keys(keys: set[Any]) -> str:
    key_labels = [key if isinstance(key, str) else repr(key) for key in keys]
    return ", ".join(sorted(key_labels))


def resolve_dotted_parts(data: dict[str, Any], path_parts: tuple[str, ...], dotted_path: str) -> Any:
    current: Any = data
    for part in path_parts:
        if not isinstance(current, dict):
            raise RuntimeError(f"Path not found: {dotted_path}")
        current_obj = cast(dict[str, Any], current)
        if part not in current_obj:
            raise RuntimeError(f"Path not found: {dotted_path}")
        current = current_obj[part]
    return current


def set_dotted_parts(data: dict[str, Any], path_parts: tuple[str, ...], dotted_path: str, value: Any) -> None:
    if not path_parts:
        raise RuntimeError(f"Invalid dotted path: {dotted_path}")

    current: Any = data
    for part in path_parts[:-1]:
        if part not in current:
            current[part] = {}
        elif not isinstance(current[part], dict):
            raise RuntimeError(f"Path conflict: {dotted_path}")
        current = current[part]

    current[path_parts[-1]] = value


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_builtin_presets_dir() -> Path:
    return get_repo_root() / PRESETS_DIR


def list_builtin_preset_identifiers(presets_dir: Path) -> list[str]:
    if not presets_dir.is_dir():
        return []
    return sorted(entry.stem for entry in presets_dir.iterdir() if entry.is_file() and entry.name.endswith(PRESET_FILE_SUFFIX))


def format_available_presets(preset_ids: list[str]) -> str:
    if not preset_ids:
        return "(none found)"
    return ", ".join(preset_ids)


def validate_preset_identifier(preset_value: str) -> str:
    preset_id = preset_value.strip()
    if not preset_id:
        raise RuntimeError("--preset requires a non-empty preset identifier")
    if "/" in preset_id or "\\" in preset_id:
        raise RuntimeError(
            "--preset expects a preset identifier (for example: implement_loop), not a path. "
            "If you used a preset file path before, move or reference that preset under repository "
            "presets/ and pass only its identifier."
        )
    if preset_id.lower().endswith(PRESET_FILE_SUFFIX):
        migration_target = preset_id[: -len(PRESET_FILE_SUFFIX)] or "<preset-id>"
        raise RuntimeError(
            f"--preset accepts extensionless preset identifiers. Use '{migration_target}' instead of '{preset_id}'."
        )
    return preset_id


def resolve_preset_path(preset_value: str) -> Path:
    preset_id = validate_preset_identifier(preset_value)
    presets_dir = get_builtin_presets_dir()
    preset_path = (presets_dir / f"{preset_id}{PRESET_FILE_SUFFIX}").resolve()
    if not preset_path.is_file():
        available = format_available_presets(list_builtin_preset_identifiers(presets_dir))
        raise RuntimeError(
            f"Unknown preset identifier: '{preset_id}'. Available built-in presets: {available}. Lookup directory: {presets_dir}"
        )
    return preset_path


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


def parse_run_config(run_cfg: dict[str, Any], launch_cwd: str | None) -> dict[str, Any]:
    project_root_raw = ensure_string(run_cfg.get("project_root"), "run.project_root")
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
        "collect_history_to": history_target["target"] if history_target else None,
        "route_bindings": normalize_route_bindings(route_bindings_compiled),
        "compiled": {
            "input_bindings": input_bindings,
            "collect_history_target": history_target,
            "route_bindings": route_bindings_compiled,
        },
    }


def validate_workflow_transitions(nodes: list[dict[str, Any]], node_ids: set[str]) -> None:
    for node in nodes:
        for route_key in ("on_success", "on_failure"):
            target = node[route_key]
            if target != END_NODE and target not in node_ids:
                raise RuntimeError(f"Node '{node['id']}' has invalid {route_key}: {target} (must be existing node or END)")


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


@task
def load_config(
    config_path: str,
    context_overrides: dict[str, str],
    launch_cwd: str | None = None,
) -> dict[str, Any]:
    if YAML_IMPORT_ERROR is not None or yaml is None:
        raise RuntimeError(f"Missing dependency: pyyaml ({YAML_IMPORT_ERROR})")
    raw = yaml.safe_load(read_text(Path(config_path)))
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


def stringify_prompt_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(to_plain_prompt_value(value), ensure_ascii=False, indent=2)


class PromptInputsProxy(dict[str, Any]):
    """Dict-like Jinja context where key lookup wins over dict attributes."""

    def __getattribute__(self, name: str) -> Any:
        if name.startswith("_"):
            return object.__getattribute__(self, name)
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def to_plain_prompt_value(value: Any) -> Any:
    if isinstance(value, PromptInputsProxy):
        plain: dict[str, Any] = {}
        for key in value:
            plain[key] = to_plain_prompt_value(value[key])
        return plain
    if isinstance(value, list):
        plain_list: list[Any] = []
        for item in cast(list[Any], value):
            plain_list.append(to_plain_prompt_value(item))
        return plain_list
    return value


def to_prompt_inputs_proxy(value: Any) -> Any:
    if isinstance(value, dict):
        value_dict = cast(dict[str, Any], value)
        return PromptInputsProxy({k: to_prompt_inputs_proxy(v) for k, v in value_dict.items()})
    if isinstance(value, list):
        proxied_list: list[Any] = []
        for item in cast(list[Any], value):
            proxied_list.append(to_prompt_inputs_proxy(item))
        return proxied_list
    return value


def finalize_prompt_value(value: Any) -> Any:
    if isinstance(value, Undefined):
        return value
    return stringify_prompt_value(value)


def prompt_render_error(node_id: str, prompt_field: str, message: str) -> RuntimeError:
    return RuntimeError(f"{prompt_field} (node_id={node_id}) render failed: {message}")


@task
def render_prompt(
    node_prompt: str,
    prompt_inputs: dict[str, Any],
    config_path: str,
    node_id: str,
    prompt_field: str,
) -> str:
    if JINJA_IMPORT_ERROR is not None or Environment is None or StrictUndefined is None:
        raise RuntimeError(f"Missing dependency: jinja2 ({JINJA_IMPORT_ERROR})")

    config_dir = Path(config_path).resolve().parent

    def prompt_input(path_value: Any) -> Any:
        if not isinstance(path_value, str):
            raise RuntimeError(f"prompt_input(path) expects string path, got {type(path_value).__name__}")
        input_path = path_value.strip()
        if not input_path:
            raise RuntimeError("prompt_input(path) expects non-empty path, got empty string")
        return resolve_dotted_path({"inputs": prompt_inputs}, f"inputs.{input_path}")

    def prompt_file(path_value: Any) -> str:
        if not isinstance(path_value, str):
            raise RuntimeError(f"prompt_file(path) expects string path, got {type(path_value).__name__}")
        include_raw = path_value.strip()
        if not include_raw:
            raise RuntimeError("prompt_file(path) expects non-empty relative path, got empty string")

        path_obj = Path(include_raw).expanduser()
        if path_obj.is_absolute():
            raise RuntimeError(
                f"prompt_file(path) only supports relative path, got absolute path: {include_raw}. "
                "Use a path relative to the workflow config file."
            )

        include_path = resolve_path(path_obj, config_dir)
        try:
            return read_text(include_path)
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"prompt_file(path) file not found: {include_raw}. Check the path relative to the workflow config file."
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                f"prompt_file(path) cannot read file: {include_raw} ({exc}). Check file permissions and UTF-8 content."
            ) from exc

    try:
        env = Environment(
            undefined=cast(Any, StrictUndefined),
            autoescape=False,
            finalize=finalize_prompt_value,
        )
        template = env.from_string(node_prompt)
        return template.render(
            inputs=to_prompt_inputs_proxy(prompt_inputs),
            prompt_file=prompt_file,
            prompt_input=prompt_input,
        )
    except Exception as exc:
        raise prompt_render_error(node_id, prompt_field, str(exc)) from exc


@task
def run_codex_exec(
    project_root: str,
    executor_cmd: list[str],
    prompt: str,
    out_file: str,
    task_log_dir: str,
    node_id: str,
    step: int,
    attempt: int,
) -> str:
    project_root_path = Path(project_root)
    out_path = Path(out_file)
    log_path = make_codex_log_path(Path(task_log_dir), node_id, step, attempt)
    process = subprocess.Popen(
        executor_cmd + ["--cd", str(project_root_path), "--output-last-message", str(out_path), "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=project_root_path,
    )

    assert process.stdin is not None
    assert process.stdout is not None

    with log_path.open("wb") as log_file:
        process.stdin.write(prompt.encode("utf-8"))
        process.stdin.close()

        while True:
            chunk = process.stdout.read(8192)
            if not chunk:
                break
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
            log_file.write(chunk)
            log_file.flush()

    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"codex failed: exit={return_code}, log={log_path}")
    if not out_path.is_file():
        raise RuntimeError(f"codex output file missing: {out_path}, log={log_path}")
    return str(log_path)


def extract_last_non_empty_line(raw_output: str) -> tuple[str, str]:
    line_starts: list[int] = []
    lines: list[str] = []
    offset = 0
    for line in raw_output.splitlines(keepends=True):
        line_starts.append(offset)
        lines.append(line)
        offset += len(line)

    if not lines and raw_output:
        line_starts.append(0)
        lines.append(raw_output)

    for index in range(len(lines) - 1, -1, -1):
        line = lines[index]
        line_without_eol = line.rstrip("\r\n")
        if line_without_eol.strip() == "":
            continue
        return raw_output[: line_starts[index]], line_without_eol.strip()

    raise RuntimeError("Output must end with a non-empty line containing JSON")


@task
def parse_and_validate_output(raw_output: str) -> tuple[dict[str, Any], bool]:
    result_text, control_line = extract_last_non_empty_line(raw_output)
    try:
        control = json.loads(control_line)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON on last line: {exc}") from exc

    if not isinstance(control, dict):
        raise RuntimeError("Last-line JSON must be an object")
    control_obj = cast(dict[str, Any], control)
    if "pass" not in control_obj:
        raise RuntimeError("Last-line JSON must contain 'pass' field")
    pass_flag_raw = control_obj["pass"]
    if not isinstance(pass_flag_raw, bool):
        raise RuntimeError("Last-line JSON field 'pass' must be boolean")
    pass_flag = pass_flag_raw
    return {"result": result_text, "control": control_obj}, pass_flag


@task
def resolve_node_output(raw_output: str, parse_output_json: bool) -> tuple[Any, bool]:
    if parse_output_json:
        return parse_and_validate_output(raw_output)
    return raw_output.rstrip(), True


@task
def resolve_next_node(node: dict[str, Any], pass_flag: bool) -> str:
    return node["on_success"] if pass_flag else node["on_failure"]


@task
def apply_route_bindings(node: dict[str, Any], pass_flag: bool, runtime_state: dict[str, Any]) -> dict[str, str]:
    route_name = "success" if pass_flag else "failure"
    applied: dict[str, str] = {}
    for binding in get_compiled_route_bindings(node, route_name):
        target_path = cast(str, binding["target"])
        source_path = cast(str, binding["source"])
        source_parts = cast(tuple[str, ...], binding["source_parts"])
        target_parts = cast(tuple[str, ...], binding["target_parts"])
        value: Any = resolve_dotted_parts(runtime_state, source_parts, source_path)
        if isinstance(value, dict):
            value = copy.deepcopy(cast(dict[str, Any], value))
        elif isinstance(value, list):
            value = copy.deepcopy(cast(list[Any], value))
        set_dotted_parts(runtime_state, target_parts, target_path, value)
        applied[target_path] = source_path
    return applied


@task
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


@task
def collect_output_history(
    node: dict[str, Any],
    node_output: Any,
    runtime_state: dict[str, Any],
) -> str | None:
    history_target = get_compiled_history_target(node)
    if history_target is None:
        return None
    target_path = history_target["target"]
    current = ensure_history_list(runtime_state, target_path, history_target["target_parts"])
    current.append(copy.deepcopy(node_output))
    return target_path


def initialize_history_targets(workflow_nodes: list[dict[str, Any]], runtime_state: dict[str, Any]) -> None:
    for node in workflow_nodes:
        history_target = get_compiled_history_target(node)
        if history_target is None:
            continue
        ensure_history_list(
            runtime_state,
            history_target["target"],
            history_target["target_parts"],
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


class RunExecutionContext(NamedTuple):
    config: dict[str, Any]
    project_root: Path
    run_state_dir: Path
    run_log_dir: Path
    max_steps: int
    runtime_state: dict[str, Any]
    attempt_counter: dict[str, int]


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


def execute_step_node(
    *,
    run_ctx: RunExecutionContext,
    step_ctx: WorkflowStepContext,
    artifacts: StepArtifactsPlan,
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
        str(run_ctx.project_root),
        run_ctx.config["executor"]["cmd"],
        rendered,
        str(artifacts.raw_output_path),
        str(run_ctx.run_log_dir),
        step_ctx.node_id,
        step_ctx.step,
        step_ctx.attempt,
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
