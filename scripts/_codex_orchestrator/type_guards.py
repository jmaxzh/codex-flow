from __future__ import annotations

from typing import Any, cast


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
