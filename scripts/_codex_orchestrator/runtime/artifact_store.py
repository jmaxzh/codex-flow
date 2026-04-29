from __future__ import annotations

import json
from typing import Any

from _codex_orchestrator.fileio import write_json, write_text
from _codex_orchestrator.runtime.artifacts import StepArtifactsPlan, write_runtime_snapshot


def persist_step_artifacts(
    *,
    artifacts: StepArtifactsPlan,
    rendered_prompt: str,
    node_output: Any,
    meta_payload: dict[str, Any],
    runtime_snapshot: dict[str, Any] | None = None,
) -> dict[str, str]:
    write_text(artifacts.prompt_path, rendered_prompt)
    write_json(artifacts.parsed_path, node_output)
    write_json(artifacts.meta_path, meta_payload)
    with artifacts.history_path.open("a", encoding="utf-8") as history:
        history.write(json.dumps(meta_payload, ensure_ascii=False) + "\n")
    if runtime_snapshot is not None:
        write_runtime_snapshot(artifacts.history_path.parent, runtime_snapshot)
    return {
        "prompt_path": str(artifacts.prompt_path),
        "parsed_path": str(artifacts.parsed_path),
        "meta_path": str(artifacts.meta_path),
    }
