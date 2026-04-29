from __future__ import annotations

from _codex_orchestrator.native_workflows.stage_schema import StageSpec


def openspec_implement_stages() -> dict[str, StageSpec]:
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
