#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, "") or __package__ == "scripts":
    SCRIPT_DIR = Path(__file__).resolve().parent
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))

from _codex_orchestrator.orchestrator_cli import fail_with_stderr as _fail_with_stderr
from _codex_orchestrator.orchestrator_cli import parse_args as _parse_args
from _codex_orchestrator.orchestrator_cli import resolve_main_config as _resolve_main_config
from _codex_orchestrator.orchestrator_cli import run_cli_main as _run_cli_main
from _codex_orchestrator.orchestrator_cli import run_workflow as _run_workflow


def main() -> int:
    return _run_cli_main(
        parse_args_func=_parse_args,
        resolve_main_config_func=_resolve_main_config,
        run_workflow_func=_run_workflow,
        fail_with_stderr_func=_fail_with_stderr,
    )


if __name__ == "__main__":
    raise SystemExit(main())
