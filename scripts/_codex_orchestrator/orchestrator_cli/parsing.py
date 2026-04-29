from __future__ import annotations

import argparse


def parse_context_overrides(pairs: list[list[str]] | None) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for raw_key, raw_value in pairs or []:
        key = raw_key.strip()
        if not key:
            raise RuntimeError("context key cannot be empty")
        if "." in key:
            raise RuntimeError(f"context key '{key}' cannot contain '.'")
        overrides[key] = raw_value
    return overrides


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run codex workflow orchestrator from built-in preset")
    parser.add_argument(
        "--preset",
        required=True,
        help="Built-in preset identifier, e.g. openspec_implement",
    )
    parser.add_argument(
        "--context",
        action="append",
        nargs=2,
        metavar=("KEY", "VALUE"),
        help="Override context.defaults key/value. Repeatable. KEY cannot contain '.'",
    )
    return parser.parse_args()
