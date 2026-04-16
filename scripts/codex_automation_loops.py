#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from prefect import flow, task
except Exception as exc:  # pragma: no cover - runtime dependency guard
    PREFECT_IMPORT_ERROR = exc

    def _identity_decorator(*args: Any, **_kwargs: Any):  # type: ignore[misc]
        if len(args) == 1 and callable(args[0]):
            return args[0]

        def _wrap(func):
            return func

        return _wrap

    flow = _identity_decorator  # type: ignore[assignment]
    task = _identity_decorator  # type: ignore[assignment]
else:
    PREFECT_IMPORT_ERROR = None

try:
    import yaml
except Exception as exc:  # pragma: no cover - runtime dependency guard
    YAML_IMPORT_ERROR = exc
    yaml = None  # type: ignore[assignment]
else:
    YAML_IMPORT_ERROR = None

try:
    from jinja2 import Environment, StrictUndefined
    from jinja2.runtime import Undefined
except Exception as exc:  # pragma: no cover - runtime dependency guard
    JINJA_IMPORT_ERROR = exc
    Environment = None  # type: ignore[assignment]
    StrictUndefined = None  # type: ignore[assignment]
    Undefined = object  # type: ignore[assignment,misc]
else:
    JINJA_IMPORT_ERROR = None


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
    return value


def ensure_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"'{field_name}' must be non-empty string")
    return value


def ensure_string_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(x, str) and x for x in value):
        raise RuntimeError(f"'{field_name}' must be non-empty string array")
    return value


def ensure_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise RuntimeError(f"'{field_name}' must be boolean")
    return value


def ensure_flat_context_map(value: Any, field_name: str) -> dict[str, Any]:
    data = ensure_dict(value, field_name)
    for key, item in data.items():
        if not isinstance(key, str) or not key:
            raise RuntimeError(f"'{field_name}' keys must be non-empty strings")
        if "." in key:
            raise RuntimeError(f"'{field_name}' key '{key}' cannot contain '.'")
        if isinstance(item, (dict, list)):
            raise RuntimeError(f"'{field_name}.{key}' cannot be object or array")
    return data


def validate_source_path(path_value: str, field_name: str) -> None:
    if not any(path_value.startswith(prefix) for prefix in ALLOWED_SOURCE_PREFIXES):
        raise RuntimeError(
            f"'{field_name}' must start with context.defaults. or context.runtime. or outputs."
        )


def parse_dotted_path(path_value: str, field_name: str) -> tuple[str, ...]:
    parts = tuple(path_value.split("."))
    if not parts or any(not part for part in parts):
        raise RuntimeError(f"Invalid dotted path: {path_value} ({field_name})")
    return parts


def resolve_dotted_parts(data: dict[str, Any], path_parts: tuple[str, ...], dotted_path: str) -> Any:
    current: Any = data
    for part in path_parts:
        if not isinstance(current, dict) or part not in current:
            raise RuntimeError(f"Path not found: {dotted_path}")
        current = current[part]
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
    return sorted(
        entry.stem
        for entry in presets_dir.iterdir()
        if entry.is_file() and entry.name.endswith(PRESET_FILE_SUFFIX)
    )


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
            "--preset accepts extensionless preset identifiers. "
            f"Use '{migration_target}' instead of '{preset_id}'."
        )
    return preset_id


