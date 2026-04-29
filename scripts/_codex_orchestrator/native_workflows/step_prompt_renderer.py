from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from _codex_orchestrator.native_workflows.prompt_inputs import build_prompt_inputs
from _codex_orchestrator.native_workflows.prompt_render_deps import prompt_render_deps
from _codex_orchestrator.native_workflows.stage_schema import NormalizedStageSpec
from _codex_orchestrator.prompt.rendering import render_prompt


def render_step_prompt(
    *,
    node: NormalizedStageSpec,
    runtime_state: dict[str, Any],
    prompt_base_dir: Path,
    read_text_func: Callable[[Path], str],
) -> str:
    prompt_inputs = build_prompt_inputs(node, runtime_state)
    return render_prompt(
        node_prompt=node["prompt"],
        prompt_inputs=prompt_inputs,
        config_path=str(prompt_base_dir / "native_workflow.yaml"),
        node_id=node["id"],
        prompt_field=node["prompt_field"],
        deps=prompt_render_deps(read_text_func=read_text_func),
    )
