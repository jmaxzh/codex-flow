from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from _codex_orchestrator.fileio import write_json, write_text
from _codex_orchestrator.naming import make_run_id

END_NODE = "END"


def prepare_run_workspace(run_cfg: dict[str, Any]) -> dict[str, Any]:
    project_root = Path(run_cfg["project_root"])
    state_dir = Path(run_cfg["state_dir"])
    state_dir.mkdir(parents=True, exist_ok=True)
    run_id = make_run_id()
    run_state_dir = state_dir / "runs" / run_id
    run_state_dir.mkdir(parents=True, exist_ok=True)
    run_log_dir = run_state_dir / "logs" / f"workflow__{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_log_dir.mkdir(parents=True, exist_ok=True)
    return {
        "project_root": project_root,
        "state_dir": state_dir,
        "run_id": run_id,
        "run_state_dir": run_state_dir,
        "run_log_dir": run_log_dir,
    }


def finalize_run_outputs(
    *,
    run_id: str,
    run_state_dir: Path,
    state_dir: Path,
    final_node: str,
    steps_executed: int,
    outputs: dict[str, Any],
) -> dict[str, Any]:
    final_summary = {
        "status": "completed",
        "run_id": run_id,
        "run_state_dir": str(run_state_dir),
        "final_node": final_node,
        "steps_executed": steps_executed,
        "outputs": outputs,
    }
    write_json(run_state_dir / "run_summary.json", final_summary)
    write_json(state_dir / "latest_run.json", {"run_id": run_id, "run_state_dir": str(run_state_dir)})
    write_text(state_dir / "latest_run_id", f"{run_id}\n")
    return final_summary
