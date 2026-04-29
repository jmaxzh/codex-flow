from __future__ import annotations

from typing import Any, NamedTuple


class RuntimeMarkerResolverConfig(NamedTuple):
    resolver_name: str
    expected_node_id: str
    marker_key: str
    end_node: str


def resolve_runtime_marker_next_node(
    cfg: RuntimeMarkerResolverConfig,
    *,
    node: dict[str, Any],
    pass_flag: bool,
    default_next_node: str,
    runtime_state: dict[str, Any],
    node_ids: set[str],
) -> str:
    if node["id"] != cfg.expected_node_id or not pass_flag:
        return default_next_node
    marker = runtime_state["context"]["runtime"].get(cfg.marker_key)
    if marker is None:
        return default_next_node
    if not isinstance(marker, str) or not marker.strip():
        raise RuntimeError(f"{cfg.resolver_name} runtime marker context.runtime.{cfg.marker_key} must be non-empty string")
    if marker != cfg.end_node and marker not in node_ids:
        raise RuntimeError(f"{cfg.resolver_name} runtime marker resolved invalid target: {marker}")
    return marker
