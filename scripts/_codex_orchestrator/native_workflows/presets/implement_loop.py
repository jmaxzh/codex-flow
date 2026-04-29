from __future__ import annotations

from _codex_orchestrator.native_workflows.stage_schema import StageSpec


def implement_loop_stages() -> dict[str, StageSpec]:
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
            "on_success": "implement_review",
            "on_failure": "END",
        },
        "implement_review": {
            "id": "implement_review",
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
            "on_failure": "implement_continue",
            "route_bindings": {
                "failure": {
                    "context.runtime.latest_check": "outputs.implement_review.control",
                }
            },
        },
        "implement_continue": {
            "id": "implement_continue",
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
            "on_success": "implement_review",
            "on_failure": "END",
            "route_bindings": {
                "success": {
                    "context.runtime.latest_impl": "outputs.implement_continue",
                }
            },
        },
    }
