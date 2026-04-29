from __future__ import annotations

import argparse
from collections.abc import Callable
from typing import Any

ResolveMainConfigFn = Callable[[str, list[list[str]] | None], tuple[str, dict[str, str]]]
RunWorkflowFn = Callable[[str, dict[str, str], str], dict[str, Any]]
ParseArgsFn = Callable[[], argparse.Namespace]
FailWithStderrFn = Callable[[str], int]
