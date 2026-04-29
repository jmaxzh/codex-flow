from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from _codex_orchestrator.execution.types import CodexExecRequest
from _codex_orchestrator.naming import make_codex_log_path


class ExecPlan(NamedTuple):
    project_root_path: Path
    out_path: Path
    log_path: Path
    cmd: list[str]


def build_exec_plan(request: CodexExecRequest) -> ExecPlan:
    project_root_path = Path(request.project_root)
    out_path = Path(request.out_file)
    log_path = make_codex_log_path(
        Path(request.task_log_dir),
        request.node_id,
        request.step,
        request.attempt,
    )
    cmd = request.executor_cmd + ["--cd", str(project_root_path), "--output-last-message", str(out_path), "-"]
    return ExecPlan(
        project_root_path=project_root_path,
        out_path=out_path,
        log_path=log_path,
        cmd=cmd,
    )
