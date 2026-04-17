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
    def build_workflow_payload(
        self,
        *,
        project_root: Path | str,
        max_steps: int,
        defaults: dict[str, object],
        start: str,
        nodes: list[dict[str, object]],
        state_dir: str = ".codex-loop-state",
        executor_cmd: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "version": 1,
            "run": {
                "project_root": str(project_root),
                "state_dir": state_dir,
                "max_steps": max_steps,
            },
            "executor": {"cmd": executor_cmd or ["codex", "exec", "--skip-git-repo-check"]},
            "context": {"defaults": defaults},
            "workflow": {"start": start, "nodes": nodes},
        }

    def write_workflow_config(
        self,
        base_dir: Path,
        *,
        project_root: Path,
        max_steps: int,
        defaults: dict[str, object],
        start: str,
        nodes: list[dict[str, object]],
        state_dir: str = ".codex-loop-state",
        executor_cmd: list[str] | None = None,
    ) -> Path:
        payload = self.build_workflow_payload(
            project_root=project_root,
            max_steps=max_steps,
            defaults=defaults,
            start=start,
            nodes=nodes,
            state_dir=state_dir,
            executor_cmd=executor_cmd,
        )
        return write_json_config(base_dir / TEST_CONFIG_RELATIVE_PATH, payload)

    def write_workflow_config_at(
        self,
        config_path: Path,
        *,
        project_root: Path | str,
        max_steps: int,
        defaults: dict[str, object],
        start: str,
        nodes: list[dict[str, object]],
        state_dir: str = ".codex-loop-state",
        executor_cmd: list[str] | None = None,
    ) -> Path:
        payload = self.build_workflow_payload(
            project_root=project_root,
            max_steps=max_steps,
            defaults=defaults,
            start=start,
            nodes=nodes,
            state_dir=state_dir,
            executor_cmd=executor_cmd,
        )
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

        def fake_codex_exec(
            project_root: str,
            executor_cmd: list[str],
            prompt: str,
            out_file: str,
            task_log_dir: str,
            node_id: str,
            step: int,
            attempt: int,
        ) -> str:
            if captured_prompts is not None:
                captured_prompts.append(prompt)
            kwargs: dict[str, Any] = {"node_id": node_id, "step": step, "attempt": attempt, "prompt": prompt}
            if raw_output_for_call is not None:
                out_text = raw_output_for_call(**kwargs)
            else:
                assert payload_for_call is not None
                out_text = json.dumps(payload_for_call(**kwargs), ensure_ascii=False)

            Path(out_file).write_text(out_text, encoding="utf-8")
            log_path = Path(task_log_dir) / f"fake_{step}_{attempt}.log"
            log_path.write_text("ok", encoding="utf-8")
            return str(log_path)

        return cast(Callable[..., str], fake_codex_exec)
