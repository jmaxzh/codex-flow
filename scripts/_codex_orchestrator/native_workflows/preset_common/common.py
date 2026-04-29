from __future__ import annotations

from _codex_orchestrator.native_workflows.stage_schema import StageSpec


def reviewer_loop_stage(*, node_id: str, history_key: str) -> dict[str, StageSpec]:
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
