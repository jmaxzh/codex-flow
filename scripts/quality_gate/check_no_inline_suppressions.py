#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANAGED_DIRS = (REPO_ROOT / "scripts", REPO_ROOT / "tests")
PATTERNS = (
    re.compile(r"#\s*noqa\b", re.IGNORECASE),
    re.compile(r"#\s*type:\s*ignore\b", re.IGNORECASE),
)


def iter_python_files() -> list[Path]:
    files: list[Path] = []
    for base_dir in MANAGED_DIRS:
        files.extend(sorted(base_dir.rglob("*.py")))
    return files


def main() -> int:
    violations: list[tuple[Path, int, str]] = []

    for file_path in iter_python_files():
        with file_path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                for pattern in PATTERNS:
                    if pattern.search(line):
                        violations.append((file_path.relative_to(REPO_ROOT), line_no, line.rstrip()))
                        break

    if not violations:
        return 0

    print("Inline suppressions are disallowed in scripts/ and tests/:")
    for rel_path, line_no, content in violations:
        print(f"- {rel_path}:{line_no}: {content}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
