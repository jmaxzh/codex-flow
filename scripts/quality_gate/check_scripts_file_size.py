#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

MAX_SCRIPT_LINES = 500
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def count_lines(path: Path) -> int:
    return sum(1 for _ in path.open("r", encoding="utf-8"))


def main() -> int:
    offenders: list[tuple[Path, int]] = []

    for script_path in sorted(SCRIPTS_DIR.glob("*.py")):
        line_count = count_lines(script_path)
        if line_count > MAX_SCRIPT_LINES:
            offenders.append((script_path.relative_to(REPO_ROOT), line_count))

    if not offenders:
        return 0

    print(f"scripts/*.py line-count gate failed (max {MAX_SCRIPT_LINES} lines):")
    for rel_path, line_count in offenders:
        print(f"- {rel_path}: {line_count} lines")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
