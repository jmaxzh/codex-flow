from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

from .naming import make_codex_log_path


class CodexExecRequest(NamedTuple):
    project_root: str
    executor_cmd: list[str]
    prompt: str
    out_file: str
    task_log_dir: str
    node_id: str
    step: int
    attempt: int


def run_codex_exec(request: CodexExecRequest) -> str:
    project_root_path = Path(request.project_root)
    out_path = Path(request.out_file)
    log_path = make_codex_log_path(
        Path(request.task_log_dir),
        request.node_id,
        request.step,
        request.attempt,
    )
    process = subprocess.Popen(
        request.executor_cmd + ["--cd", str(project_root_path), "--output-last-message", str(out_path), "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=project_root_path,
    )

    assert process.stdin is not None
    assert process.stdout is not None

    with log_path.open("wb") as log_file:
        process.stdin.write(request.prompt.encode("utf-8"))
        process.stdin.close()

        while True:
            chunk = process.stdout.read(8192)
            if not chunk:
                break
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
            log_file.write(chunk)
            log_file.flush()

    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"codex failed: exit={return_code}, log={log_path}")
    if not out_path.is_file():
        raise RuntimeError(f"codex output file missing: {out_path}, log={log_path}")
    return str(log_path)
