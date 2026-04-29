from __future__ import annotations

from pathlib import Path

from _codex_orchestrator.orchestrator_cli.types import FailWithStderrFn, ParseArgsFn, ResolveMainConfigFn, RunWorkflowFn


def run_cli_main(
    *,
    parse_args_func: ParseArgsFn,
    resolve_main_config_func: ResolveMainConfigFn,
    run_workflow_func: RunWorkflowFn,
    fail_with_stderr_func: FailWithStderrFn,
) -> int:
    args = parse_args_func()

    try:
        preset_id, context_overrides = resolve_main_config_func(args.preset, args.context)
    except Exception as exc:
        return fail_with_stderr_func(str(exc))

    try:
        launch_cwd = str(Path.cwd().resolve())
        summary = run_workflow_func(preset_id, context_overrides, launch_cwd)
        print(f"[logs] task log dir: {summary['run_state_dir']}/logs", flush=True)
    except Exception as exc:
        return fail_with_stderr_func(str(exc))
    return 0
