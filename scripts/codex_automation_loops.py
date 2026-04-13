#!/usr/bin/env python3
from __future__ import annotations

import argparse
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


CONFIG_FILE = "orchestrator.yaml"
DEFAULT_EXECUTOR_CMD = ["codex", "exec", "--skip-git-repo-check"]
END_NODE = "END"
PROMPT_VAR_PATTERN = re.compile(r"{{\s*([^{}]+?)\s*}}")


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
    current: Any = data
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise RuntimeError(f"Path not found: {dotted_path}")
        current = current[part]
    return current


def make_codex_log_path(task_log_dir: Path, node_id: str, step: int, attempt: int) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    safe_node = re.sub(r"[^a-zA-Z0-9_-]", "_", node_id)
    return task_log_dir / f"{safe_node}__step{step:03d}__attempt{attempt:02d}__{ts}.log"


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


@task
def load_config(config_path: str) -> dict[str, Any]:
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
    project_root = resolve_path(project_root_raw, Path(config_path).parent)
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
    static_context = context_cfg.get("static", {})
    if not isinstance(static_context, dict):
        raise RuntimeError("context.static must be object")

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

        on_success = ensure_string(node.get("on_success"), f"workflow.nodes[{idx}].on_success")
        on_failure = ensure_string(node.get("on_failure"), f"workflow.nodes[{idx}].on_failure")
        nodes.append(
            {
                "id": node_id,
                "prompt": prompt,
                "input_map": input_map,
                "on_success": on_success,
                "on_failure": on_failure,
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
        "run": {
            "project_root": str(project_root),
            "state_dir": str(state_dir),
            "max_steps": max_steps,
        },
        "executor": {"cmd": executor_cmd},
        "context": {"static": static_context},
        "workflow": {"start": start_node, "nodes": nodes},
    }


@task
def build_prompt_inputs(node: dict[str, Any], runtime_state: dict[str, Any]) -> dict[str, Any]:
    prompt_inputs: dict[str, Any] = {}
    for key, source_path in node["input_map"].items():
        if not source_path.startswith("context.static.") and not source_path.startswith("outputs."):
            raise RuntimeError(
                f"Node '{node['id']}' input_map path '{source_path}' must start with context.static. or outputs."
            )
        prompt_inputs[key] = resolve_dotted_path(runtime_state, source_path)
    return prompt_inputs


def stringify_prompt_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2)


@task
def render_prompt(node_prompt: str, prompt_inputs: dict[str, Any]) -> str:
    def replace_var(match: re.Match[str]) -> str:
        expr = match.group(1).strip()
        if not expr.startswith("inputs."):
            raise RuntimeError(f"Unsupported template variable: {{{{{expr}}}}}")
        input_path = expr[len("inputs.") :]
        if not input_path:
            raise RuntimeError("Template variable cannot be empty")
        value = resolve_dotted_path({"inputs": prompt_inputs}, f"inputs.{input_path}")
        return stringify_prompt_value(value)

    return PROMPT_VAR_PATTERN.sub(replace_var, node_prompt)


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


@task
def parse_and_validate_output(raw_output: str) -> tuple[dict[str, Any], bool]:
    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON output: {exc}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Output JSON must be an object")
    if "pass" not in payload:
        raise RuntimeError("Output JSON must contain 'pass' field")
    pass_flag = payload["pass"]
    if not isinstance(pass_flag, bool):
        raise RuntimeError("Output JSON field 'pass' must be boolean")
    return payload, pass_flag


@task
def resolve_next_node(node: dict[str, Any], pass_flag: bool, existing_node_ids: list[str]) -> str:
    next_node = node["on_success"] if pass_flag else node["on_failure"]
    if next_node == END_NODE:
        return END_NODE
    if next_node not in existing_node_ids:
        raise RuntimeError(f"Node '{node['id']}' routes to missing node: {next_node}")
    return next_node


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
    parsed_output: dict[str, Any],
    codex_log_path: str,
) -> dict[str, str]:
    state_root = Path(state_dir)
    safe_node = re.sub(r"[^a-zA-Z0-9_-]", "_", node_id)
    prefix = f"step{step:03d}__{safe_node}__attempt{attempt:02d}"

    prompt_path = state_root / f"{prefix}__prompt.txt"
    parsed_path = state_root / f"{prefix}__parsed.json"
    meta_path = state_root / f"{prefix}__meta.json"
    history_path = state_root / "history.jsonl"

    write_text(prompt_path, rendered_prompt)
    write_json(parsed_path, parsed_output)
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
def run_workflow() -> dict[str, Any]:
    config_path = Path.cwd() / CONFIG_FILE
    config = load_config(str(config_path))

    run_cfg = config["run"]
    project_root = Path(run_cfg["project_root"])
    state_dir = Path(run_cfg["state_dir"])
    state_dir.mkdir(parents=True, exist_ok=True)
    run_log_dir = state_dir / "logs" / f"workflow__{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_log_dir.mkdir(parents=True, exist_ok=True)
    print(f"[logs] task log dir: {run_log_dir}", flush=True)

    workflow = config["workflow"]
    nodes_by_id = {node["id"]: node for node in workflow["nodes"]}
    node_ids = list(nodes_by_id.keys())

    runtime_state: dict[str, Any] = {
        "context": {"static": config["context"]["static"]},
        "outputs": {},
    }
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
        rendered = render_prompt(node["prompt"], prompt_inputs)

        safe_node = re.sub(r"[^a-zA-Z0-9_-]", "_", current_node_id)
        raw_output_path = state_dir / f"step{step:03d}__{safe_node}__attempt{attempt:02d}__raw.txt"
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
        parsed_output, pass_flag = parse_and_validate_output(raw_output)
        runtime_state["outputs"][current_node_id] = parsed_output

        next_node = resolve_next_node(node, pass_flag, node_ids)
        persist_state_and_logs(
            str(state_dir),
            step,
            current_node_id,
            attempt,
            next_node,
            pass_flag,
            rendered,
            str(raw_output_path),
            parsed_output,
            codex_log_path,
        )

        write_json(
            state_dir / "runtime_state.json",
            {
                "current_node": next_node,
                "step": step,
                "max_steps": max_steps,
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
        "final_node": current_node_id,
        "steps_executed": steps_executed,
        "outputs": runtime_state["outputs"],
    }
    write_json(state_dir / "run_summary.json", final_summary)
    return final_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run codex workflow orchestrator from ./orchestrator.yaml"
    )
    return parser.parse_args()


def main() -> int:
    parse_args()  # Keep CLI minimal: no business arguments.

    if PREFECT_IMPORT_ERROR is not None:
        print(f"Missing dependency: prefect ({PREFECT_IMPORT_ERROR})", file=sys.stderr)
        return 2
    if YAML_IMPORT_ERROR is not None:
        print(f"Missing dependency: pyyaml ({YAML_IMPORT_ERROR})", file=sys.stderr)
        return 2

    config_path = Path.cwd() / CONFIG_FILE
    if not config_path.is_file():
        print(f"Config file not found: {config_path}", file=sys.stderr)
        return 2

    try:
        run_workflow()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
