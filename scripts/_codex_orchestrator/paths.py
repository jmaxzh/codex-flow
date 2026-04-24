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


def validate_preset_identifier(preset_value: str) -> str:
    preset_id = preset_value.strip()
    if not preset_id:
        raise RuntimeError("--preset requires a non-empty preset identifier")
    if "/" in preset_id or "\\" in preset_id:
        raise RuntimeError(
            "--preset expects a preset identifier (for example: openspec_implement), not a path. "
            "If you used a preset file path before, move or reference that preset under repository "
            "presets/ and pass only its identifier."
        )
    if preset_id.lower().endswith(PRESET_FILE_SUFFIX):
        migration_target = preset_id[: -len(PRESET_FILE_SUFFIX)] or "<preset-id>"
        raise RuntimeError(
            f"--preset accepts extensionless preset identifiers. Use '{migration_target}' instead of '{preset_id}'."
        )
    return preset_id