def resolve_preset_path(preset_value: str) -> Path:
    preset_id = validate_preset_identifier(preset_value)
    presets_dir = get_builtin_presets_dir()
    preset_path = (presets_dir / f"{preset_id}{PRESET_FILE_SUFFIX}").resolve()
    if not preset_path.is_file():
        available = format_available_presets(list_builtin_preset_identifiers(presets_dir))
        raise RuntimeError(
            f"Unknown preset identifier: '{preset_id}'. "
            f"Available built-in presets: {available}. "
            f"Lookup directory: {presets_dir}"
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


@task
def load_config(
    config_path: str,
    context_overrides: dict[str, str],
    launch_cwd: str | None = None,
) -> dict[str, Any]:
    if YAML_IMPORT_ERROR is not None:
        raise RuntimeError(f"Missing dependency: pyyaml ({YAML_IMPORT_ERROR})")
    raw = yaml.safe_load(read_text(Path(config_path)))
    if not isinstance(raw, dict):
        raise RuntimeError("Config root must be object")

    version = raw.get("version")
    if version != 1:
        raise RuntimeError("Config 'version' must be 1")

    run_cfg = ensure_dict(raw.get("run"), "run")
    workflow_cfg = ensure_dict(raw.get("workflow"), "workflow")

    project_root_raw = ensure_string(run_cfg.get("project_root"), "run.project_root")
    project_root_base = Path(launch_cwd).resolve() if launch_cwd else Path.cwd().resolve()
    project_root = resolve_path(project_root_raw, project_root_base)
    if not project_root.is_dir():
        raise RuntimeError(f"run.project_root not found: {project_root}")

    state_dir_raw = ensure_string(run_cfg.get("state_dir", ".codex-loop-state"), "run.state_dir")
    state_dir = resolve_path(state_dir_raw, project_root)

    max_steps = run_cfg.get("max_steps")
    if not isinstance(max_steps, int) or max_steps <= 0:
        raise RuntimeError("run.max_steps must be positive integer")

    executor_cfg_raw = raw.get("executor") or {}
    executor_cfg = ensure_dict(executor_cfg_raw, "executor")
    executor_cmd_raw = executor_cfg.get("cmd", DEFAULT_EXECUTOR_CMD)
    executor_cmd = ensure_string_list(executor_cmd_raw, "executor.cmd")

    context_cfg_raw = raw.get("context") or {}
    context_cfg = ensure_dict(context_cfg_raw, "context")
    defaults_context = ensure_flat_context_map(context_cfg.get("defaults", {}), "context.defaults")
    merged_defaults_context = {**defaults_context, **context_overrides}

    start_node = ensure_string(workflow_cfg.get("start"), "workflow.start")
    nodes_raw = workflow_cfg.get("nodes")
    if not isinstance(nodes_raw, list) or not nodes_raw:
        raise RuntimeError("workflow.nodes must be non-empty array")

    nodes: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    for idx, node_raw in enumerate(nodes_raw, start=1):
        node = ensure_dict(node_raw, f"workflow.nodes[{idx}]")
        node_id = ensure_string(node.get("id"), f"workflow.nodes[{idx}].id")
        if node_id == END_NODE:
            raise RuntimeError(f"workflow.nodes[{idx}].id cannot be reserved id: {END_NODE}")
        if node_id in node_ids:
            raise RuntimeError(f"Duplicate node id: {node_id}")
        node_ids.add(node_id)

        prompt = ensure_string(node.get("prompt"), f"workflow.nodes[{idx}].prompt")
        input_map = node.get("input_map", {})
        if not isinstance(input_map, dict):
            raise RuntimeError(f"workflow.nodes[{idx}].input_map must be object")
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in input_map.items()):
            raise RuntimeError(f"workflow.nodes[{idx}].input_map must be string->string map")
        input_map_parts: dict[str, tuple[str, ...]] = {}
        for input_key, source_path in input_map.items():
            validate_source_path(source_path, f"workflow.nodes[{idx}].input_map.{input_key}")
            input_map_parts[input_key] = parse_dotted_path(
                source_path, f"workflow.nodes[{idx}].input_map.{input_key}"
            )

        on_success = ensure_string(node.get("on_success"), f"workflow.nodes[{idx}].on_success")
        on_failure = ensure_string(node.get("on_failure"), f"workflow.nodes[{idx}].on_failure")
        parse_output_json = ensure_bool(
            node.get("parse_output_json", True),
            f"workflow.nodes[{idx}].parse_output_json",
        )
        collect_history_to_raw = node.get("collect_history_to")
        collect_history_to: str | None = None
        collect_history_to_parts: tuple[str, ...] | None = None
        if collect_history_to_raw is not None:
            collect_history_to = ensure_string(
                collect_history_to_raw,
                f"workflow.nodes[{idx}].collect_history_to",
            )
            if not collect_history_to.startswith(ROUTE_BINDING_TARGET_PREFIX):
                raise RuntimeError(
                    f"workflow.nodes[{idx}].collect_history_to must start with "
                    f"{ROUTE_BINDING_TARGET_PREFIX}"
                )
            collect_history_to_parts = parse_dotted_path(
                collect_history_to,
                f"workflow.nodes[{idx}].collect_history_to",
            )
        route_bindings_raw = node.get("route_bindings", {})
        if not isinstance(route_bindings_raw, dict):
            raise RuntimeError(f"workflow.nodes[{idx}].route_bindings must be object")

        unknown_routes = set(route_bindings_raw.keys()) - {"success", "failure"}
        if unknown_routes:
            bad = ", ".join(sorted(unknown_routes))
            raise RuntimeError(
                f"workflow.nodes[{idx}].route_bindings has unsupported keys: {bad} (allowed: success,failure)"
            )

        route_bindings: dict[str, dict[str, str]] = {}
        route_bindings_parts: dict[str, list[dict[str, Any]]] = {}
        for route_name in ("success", "failure"):
            route_map_raw = route_bindings_raw.get(route_name, {})
            if not isinstance(route_map_raw, dict):
                raise RuntimeError(
                    f"workflow.nodes[{idx}].route_bindings.{route_name} must be object"
                )
            if not all(isinstance(k, str) and isinstance(v, str) for k, v in route_map_raw.items()):
                raise RuntimeError(
                    f"workflow.nodes[{idx}].route_bindings.{route_name} must be string->string map"
                )

            normalized_map: dict[str, str] = {}
            normalized_bindings_parts: list[dict[str, Any]] = []
            for target_path, source_path in route_map_raw.items():
                if not target_path.startswith(ROUTE_BINDING_TARGET_PREFIX):
                    raise RuntimeError(
                        f"workflow.nodes[{idx}].route_bindings.{route_name} target '{target_path}' "
                        f"must start with {ROUTE_BINDING_TARGET_PREFIX}"
                    )
                validate_source_path(
                    source_path,
                    f"workflow.nodes[{idx}].route_bindings.{route_name}.{target_path}",
                )
                normalized_map[target_path] = source_path
                normalized_bindings_parts.append(
                    {
                        "target": target_path,
                        "source": source_path,
                        "target_parts": parse_dotted_path(
                            target_path,
                            f"workflow.nodes[{idx}].route_bindings.{route_name}.{target_path}.target",
                        ),
                        "source_parts": parse_dotted_path(
                            source_path,
                            f"workflow.nodes[{idx}].route_bindings.{route_name}.{target_path}",
                        ),
                    }
                )
            route_bindings[route_name] = normalized_map
            route_bindings_parts[route_name] = normalized_bindings_parts

        nodes.append(
            {
                "id": node_id,
                "prompt": prompt,
                "prompt_field": f"workflow.nodes[{idx}].prompt",
                "input_map": input_map,
                "input_map_parts": input_map_parts,
                "on_success": on_success,
                "on_failure": on_failure,
                "parse_output_json": parse_output_json,
                "collect_history_to": collect_history_to,
                "collect_history_to_parts": collect_history_to_parts,
                "route_bindings": route_bindings,
                "route_bindings_parts": route_bindings_parts,
            }
        )

    if start_node not in node_ids:
        raise RuntimeError(f"workflow.start target not found: {start_node}")

    for node in nodes:
        for route_key in ("on_success", "on_failure"):
            target = node[route_key]
            if target != END_NODE and target not in node_ids:
                raise RuntimeError(
                    f"Node '{node['id']}' has invalid {route_key}: {target} (must be existing node or END)"
                )

    return {
        "version": 1,
        "config_path": str(Path(config_path).resolve()),
        "run": {
            "project_root": str(project_root),
            "state_dir": str(state_dir),
            "max_steps": max_steps,
        },
        "executor": {"cmd": executor_cmd},
        "context": {"defaults": merged_defaults_context},
        "workflow": {"start": start_node, "nodes": nodes},
    }


