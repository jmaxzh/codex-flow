import importlib
from collections.abc import Callable
from unittest.mock import patch


def patch_native_exec(side_effect: Callable[..., str]):
    native_io = importlib.import_module("_codex_orchestrator.native_workflows.runtime_io")
    return patch.object(native_io, "run_codex_exec", side_effect=side_effect)
