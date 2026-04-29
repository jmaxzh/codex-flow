from __future__ import annotations

import subprocess
from pathlib import Path
from typing import BinaryIO

from _codex_orchestrator.execution.io import stream_bytes_to_stdout_and_log
from _codex_orchestrator.execution.plan import build_exec_plan
from _codex_orchestrator.execution.types import CodexExecRequest


def _stream_exec_output(
    *,
    process: subprocess.Popen[bytes],
    prompt: str,
    log_file: BinaryIO,
) -> None:
    assert process.stdin is not None
    assert process.stdout is not None

    process.stdin.write(prompt.encode("utf-8"))
    process.stdin.close()

    while True:
        chunk = process.stdout.read(8192)
        if not chunk:
            break
        stream_bytes_to_stdout_and_log(chunk, log_file=log_file)


def _validate_exec_result(return_code: int, out_path: Path, log_path: Path) -> None:
    if return_code != 0:
        raise RuntimeError(f"codex failed: exit={return_code}, log={log_path}")
    if not out_path.is_file():
        raise RuntimeError(f"codex output file missing: {out_path}, log={log_path}")


def run_codex_exec(request: CodexExecRequest) -> str:
    plan = build_exec_plan(request)
    process = subprocess.Popen(
        plan.cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=plan.project_root_path,
    )

    with plan.log_path.open("wb") as log_file:
        _stream_exec_output(
            process=process,
            prompt=request.prompt,
            log_file=log_file,
        )

    return_code = process.wait()
    _validate_exec_result(return_code, plan.out_path, plan.log_path)
    return str(plan.log_path)
