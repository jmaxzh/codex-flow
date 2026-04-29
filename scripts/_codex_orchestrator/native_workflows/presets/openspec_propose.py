from __future__ import annotations

from typing import Any

from _codex_orchestrator.native_workflows.constants import END_NODE
from _codex_orchestrator.native_workflows.preset_common.next_node_resolvers import (
    RuntimeMarkerResolverConfig,
    resolve_runtime_marker_next_node,
)
from _codex_orchestrator.native_workflows.stage_schema import StageSpec

OPENSPEC_PROPOSE_NEXT_NODE_RESOLVER_CONFIG = RuntimeMarkerResolverConfig(
    resolver_name="openspec_propose",
    expected_node_id="openspec_propose_review",
    marker_key="doc_review_next_node",
    end_node=END_NODE,
)


def openspec_propose_next_node_resolver(
    node: dict[str, Any],
    pass_flag: bool,
    default_next_node: str,
    runtime_state: dict[str, Any],
    node_ids: set[str],
) -> str:
    return resolve_runtime_marker_next_node(
        OPENSPEC_PROPOSE_NEXT_NODE_RESOLVER_CONFIG,
        node=node,
        pass_flag=pass_flag,
        default_next_node=default_next_node,
        runtime_state=runtime_state,
        node_ids=node_ids,
    )


def openspec_propose_stages() -> dict[str, StageSpec]:
    return {
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
