from __future__ import annotations

from collections.abc import Callable
from typing import Any

from _codex_orchestrator.native_workflows.presets import (
    run_bug_review_loop_flow,
    run_doc_review_loop_flow,
    run_doc_revise_flow,
    run_implement_loop_flow,
    run_openspec_implement_flow,
    run_openspec_propose_flow,
    run_quality_review_loop_flow,
)

FlowRunner = Callable[[dict[str, str], str, int | None], dict[str, Any]]

BUILTIN_FLOW_REGISTRY: dict[str, FlowRunner] = {
    "doc_doctor": run_doc_revise_flow,
    "doc_review_loop": run_doc_review_loop_flow,
    "bug_review_loop": run_bug_review_loop_flow,
    "implement_loop": run_implement_loop_flow,
    "openspec_implement": run_openspec_implement_flow,
    "openspec_propose": run_openspec_propose_flow,
    "quality_review_loop": run_quality_review_loop_flow,
}


def list_builtin_preset_identifiers() -> list[str]:
    return sorted(BUILTIN_FLOW_REGISTRY)


def get_flow_runner(preset_id: str) -> FlowRunner:
    try:
        return BUILTIN_FLOW_REGISTRY[preset_id]
    except KeyError as exc:
        available = ", ".join(list_builtin_preset_identifiers()) or "(none found)"
        raise RuntimeError(f"Unknown preset identifier: '{preset_id}'. Available built-in presets: {available}.") from exc
