from __future__ import annotations

from typing import Any, cast


def parse_dotted_path(path_value: str, field_name: str) -> tuple[str, ...]:
    parts = tuple(path_value.split("."))
    if not parts or any(not part for part in parts):
        raise RuntimeError(f"Invalid dotted path: {path_value} ({field_name})")
    return parts


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


def resolve_dotted_path(data: dict[str, Any], dotted_path: str) -> Any:
    return resolve_dotted_parts(data, parse_dotted_path(dotted_path, dotted_path), dotted_path)


def set_dotted_path(data: dict[str, Any], dotted_path: str, value: Any) -> None:
    set_dotted_parts(data, parse_dotted_path(dotted_path, dotted_path), dotted_path, value)
