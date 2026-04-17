from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


def sanitize_node_id(node_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", node_id)


def build_step_prefix(step: int, node_id: str, attempt: int) -> str:
    return f"step{step:03d}__{sanitize_node_id(node_id)}__attempt{attempt:02d}"


def make_run_id() -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    return f"run__{ts}"


def make_codex_log_path(task_log_dir: Path, node_id: str, step: int, attempt: int) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    prefix = build_step_prefix(step, node_id, attempt)
    return task_log_dir / f"{prefix}__{ts}.log"
