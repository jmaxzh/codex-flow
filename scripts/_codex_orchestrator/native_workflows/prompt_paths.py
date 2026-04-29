from __future__ import annotations

from pathlib import Path

from _codex_orchestrator.paths import get_repo_root


def prompt_base_dir() -> Path:
    repo_root = get_repo_root()
    return repo_root / "presets" / "prompts"
