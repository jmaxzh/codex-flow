from __future__ import annotations

from typing import Any

from _codex_orchestrator.native_workflows.constants import END_NODE
from _codex_orchestrator.native_workflows.preset_common.next_node_resolvers import (
    RuntimeMarkerResolverConfig,
    resolve_runtime_marker_next_node,
)
from _codex_orchestrator.native_workflows.stage_schema import StageSpec

DOC_REVISE_NEXT_NODE_RESOLVER_CONFIG = RuntimeMarkerResolverConfig(
    resolver_name="doc_revise",
    expected_node_id="doc_review",
    marker_key="doc_review_next_node",
    end_node=END_NODE,
)


def doc_revise_next_node_resolver(
    node: dict[str, Any],
    pass_flag: bool,
    default_next_node: str,
    runtime_state: dict[str, Any],
    node_ids: set[str],
) -> str:
    return resolve_runtime_marker_next_node(
        DOC_REVISE_NEXT_NODE_RESOLVER_CONFIG,
        node=node,
        pass_flag=pass_flag,
        default_next_node=default_next_node,
        runtime_state=runtime_state,
        node_ids=node_ids,
    )


def doc_revise_stages() -> dict[str, StageSpec]:
    return {
        "doc_review": {
            "id": "doc_review",
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
            "on_failure": "doc_review",
            "route_bindings": {
                "failure": {
                    "context.runtime.doc_review_next_node": "context.defaults.doc_review_fix_node",
                }
            },
        },
        "doc_revise": {
            "id": "doc_revise",
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
            "on_success": "doc_review",
            "on_failure": "END",
            "route_bindings": {
                "success": {
                    "context.runtime.doc_review_next_node": "context.defaults.doc_review_end_node",
                }
            },
        },
    }
