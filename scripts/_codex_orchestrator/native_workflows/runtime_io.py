from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from _codex_orchestrator.executor import CodexExecRequest, run_codex_exec
from _codex_orchestrator.fileio import read_text

DEFAULT_EXECUTOR_CMD: list[str] = ["codex", "exec", "--skip-git-repo-check"]


class NativeWorkflowIO(NamedTuple):
    executor_cmd: list[str]
    run_codex_exec_func: Callable[[CodexExecRequest], str]
    read_text_func: Callable[[Path], str]


def default_runtime_io() -> NativeWorkflowIO:
    return NativeWorkflowIO(
        executor_cmd=list(DEFAULT_EXECUTOR_CMD),
        run_codex_exec_func=run_codex_exec,
        read_text_func=read_text,
    )
