import importlib.util
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

SCRIPT_PATH = ROOT / "scripts" / "codex_automation_loops.py"

spec = importlib.util.spec_from_file_location("codex_orchestrator", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def run_workflow_direct(preset_id: str, context_overrides: dict[str, str], launch_cwd: str | None = None) -> dict[str, Any]:
    return cast(dict[str, Any], module.run_workflow.fn(preset_id, context_overrides, launch_cwd))


def make_fake_codex_exec(
    *,
    payload_for_call: Callable[..., Any] | None = None,
    raw_output_for_call: Callable[..., str] | None = None,
    captured_prompts: list[str] | None = None,
) -> Callable[..., str]:
    if (payload_for_call is None) == (raw_output_for_call is None):
        raise ValueError("Provide exactly one of payload_for_call or raw_output_for_call")

    def fake_codex_exec(request: Any) -> str:
        node_id = request.node_id
        step = request.step
        attempt = request.attempt
        prompt = request.prompt
        if captured_prompts is not None:
            captured_prompts.append(prompt)

        kwargs: dict[str, Any] = {
            "node_id": node_id,
            "step": step,
            "attempt": attempt,
            "prompt": prompt,
        }
        if raw_output_for_call is not None:
            out_text = raw_output_for_call(**kwargs)
        else:
            assert payload_for_call is not None
            out_text = json.dumps(payload_for_call(**kwargs), ensure_ascii=False)

        Path(request.out_file).write_text(out_text, encoding="utf-8")
        log_path = Path(request.task_log_dir) / f"fake_{step}_{attempt}.log"
        log_path.write_text("ok", encoding="utf-8")
        return str(log_path)

    return cast(Callable[..., str], fake_codex_exec)


def patch_native_exec(side_effect: Callable[..., str]):
    import importlib
    from unittest.mock import patch

    native_runtime = importlib.import_module("_codex_orchestrator.native_workflows.runtime")
    return patch.object(native_runtime, "run_codex_exec", side_effect=side_effect)
