from __future__ import annotations

from typing import Any


def resolve_next_node(node: dict[str, Any], pass_flag: bool) -> str:
    return node["on_success"] if pass_flag else node["on_failure"]
