from __future__ import annotations

from collections.abc import Mapping


def parse_max_steps_override(raw_max_steps_override: str | None) -> int | None:
    if raw_max_steps_override is None:
        return None
    try:
        return int(raw_max_steps_override)
    except ValueError as exc:
        raise RuntimeError(f"Invalid __max_steps override: {raw_max_steps_override}") from exc


def split_context_overrides_and_max_steps_override(
    context_overrides: Mapping[str, str],
) -> tuple[dict[str, str], int | None]:
    context_data = dict(context_overrides)
    raw_max_steps_override = context_data.pop("__max_steps", None)
    return context_data, parse_max_steps_override(raw_max_steps_override)
