import tempfile
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Protocol, overload

from tests.codex_orchestrator_fake_exec import make_fake_codex_exec
from tests.codex_orchestrator_module_loader import ROOT, module, run_workflow_direct
from tests.codex_orchestrator_runtime_patch import patch_native_exec


class RuntimeWorkflowRunner(Protocol):
    @overload
    def __call__(self, preset_id: str) -> dict[str, Any]: ...

    @overload
    def __call__(self, preset_id: str, context_overrides: dict[str, str] | None) -> dict[str, Any]: ...

    @overload
    def __call__(
        self,
        preset_id: str,
        context_overrides: dict[str, str] | None,
        launch_cwd: Path | str | None,
    ) -> dict[str, Any]: ...


@contextmanager
def runtime_harness(
    *,
    payload_for_call: Callable[..., Any] | None = None,
    raw_output_for_call: Callable[..., str] | None = None,
    captured_prompts: list[str] | None = None,
) -> Generator[tuple[Path, RuntimeWorkflowRunner]]:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        fake_exec = make_fake_codex_exec(
            payload_for_call=payload_for_call,
            raw_output_for_call=raw_output_for_call,
            captured_prompts=captured_prompts,
        )

        with patch_native_exec(fake_exec):

            def run(
                preset_id: str,
                context_overrides: dict[str, str] | None = None,
                launch_cwd: Path | str | None = None,
            ) -> dict[str, Any]:
                resolved_cwd = str(launch_cwd or tmp_path)
                return run_workflow_direct(preset_id, context_overrides or {}, resolved_cwd)

            yield tmp_path, run


__all__ = [
    "ROOT",
    "make_fake_codex_exec",
    "module",
    "patch_native_exec",
    "runtime_harness",
]
