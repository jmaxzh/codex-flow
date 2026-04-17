from __future__ import annotations

from pathlib import Path

PRESETS_DIR = "presets"
PRESET_FILE_SUFFIX = ".yaml"


def resolve_path(path_value: str | Path, base_dir: Path) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def get_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_builtin_presets_dir() -> Path:
    return get_repo_root() / PRESETS_DIR


def list_builtin_preset_identifiers(presets_dir: Path) -> list[str]:
    if not presets_dir.is_dir():
        return []
    return sorted(entry.stem for entry in presets_dir.iterdir() if entry.is_file() and entry.name.endswith(PRESET_FILE_SUFFIX))


def format_available_presets(preset_ids: list[str]) -> str:
    if not preset_ids:
        return "(none found)"
    return ", ".join(preset_ids)


def validate_preset_identifier(preset_value: str) -> str:
    preset_id = preset_value.strip()
    if not preset_id:
        raise RuntimeError("--preset requires a non-empty preset identifier")
    if "/" in preset_id or "\\" in preset_id:
        raise RuntimeError(
            "--preset expects a preset identifier (for example: implement_loop), not a path. "
            "If you used a preset file path before, move or reference that preset under repository "
            "presets/ and pass only its identifier."
        )
    if preset_id.lower().endswith(PRESET_FILE_SUFFIX):
        migration_target = preset_id[: -len(PRESET_FILE_SUFFIX)] or "<preset-id>"
        raise RuntimeError(
            f"--preset accepts extensionless preset identifiers. Use '{migration_target}' instead of '{preset_id}'."
        )
    return preset_id


def resolve_preset_path(preset_value: str) -> Path:
    preset_id = validate_preset_identifier(preset_value)
    presets_dir = get_builtin_presets_dir()
    preset_path = (presets_dir / f"{preset_id}{PRESET_FILE_SUFFIX}").resolve()
    if not preset_path.is_file():
        available = format_available_presets(list_builtin_preset_identifiers(presets_dir))
        raise RuntimeError(
            f"Unknown preset identifier: '{preset_id}'. Available built-in presets: {available}. Lookup directory: {presets_dir}"
        )
    return preset_path
