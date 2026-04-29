from __future__ import annotations

from _codex_orchestrator.paths import PRESET_FILE_SUFFIX


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
