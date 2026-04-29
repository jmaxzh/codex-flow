from __future__ import annotations

from typing import Any

from prefect import flow

from _codex_orchestrator.native_workflows.context_overrides import (
    split_context_overrides_and_max_steps_override as _split_context_and_max_steps_override_impl,
)
from _codex_orchestrator.native_workflows.runtime_dispatch import run_workflow_with_options as _run_workflow_with_options_impl


@flow(name="codex_orchestrator")
def run_workflow(
    preset_id: str,
    context_overrides: dict[str, str],
    launch_cwd: str | None = None,
) -> dict[str, Any]:
    context_data, max_steps_override = _split_context_and_max_steps_override_impl(context_overrides)
    return _run_workflow_with_options_impl(
        preset_id=preset_id,
        context_overrides=context_data,
        launch_cwd=launch_cwd,
        max_steps_override=max_steps_override,
    )