@task
def build_prompt_inputs(node: dict[str, Any], runtime_state: dict[str, Any]) -> dict[str, Any]:
    prompt_inputs: dict[str, Any] = {}
    input_map = node.get("input_map", {})
    input_map_parts = node.get("input_map_parts")
    if input_map_parts is None:
        raise RuntimeError(f"Node '{node.get('id', '<unknown>')}' missing compiled input_map_parts")
    for key, source_parts in input_map_parts.items():
        source_path = input_map[key]
        prompt_inputs[key] = resolve_dotted_parts(runtime_state, source_parts, source_path)
    return prompt_inputs


def stringify_prompt_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(to_plain_prompt_value(value), ensure_ascii=False, indent=2)


class PromptInputsProxy(dict[str, Any]):
    """Dict-like Jinja context where key lookup wins over dict attributes."""

    def __getattribute__(self, name: str) -> Any:
        if name.startswith("_"):
            return dict.__getattribute__(self, name)
        if dict.__contains__(self, name):
            return dict.__getitem__(self, name)
        raise AttributeError(name)


def to_plain_prompt_value(value: Any) -> Any:
    if isinstance(value, PromptInputsProxy):
        return {k: to_plain_prompt_value(v) for k, v in dict.items(value)}
    if isinstance(value, list):
        return [to_plain_prompt_value(v) for v in value]
    return value


