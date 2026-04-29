from __future__ import annotations

from typing import Any


def build_runtime_snapshot(
    runtime_state: dict[str, Any],
    attempt_counter: dict[str, int],
    current_node: str,
    step: int,
    max_steps: int,
) -> dict[str, Any]:
    return {
        "current_node": current_node,
        "step": step,
        "max_steps": max_steps,
        "context": runtime_state["context"],
        "outputs": runtime_state["outputs"],
        "attempt_counter": attempt_counter,
    }
