from __future__ import annotations

import json
from typing import Any, cast


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


def resolve_node_output(raw_output: str, parse_output_json: bool) -> tuple[Any, bool]:
    if parse_output_json:
        return parse_and_validate_output(raw_output)
    return raw_output.rstrip(), True


def resolve_next_node(node: dict[str, Any], pass_flag: bool) -> str:
    return node["on_success"] if pass_flag else node["on_failure"]
