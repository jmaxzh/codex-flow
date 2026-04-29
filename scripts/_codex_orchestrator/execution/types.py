from __future__ import annotations

from typing import NamedTuple


class CodexExecRequest(NamedTuple):
    project_root: str
    executor_cmd: list[str]
    prompt: str
    out_file: str
    task_log_dir: str
    node_id: str
    step: int
    attempt: int
