from __future__ import annotations

from _codex_orchestrator.native_workflows.preset_common.common import reviewer_loop_stage
from _codex_orchestrator.native_workflows.stage_schema import StageSpec


def quality_review_loop_stages() -> dict[str, StageSpec]:
    return reviewer_loop_stage(
        node_id="quality_review",
        history_key="quality_review_history",
    )


def bug_review_loop_stages() -> dict[str, StageSpec]:
    return reviewer_loop_stage(
        node_id="bug_review",
        history_key="bug_review_history",
    )


def doc_review_loop_stages() -> dict[str, StageSpec]:
    return reviewer_loop_stage(
        node_id="doc_review",
        history_key="doc_review_history",
    )
