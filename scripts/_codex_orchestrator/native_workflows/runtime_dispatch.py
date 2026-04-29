from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from _codex_orchestrator.native_workflows.registry import get_flow_runner


def fail_with_stderr(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def run_workflow(preset_id: str, context_overrides: dict[str, str], launch_cwd: str | None = None) -> dict[str, Any]:
    return run_workflow_with_options(
        preset_id=preset_id,
        context_overrides=context_overrides,
        launch_cwd=launch_cwd,
        max_steps_override=None,
    )


def run_workflow_with_options(
    *,
    preset_id: str,
    context_overrides: dict[str, str],
    launch_cwd: str | None = None,
    max_steps_override: int | None = None,
) -> dict[str, Any]:
    launch_cwd_resolved = str(Path(launch_cwd).resolve()) if launch_cwd else str(Path.cwd().resolve())
    runner = get_flow_runner(preset_id)
    return runner(context_overrides, launch_cwd_resolved, max_steps_override)
