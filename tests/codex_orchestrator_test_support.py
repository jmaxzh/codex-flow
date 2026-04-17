import importlib.util
import json
import types
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "codex_automation_loops.py"
TEST_CONFIG_RELATIVE_PATH = Path("presets") / "test_preset.yaml"


spec = importlib.util.spec_from_file_location("codex_orchestrator", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write_json_config(config_path: Path, payload: dict[str, Any]) -> Path:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    return config_path


class PatchedYamlMixin:
    def patch_yaml(self):
        return patch.multiple(
            module,
            YAML_IMPORT_ERROR=None,
            yaml=types.SimpleNamespace(safe_load=json.loads),
        )


class WorkflowTestFactoryMixin:
    def _normalize_run_args(self, run_args: dict[str, Any] | None, kwargs: dict[str, Any]) -> dict[str, Any]:
        if run_args is not None:
            normalized = {
                "project_root": run_args["project_root"],
                "max_steps": run_args["max_steps"],
                "state_dir": run_args.get("state_dir", ".codex-loop-state"),
                "executor_cmd": run_args.get("executor_cmd"),
            }
        else:
            normalized = {
                "project_root": kwargs.pop("project_root"),
                "max_steps": kwargs.pop("max_steps"),
                "state_dir": kwargs.pop("state_dir", ".codex-loop-state"),
                "executor_cmd": kwargs.pop("executor_cmd", None),
            }
        if kwargs:
            unknown = ", ".join(sorted(kwargs))
            raise TypeError(f"Unexpected workflow args: {unknown}")
        return normalized

    def build_workflow_payload(
        self,
        *,
        defaults: dict[str, object],
        start: str,
        nodes: list[dict[str, object]],
        run_args: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        normalized = self._normalize_run_args(run_args, kwargs)
        return {
            "version": 1,
            "run": {
                "project_root": str(normalized["project_root"]),
                "state_dir": normalized["state_dir"],
                "max_steps": normalized["max_steps"],
            },
            "executor": {"cmd": normalized["executor_cmd"] or ["codex", "exec", "--skip-git-repo-check"]},
            "context": {"defaults": defaults},
            "workflow": {"start": start, "nodes": nodes},
        }

    def write_workflow_config(self, base_dir: Path, **kwargs: Any) -> Path:
        payload = self.build_workflow_payload(**kwargs)
        return write_json_config(base_dir / TEST_CONFIG_RELATIVE_PATH, payload)

    def write_workflow_config_at(self, config_path: Path, **kwargs: Any) -> Path:
        payload = self.build_workflow_payload(**kwargs)
        return write_json_config(config_path, payload)

    def make_fake_codex_exec(
        self,
        payload_for_call: Callable[..., Any] | None = None,
        *,
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
            kwargs: dict[str, Any] = {"node_id": node_id, "step": step, "attempt": attempt, "prompt": prompt}
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
