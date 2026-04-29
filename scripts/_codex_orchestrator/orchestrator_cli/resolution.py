from __future__ import annotations

from collections.abc import Mapping

from _codex_orchestrator.native_workflows.context_overrides import parse_max_steps_override as _parse_max_steps_override
from _codex_orchestrator.native_workflows.context_overrides import (
    split_context_overrides_and_max_steps_override as _split_context_overrides_and_max_steps_override,
)
from _codex_orchestrator.native_workflows.registry import list_builtin_preset_identifiers
from _codex_orchestrator.orchestrator_cli.parsing import parse_context_overrides
from _codex_orchestrator.preset_identifier import validate_preset_identifier


def resolve_main_config(preset: str, context_pairs: list[list[str]] | None) -> tuple[str, dict[str, str]]:
    context_overrides = parse_context_overrides(context_pairs)
    preset_id = validate_preset_identifier(preset)
    builtin_preset_ids = list_builtin_preset_identifiers()
    if preset_id not in builtin_preset_ids:
        available = ", ".join(builtin_preset_ids) or "(none found)"
        raise RuntimeError(f"Unknown preset identifier: '{preset_id}'. Available built-in presets: {available}.")
    return preset_id, context_overrides


def parse_max_steps_override(raw_max_steps_override: str | None) -> int | None:
    return _parse_max_steps_override(raw_max_steps_override)


def split_context_overrides_and_max_steps_override(
    context_overrides: Mapping[str, str],
) -> tuple[dict[str, str], int | None]:
    return _split_context_overrides_and_max_steps_override(context_overrides)
