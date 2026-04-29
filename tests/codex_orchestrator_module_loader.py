import importlib
import types
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
_loaded_module: types.ModuleType | None = None
_loaded_cli_module: types.ModuleType | None = None


def get_module() -> types.ModuleType:
    global _loaded_module
    if _loaded_module is None:
        _loaded_module = importlib.import_module("_codex_orchestrator.native_workflows.api")
    return _loaded_module


def get_cli_module() -> types.ModuleType:
    global _loaded_cli_module
    if _loaded_cli_module is None:
        _loaded_cli_module = importlib.import_module("_codex_orchestrator.orchestrator_cli")
    return _loaded_cli_module


class _ModuleProxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(get_module(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(get_module(), name, value)

    def __delattr__(self, name: str) -> None:
        delattr(get_module(), name)


module = _ModuleProxy()


def run_workflow_direct(preset_id: str, context_overrides: dict[str, str], launch_cwd: str | None = None) -> dict[str, Any]:
    cli_module = get_cli_module()
    split_context = cli_module.split_context_overrides_and_max_steps_override
    run_with_options = cli_module.run_workflow_with_options
    context_data, max_steps_override = split_context(context_overrides)
    return run_with_options(
        preset_id=preset_id,
        context_overrides=context_data,
        launch_cwd=launch_cwd,
        max_steps_override=max_steps_override,
    )
