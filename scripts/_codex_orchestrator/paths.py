from __future__ import annotations

from pathlib import Path

PRESET_FILE_SUFFIX = ".yaml"


def resolve_path(path_value: str | Path, base_dir: Path) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def get_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


__all__ = [
    "PRESET_FILE_SUFFIX",
    "get_repo_root",
    "resolve_path",
]
