from __future__ import annotations

from typing import Any

from .runtime import LoopFlowConfig, StageSpec, execute_loop_flow


def _openspec_implement_stages() -> dict[str, StageSpec]:
    return {
        "openspec_implement_first": {
            "id": "openspec_implement_first",
            "prompt": '{{ prompt_file("./openspec_implement_first.md") }}',
            "input_map": {
                "user_instruction": "context.defaults.user_instruction",
                "spec": "context.defaults.spec",
            },
            "parse_output_json": False,
            "on_success": "openspec_implement_review",
            "on_failure": "END",
        },
        "openspec_implement_review": {
            "id": "openspec_implement_review",
            "prompt": '{{ prompt_file("./openspec_implement_review.md") }}',
            "input_map": {
                "spec": "context.defaults.spec",
            },
            "on_success": "END",
            "on_failure": "openspec_implement_continue",
            "route_bindings": {
                "failure": {
                    "context.runtime.latest_check": "outputs.openspec_implement_review.control",
                }
            },
        },
        "openspec_implement_continue": {
            "id": "openspec_implement_continue",
            "prompt": '{{ prompt_file("./openspec_implement_continue.md") }}',
            "input_map": {
                "spec": "context.defaults.spec",
                "latest_check": "context.runtime.latest_check",
            },
            "parse_output_json": False,
            "on_success": "openspec_implement_review",
            "on_failure": "END",
            "route_bindings": {
                "success": {
                    "context.runtime.latest_impl": "outputs.openspec_implement_continue",
                }
            },
        },
    }


def _reviewer_loop_stage(
    *,
    node_id: str,
    history_key: str,
) -> dict[str, StageSpec]:
    history_path = f"context.runtime.{history_key}"
    return {
        node_id: {
            "id": node_id,
            "prompt": '{{ prompt_file("./shared/reviewer_loop_stage.md") }}',
            "input_map": {
                "user_instruction": "context.defaults.user_instruction",
                "review_history": history_path,
                "role_prompt_file": "context.defaults.role_prompt_file",
            },
            "collect_history_to": history_path,
            "on_success": "END",
            "on_failure": node_id,
        }
    }


def run_openspec_implement_flow(context_overrides: dict[str, str], launch_cwd: str) -> dict[str, Any]:
    return execute_loop_flow(
        flow_cfg=LoopFlowConfig(
            launch_cwd=launch_cwd,
            context_overrides=context_overrides,
            defaults={
                "spec": "",
                "user_instruction": "",
            },
            max_steps=50,
            start_node="openspec_implement_first",
            stages=_openspec_implement_stages(),
        ),
    )


def run_refactor_loop_flow(context_overrides: dict[str, str], launch_cwd: str) -> dict[str, Any]:
    return execute_loop_flow(
        flow_cfg=LoopFlowConfig(
            launch_cwd=launch_cwd,
            context_overrides=context_overrides,
            defaults={
                "user_instruction": "请评审未提交代码，直到没有新增问题。",
                "role_prompt_file": "arch_reviwer_role.md",
            },
            max_steps=50,
            start_node="arch_reviwer",
            stages=_reviewer_loop_stage(
                node_id="arch_reviwer",
                history_key="arch_review_history",
            ),
        ),
    )


def run_reviewer_loop_flow(context_overrides: dict[str, str], launch_cwd: str) -> dict[str, Any]:
    return execute_loop_flow(
        flow_cfg=LoopFlowConfig(
            launch_cwd=launch_cwd,
            context_overrides=context_overrides,
            defaults={
                "user_instruction": "请 review 未提交代码，直到没有新增问题。",
                "role_prompt_file": "bug_reviwer_role.md",
            },
            max_steps=50,
            start_node="bug_reviwer",
            stages=_reviewer_loop_stage(
                node_id="bug_reviwer",
                history_key="bug_review_history",
            ),
        ),
    )


def run_doc_reviewer_loop_flow(context_overrides: dict[str, str], launch_cwd: str) -> dict[str, Any]:
    return execute_loop_flow(
        flow_cfg=LoopFlowConfig(
            launch_cwd=launch_cwd,
            context_overrides=context_overrides,
            defaults={
                "user_instruction": "请评审未提交文档改动，直到没有新增问题。",
                "role_prompt_file": "doc_reviwer_role.md",
            },
            max_steps=50,
            start_node="doc_reviwer",
            stages=_reviewer_loop_stage(
                node_id="doc_reviwer",
                history_key="doc_review_history",
            ),
        ),
    )


def run_openspec_propose_flow(context_overrides: dict[str, str], launch_cwd: str) -> dict[str, Any]:
    def _openspec_propose_next_node_resolver(
        node: dict[str, Any],
        pass_flag: bool,
        default_next_node: str,
        runtime_state: dict[str, Any],
        node_ids: set[str],
    ) -> str:
        if node["id"] != "openspec_propose_review" or not pass_flag:
            return default_next_node
        marker = runtime_state["context"]["runtime"].get("doc_review_next_node")
        if marker is None:
            return default_next_node
        if not isinstance(marker, str) or not marker.strip():
            raise RuntimeError("openspec_propose runtime marker context.runtime.doc_review_next_node must be non-empty string")
        if marker != "END" and marker not in node_ids:
            raise RuntimeError(f"openspec_propose runtime marker resolved invalid target: {marker}")
        return marker

    stages: dict[str, StageSpec] = {
        "openspec_propose_review": {
            "id": "openspec_propose_review",
            "prompt": '{{ prompt_file("./openspec_propose_review.md") }}',
            "input_map": {
                "user_instruction": "context.defaults.user_instruction",
                "doc_review_history": "context.runtime.doc_review_history",
            },
            "collect_history_to": "context.runtime.doc_review_history",
            "on_success": "END",
            "on_failure": "openspec_propose_review",
            "route_bindings": {
                "failure": {
                    "context.runtime.doc_review_next_node": "context.defaults.doc_review_fix_node",
                }
            },
        },
        "openspec_propose_revise": {
            "id": "openspec_propose_revise",
            "prompt": '{{ prompt_file("./openspec_propose_revise.md") }}',
            "input_map": {
                "user_instruction": "context.defaults.user_instruction",
                "doc_review_history": "context.runtime.doc_review_history",
            },
            "parse_output_json": False,
            "on_success": "openspec_propose_review",
            "on_failure": "END",
            "route_bindings": {
                "success": {
                    "context.runtime.doc_review_next_node": "context.defaults.doc_review_end_node",
                }
            },
        },
    }

    return execute_loop_flow(
        flow_cfg=LoopFlowConfig(
            launch_cwd=launch_cwd,
            context_overrides=context_overrides,
            defaults={
                "user_instruction": "请修复文档评审发现的问题，直到没有新增问题。",
                "doc_review_fix_node": "openspec_propose_revise",
                "doc_review_end_node": "END",
            },
            max_steps=50,
            start_node="openspec_propose_review",
            stages=stages,
            next_node_resolver=_openspec_propose_next_node_resolver,
        ),
    )
