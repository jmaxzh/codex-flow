from __future__ import annotations

from typing import Any, NamedTuple

from _codex_orchestrator.native_workflows.loop_runner import execute_loop_flow
from _codex_orchestrator.native_workflows.preset_common.reviewer_loops import (
    bug_review_loop_stages,
    doc_review_loop_stages,
    quality_review_loop_stages,
)
from _codex_orchestrator.native_workflows.presets.doc_revise import doc_revise_next_node_resolver, doc_revise_stages
from _codex_orchestrator.native_workflows.presets.implement_loop import implement_loop_stages
from _codex_orchestrator.native_workflows.presets.openspec_implement import openspec_implement_stages
from _codex_orchestrator.native_workflows.presets.openspec_propose import (
    openspec_propose_next_node_resolver,
    openspec_propose_stages,
)
from _codex_orchestrator.native_workflows.stage_schema import LoopFlowConfig, NextNodeResolver, StageSpec

DEFAULT_MAX_STEPS = 50


class _FlowSpec(NamedTuple):
    defaults: dict[str, Any]
    start_node: str
    stages: dict[str, StageSpec]
    next_node_resolver: NextNodeResolver | None = None


def _run_flow(
    *,
    context_overrides: dict[str, str],
    launch_cwd: str,
    flow_spec: _FlowSpec,
    max_steps_override: int | None = None,
) -> dict[str, Any]:
    flow_cfg: LoopFlowConfig = LoopFlowConfig(
        launch_cwd=launch_cwd,
        context_overrides=context_overrides,
        defaults=flow_spec.defaults,
        max_steps=DEFAULT_MAX_STEPS,
        max_steps_override=max_steps_override,
        start_node=flow_spec.start_node,
        stages=flow_spec.stages,
    )
    if flow_spec.next_node_resolver is not None:
        flow_cfg["next_node_resolver"] = flow_spec.next_node_resolver
    return execute_loop_flow(flow_cfg=flow_cfg)


def run_doc_revise_flow(
    context_overrides: dict[str, str],
    launch_cwd: str,
    max_steps_override: int | None = None,
) -> dict[str, Any]:
    return _run_flow(
        context_overrides=context_overrides,
        launch_cwd=launch_cwd,
        flow_spec=_FlowSpec(
            defaults={
                "user_instruction": "请修复文档评审发现的问题，直到没有新增问题。",
                "doc_review_fix_node": "doc_revise",
                "doc_review_end_node": "END",
            },
            start_node="doc_review",
            stages=doc_revise_stages(),
            next_node_resolver=doc_revise_next_node_resolver,
        ),
        max_steps_override=max_steps_override,
    )


def run_doc_review_loop_flow(
    context_overrides: dict[str, str],
    launch_cwd: str,
    max_steps_override: int | None = None,
) -> dict[str, Any]:
    return _run_flow(
        context_overrides=context_overrides,
        launch_cwd=launch_cwd,
        flow_spec=_FlowSpec(
            defaults={
                "user_instruction": "请评审未提交文档改动，直到没有新增问题。",
                "role_prompt_file": "doc_reviwer_role.md",
            },
            start_node="doc_review",
            stages=doc_review_loop_stages(),
        ),
        max_steps_override=max_steps_override,
    )


def run_implement_loop_flow(
    context_overrides: dict[str, str],
    launch_cwd: str,
    max_steps_override: int | None = None,
) -> dict[str, Any]:
    return _run_flow(
        context_overrides=context_overrides,
        launch_cwd=launch_cwd,
        flow_spec=_FlowSpec(
            defaults={
                "spec": "docs/prefect-codex-implement-loop-plan.md",
                "user_instruction": "请按规格完成。",
            },
            start_node="implement_first",
            stages=implement_loop_stages(),
        ),
        max_steps_override=max_steps_override,
    )


def run_openspec_implement_flow(
    context_overrides: dict[str, str],
    launch_cwd: str,
    max_steps_override: int | None = None,
) -> dict[str, Any]:
    return _run_flow(
        context_overrides=context_overrides,
        launch_cwd=launch_cwd,
        flow_spec=_FlowSpec(
            defaults={
                "spec": "",
                "user_instruction": "",
            },
            start_node="openspec_implement_first",
            stages=openspec_implement_stages(),
        ),
        max_steps_override=max_steps_override,
    )


def run_openspec_propose_flow(
    context_overrides: dict[str, str],
    launch_cwd: str,
    max_steps_override: int | None = None,
) -> dict[str, Any]:
    return _run_flow(
        context_overrides=context_overrides,
        launch_cwd=launch_cwd,
        flow_spec=_FlowSpec(
            defaults={
                "user_instruction": "请修复文档评审发现的问题，直到没有新增问题。",
                "doc_review_fix_node": "openspec_propose_revise",
                "doc_review_end_node": "END",
            },
            start_node="openspec_propose_review",
            stages=openspec_propose_stages(),
            next_node_resolver=openspec_propose_next_node_resolver,
        ),
        max_steps_override=max_steps_override,
    )


def run_quality_review_loop_flow(
    context_overrides: dict[str, str],
    launch_cwd: str,
    max_steps_override: int | None = None,
) -> dict[str, Any]:
    return _run_flow(
        context_overrides=context_overrides,
        launch_cwd=launch_cwd,
        flow_spec=_FlowSpec(
            defaults={
                "user_instruction": "请评审未提交代码，直到没有新增问题。",
                "role_prompt_file": "arch_reviwer_role.md",
            },
            start_node="quality_review",
            stages=quality_review_loop_stages(),
        ),
        max_steps_override=max_steps_override,
    )


def run_bug_review_loop_flow(
    context_overrides: dict[str, str],
    launch_cwd: str,
    max_steps_override: int | None = None,
) -> dict[str, Any]:
    return _run_flow(
        context_overrides=context_overrides,
        launch_cwd=launch_cwd,
        flow_spec=_FlowSpec(
            defaults={
                "user_instruction": "请 review 未提交代码，直到没有新增问题。",
                "role_prompt_file": "bug_reviwer_role.md",
            },
            start_node="bug_review",
            stages=bug_review_loop_stages(),
        ),
        max_steps_override=max_steps_override,
    )