def to_prompt_inputs_proxy(value: Any) -> Any:
    if isinstance(value, dict):
        return PromptInputsProxy({k: to_prompt_inputs_proxy(v) for k, v in value.items()})
    if isinstance(value, list):
        return [to_prompt_inputs_proxy(v) for v in value]
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
    if JINJA_IMPORT_ERROR is not None:
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
            raise RuntimeError(
                f"prompt_file(path) expects string path, got {type(path_value).__name__}"
            )
        include_raw = path_value.strip()
        if not include_raw:
            raise RuntimeError(
                "prompt_file(path) expects non-empty relative path, got empty string"
            )

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
                f"prompt_file(path) file not found: {include_raw}. "
                "Check the path relative to the workflow config file."
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                f"prompt_file(path) cannot read file: {include_raw} ({exc}). "
                "Check file permissions and UTF-8 content."
            ) from exc

    try:
        env = Environment(
            undefined=StrictUndefined,
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
    if "pass" not in control:
        raise RuntimeError("Last-line JSON must contain 'pass' field")
    pass_flag = control["pass"]
    if not isinstance(pass_flag, bool):
        raise RuntimeError("Last-line JSON field 'pass' must be boolean")
    return {"result": result_text, "control": control}, pass_flag


@task
def resolve_node_output(raw_output: str, parse_output_json: bool) -> tuple[Any, bool]:
    if parse_output_json:
        return parse_and_validate_output(raw_output)
    return raw_output.rstrip(), True


@task
def resolve_next_node(node: dict[str, Any], pass_flag: bool, existing_node_ids: list[str]) -> str:
    next_node = node["on_success"] if pass_flag else node["on_failure"]
    if next_node == END_NODE:
        return END_NODE
    if next_node not in existing_node_ids:
        raise RuntimeError(f"Node '{node['id']}' routes to missing node: {next_node}")
    return next_node


@task
def apply_route_bindings(node: dict[str, Any], pass_flag: bool, runtime_state: dict[str, Any]) -> dict[str, str]:
    route_name = "success" if pass_flag else "failure"
    bindings_parts = node.get("route_bindings_parts", {}).get(route_name)
    if bindings_parts is None:
        raise RuntimeError(f"Node '{node.get('id', '<unknown>')}' missing compiled route_bindings_parts")
    applied: dict[str, str] = {}
    for binding in bindings_parts:
        target_path = binding["target"]
        source_path = binding["source"]
        value = resolve_dotted_parts(runtime_state, binding["source_parts"], source_path)
        if isinstance(value, (dict, list)):
            value = copy.deepcopy(value)
        set_dotted_parts(runtime_state, binding["target_parts"], target_path, value)
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
    try:
        current = resolve_dotted_parts(runtime_state, parts, target_path)
    except RuntimeError:
        current = []
        set_dotted_parts(runtime_state, parts, target_path, current)
    if not isinstance(current, list):
        raise RuntimeError(f"History target must be array at path: {target_path}")
    return current


@task
def collect_output_history(
    node: dict[str, Any],
    node_output: Any,
    runtime_state: dict[str, Any],
) -> str | None:
    target_path = node.get("collect_history_to")
    if not target_path:
        return None
    current = ensure_history_list(runtime_state, target_path, node.get("collect_history_to_parts"))
    current.append(copy.deepcopy(node_output))
    return target_path


def initialize_history_targets(workflow_nodes: list[dict[str, Any]], runtime_state: dict[str, Any]) -> None:
    for node in workflow_nodes:
        target_path = node.get("collect_history_to")
        if not target_path:
            continue
        ensure_history_list(runtime_state, target_path, node.get("collect_history_to_parts"))


@task
def persist_state_and_logs(
    state_dir: str,
    step: int,
    node_id: str,
    attempt: int,
    next_node: str,
    pass_flag: bool,
    rendered_prompt: str,
    raw_output_path: str,
    node_output: Any,
    codex_log_path: str,
    applied_route_bindings: dict[str, str],
) -> dict[str, str]:
    state_root = Path(state_dir)
    prefix = build_step_prefix(step, node_id, attempt)

    prompt_path = state_root / f"{prefix}__prompt.txt"
    parsed_path = state_root / f"{prefix}__parsed.json"
    meta_path = state_root / f"{prefix}__meta.json"
    history_path = state_root / "history.jsonl"

    write_text(prompt_path, rendered_prompt)
    write_json(parsed_path, node_output)
    meta_payload = {
        "step": step,
        "node_id": node_id,
        "attempt": attempt,
        "pass": pass_flag,
        "next_node": next_node,
        "prompt_path": str(prompt_path),
        "raw_output_path": raw_output_path,
        "parsed_output_path": str(parsed_path),
        "codex_log_path": codex_log_path,
        "applied_route_bindings": applied_route_bindings,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(meta_path, meta_payload)
    with history_path.open("a", encoding="utf-8") as history:
        history.write(json.dumps(meta_payload, ensure_ascii=False) + "\n")

    return {
        "prompt_path": str(prompt_path),
        "parsed_path": str(parsed_path),
        "meta_path": str(meta_path),
    }


@flow(name="codex_orchestrator")
def run_workflow(
    config_path: str,
    context_overrides: dict[str, str],
    launch_cwd: str | None = None,
) -> dict[str, Any]:
    config = load_config(config_path, context_overrides, launch_cwd)

    run_cfg = config["run"]
    project_root = Path(run_cfg["project_root"])
    state_dir = Path(run_cfg["state_dir"])
    state_dir.mkdir(parents=True, exist_ok=True)
    run_id = make_run_id()
    run_state_dir = state_dir / "runs" / run_id
    run_state_dir.mkdir(parents=True, exist_ok=True)
    run_log_dir = run_state_dir / "logs" / f"workflow__{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_log_dir.mkdir(parents=True, exist_ok=True)
    print(f"[logs] task log dir: {run_log_dir}", flush=True)

    workflow = config["workflow"]
    nodes_by_id = {node["id"]: node for node in workflow["nodes"]}
    node_ids = list(nodes_by_id.keys())

    runtime_state: dict[str, Any] = {
        "context": {"defaults": config["context"]["defaults"], "runtime": {}},
        "outputs": {},
    }
    initialize_history_targets(workflow["nodes"], runtime_state)
    attempt_counter: dict[str, int] = {}
    steps_executed = 0

    current_node_id = workflow["start"]
    max_steps = run_cfg["max_steps"]
    for step in range(1, max_steps + 1):
        if current_node_id == END_NODE:
            break

        node = nodes_by_id[current_node_id]
        attempt = attempt_counter.get(current_node_id, 0) + 1
        attempt_counter[current_node_id] = attempt
        steps_executed += 1

        prompt_inputs = build_prompt_inputs(node, runtime_state)
        rendered = render_prompt(
            node["prompt"],
            prompt_inputs,
            config["config_path"],
            node["id"],
            node["prompt_field"],
        )

        raw_output_path = run_state_dir / f"{build_step_prefix(step, current_node_id, attempt)}__raw.txt"
        codex_log_path = run_codex_exec(
            str(project_root),
            config["executor"]["cmd"],
            rendered,
            str(raw_output_path),
            str(run_log_dir),
            current_node_id,
            step,
            attempt,
        )

        raw_output = read_text(raw_output_path)
        node_output, pass_flag = resolve_node_output(raw_output, node["parse_output_json"])
        runtime_state["outputs"][current_node_id] = node_output
        collect_output_history(node, node_output, runtime_state)

        next_node = resolve_next_node(node, pass_flag, node_ids)
        applied_route_bindings = apply_route_bindings(node, pass_flag, runtime_state)
        persist_state_and_logs(
            str(run_state_dir),
            step,
            current_node_id,
            attempt,
            next_node,
            pass_flag,
            rendered,
            str(raw_output_path),
            node_output,
            codex_log_path,
            applied_route_bindings,
        )

        write_json(
            run_state_dir / "runtime_state.json",
            {
                "current_node": next_node,
                "step": step,
                "max_steps": max_steps,
                "context": runtime_state["context"],
                "outputs": runtime_state["outputs"],
                "attempt_counter": attempt_counter,
            },
        )
        current_node_id = next_node
        if current_node_id == END_NODE:
            break
    else:
        raise RuntimeError(f"Reached max_steps without END: {max_steps}")

    final_summary = {
        "status": "completed",
        "run_id": run_id,
        "run_state_dir": str(run_state_dir),
        "final_node": current_node_id,
        "steps_executed": steps_executed,
        "outputs": runtime_state["outputs"],
    }
    write_json(run_state_dir / "run_summary.json", final_summary)
    write_json(state_dir / "latest_run.json", {"run_id": run_id, "run_state_dir": str(run_state_dir)})
    write_text(state_dir / "latest_run_id", f"{run_id}\n")
    return final_summary


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


def main() -> int:
    args = parse_args()

    if PREFECT_IMPORT_ERROR is not None:
        print(f"Missing dependency: prefect ({PREFECT_IMPORT_ERROR})", file=sys.stderr)
        return 2
    if YAML_IMPORT_ERROR is not None:
        print(f"Missing dependency: pyyaml ({YAML_IMPORT_ERROR})", file=sys.stderr)
        return 2
    if JINJA_IMPORT_ERROR is not None:
        print(f"Missing dependency: jinja2 ({JINJA_IMPORT_ERROR})", file=sys.stderr)
        return 2

    try:
        context_overrides = parse_context_overrides(args.context)
        config_path = resolve_preset_path(args.preset)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not config_path.is_file():
        print(f"Config file not found: {config_path}", file=sys.stderr)
        return 2

    try:
        launch_cwd = str(Path.cwd().resolve())
        run_workflow(str(config_path), context_overrides, launch_cwd)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
