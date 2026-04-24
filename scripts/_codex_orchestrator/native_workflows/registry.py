from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .presets import (
    run_doc_reviewer_loop_flow,
    run_openspec_implement_flow,
    run_openspec_propose_flow,
    run_refactor_loop_flow,
    run_reviewer_loop_flow,
)

FlowRunner = Callable[[dict[str, str], str], dict[str, Any]]

BUILTIN_FLOW_REGISTRY: dict[str, FlowRunner] = {
    "openspec_implement": run_openspec_implement_flow,
    "openspec_propose": run_openspec_propose_flow,
    "refactor_loop": run_refactor_loop_flow,
    "reviewer_loop": run_reviewer_loop_flow,
    "doc_reviewer_loop": run_doc_reviewer_loop_flow,
}


def list_builtin_preset_identifiers() -> list[str]:
    return sorted(BUILTIN_FLOW_REGISTRY)


def get_flow_runner(preset_id: str) -> FlowRunner:
    try:
        return BUILTIN_FLOW_REGISTRY[preset_id]
    except KeyError as exc:
        available = ", ".join(list_builtin_preset_identifiers()) or "(none found)"
        raise RuntimeError(f"Unknown preset identifier: '{preset_id}'. Available built-in presets: {available}.") from exc
