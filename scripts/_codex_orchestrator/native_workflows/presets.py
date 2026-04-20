from __future__ import annotations

from typing import Any

from .runtime import LoopFlowConfig, StageSpec, execute_loop_flow


def _implement_loop_stages() -> dict[str, StageSpec]:
    return {
        "implement_first": {
            "id": "implement_first",
            "prompt": """
任务: {{ inputs.spec }}
用户要求: {{ inputs.user_instruction }}

{{ prompt_file("./shared/implementer_role.md") }}
""".strip(),
            "input_map": {
                "user_instruction": "context.defaults.user_instruction",
                "spec": "context.defaults.spec",
            },
            "parse_output_json": False,
            "on_success": "check",
            "on_failure": "END",
        },
        "check": {
            "id": "check",
            "prompt": """
任务: {{ inputs.spec }}

{{ prompt_file("./shared/implementer_checker_role.md") }}

若全部完成，pass=true，否则 pass=false，
最后一行输出严格 JSON object（不要使用代码块）：
{"pass": true/false}
""".strip(),
            "input_map": {
                "spec": "context.defaults.spec",
            },
            "on_success": "END",
            "on_failure": "implement_loop",
            "route_bindings": {
                "failure": {
                    "context.runtime.latest_check": "outputs.check.control",
                }
            },
        },
        "implement_loop": {
            "id": "implement_loop",
            "prompt": """
任务: {{ inputs.spec }}
未完成部分: {{ inputs.latest_check }}

{{ prompt_file("./shared/implementer_role.md") }}

继续实现任务的未完成部分。
""".strip(),
            "input_map": {
                "spec": "context.defaults.spec",
                "latest_check": "context.runtime.latest_check",
            },
            "parse_output_json": False,
            "on_success": "check",
            "on_failure": "END",
            "route_bindings": {
                "success": {
                    "context.runtime.latest_impl": "outputs.implement_loop",
                }
            },
        },
    }


def _reviewer_loop_stage(
    *,
    node_id: str,
    prompt_file: str,
    user_instruction: str,
    history_key: str,
) -> dict[str, StageSpec]:
    history_path = f"context.runtime.{history_key}"
    return {
        node_id: {
            "id": node_id,
            "prompt": f"""
用户指令: {{{{ inputs.user_instruction }}}}
历史评审输出: {{{{ inputs.{history_key} }}}}

{{{{ prompt_file("./shared/{prompt_file}") }}}}

仅输出“本轮新增问题（含代码位置）”，不要重复历史中已发现的问题。
若无新增问题，pass=true，否则 pass=false，
最后一行输出严格 JSON object（不要使用代码块）：
{{"pass": true/false}}
""".strip(),
            "input_map": {
                "user_instruction": "context.defaults.user_instruction",
                history_key: history_path,
            },
            "collect_history_to": history_path,
            "on_success": "END",
            "on_failure": node_id,
        }
    }


def run_implement_loop_flow(context_overrides: dict[str, str], launch_cwd: str) -> dict[str, Any]:
    return execute_loop_flow(
        flow_cfg=LoopFlowConfig(
            launch_cwd=launch_cwd,
            context_overrides=context_overrides,
            defaults={
                "spec": "docs/prefect-codex-implement-loop-plan.md",
                "user_instruction": "请按规格完成。",
            },
            max_steps=50,
            start_node="implement_first",
            stages=_implement_loop_stages(),
        ),
    )


def run_refactor_loop_flow(context_overrides: dict[str, str], launch_cwd: str) -> dict[str, Any]:
    return execute_loop_flow(
        flow_cfg=LoopFlowConfig(
            launch_cwd=launch_cwd,
            context_overrides=context_overrides,
            defaults={
                "user_instruction": "请评审未提交代码，直到没有新增问题。",
            },
            max_steps=50,
            start_node="arch_reviwer",
            stages=_reviewer_loop_stage(
                node_id="arch_reviwer",
                prompt_file="arch_reviwer_role.md",
                user_instruction="请评审未提交代码，直到没有新增问题。",
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
            },
            max_steps=50,
            start_node="bug_reviwer",
            stages=_reviewer_loop_stage(
                node_id="bug_reviwer",
                prompt_file="bug_reviwer_role.md",
                user_instruction="请 review 未提交代码，直到没有新增问题。",
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
            },
            max_steps=50,
            start_node="doc_reviwer",
            stages=_reviewer_loop_stage(
                node_id="doc_reviwer",
                prompt_file="doc_reviwer_role.md",
                user_instruction="请评审未提交文档改动，直到没有新增问题。",
                history_key="doc_review_history",
            ),
        ),
    )


def run_doc_doctor_flow(context_overrides: dict[str, str], launch_cwd: str) -> dict[str, Any]:
    def _doc_doctor_next_node_resolver(
        node: dict[str, Any],
        pass_flag: bool,
        default_next_node: str,
        runtime_state: dict[str, Any],
        node_ids: set[str],
    ) -> str:
        if node["id"] != "doc_reviwer" or not pass_flag:
            return default_next_node
        marker = runtime_state["context"]["runtime"].get("doc_review_next_node")
        if marker is None:
            return default_next_node
        if not isinstance(marker, str) or not marker.strip():
            raise RuntimeError("doc_doctor runtime marker context.runtime.doc_review_next_node must be non-empty string")
        if marker != "END" and marker not in node_ids:
            raise RuntimeError(f"doc_doctor runtime marker resolved invalid target: {marker}")
        return marker

    stages: dict[str, StageSpec] = {
        "doc_reviwer": {
            "id": "doc_reviwer",
            "prompt": """
用户指令: {{ inputs.user_instruction }}
历史评审输出: {{ inputs.doc_review_history }}

{{ prompt_file("./shared/doc_reviwer_role.md") }}

仅输出“本轮新增问题（含文档位置）”，不要重复历史中已发现的问题。
若无新增问题，pass=true，否则 pass=false，
最后一行输出严格 JSON object（不要使用代码块）：
{"pass": true/false}
""".strip(),
            "input_map": {
                "user_instruction": "context.defaults.user_instruction",
                "doc_review_history": "context.runtime.doc_review_history",
            },
            "collect_history_to": "context.runtime.doc_review_history",
            "on_success": "END",
            "on_failure": "doc_reviwer",
            "route_bindings": {
                "failure": {
                    "context.runtime.doc_review_next_node": "context.defaults.doc_review_fix_node",
                }
            },
        },
        "doc_fix": {
            "id": "doc_fix",
            "prompt": """
用户指令: {{ inputs.user_instruction }}
全量历史评审输出: {{ inputs.doc_review_history }}

{{ prompt_file("./shared/doc_fix_role.md") }}
""".strip(),
            "input_map": {
                "user_instruction": "context.defaults.user_instruction",
                "doc_review_history": "context.runtime.doc_review_history",
            },
            "parse_output_json": False,
            "on_success": "doc_reviwer",
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
                "doc_review_fix_node": "doc_fix",
                "doc_review_end_node": "END",
            },
            max_steps=50,
            start_node="doc_reviwer",
            stages=stages,
            next_node_resolver=_doc_doctor_next_node_resolver,
        ),
    )
