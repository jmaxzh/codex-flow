from __future__ import annotations

from typing import Any, cast

from _codex_orchestrator.dotted_paths import parse_dotted_path, resolve_dotted_parts
from _codex_orchestrator.native_workflows.stage_schema import NormalizedStageSpec


def build_prompt_inputs(node: NormalizedStageSpec, runtime_state: dict[str, Any]) -> dict[str, Any]:
    prompt_inputs: dict[str, Any] = {}
    for input_key_raw, source_path_raw in cast(dict[str, Any], node["input_map"]).items():
        input_key = input_key_raw
        source_path = source_path_raw
        source_parts = parse_dotted_path(source_path, f"{node['id']}.input_map.{input_key}")
        prompt_inputs[input_key] = resolve_dotted_parts(runtime_state, source_parts, source_path)
    return prompt_inputs
