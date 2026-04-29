# orchestrator-module-boundaries

## Why
The orchestrator previously had many sibling modules with similar prefixes (for example `runtime_*`, `prompt_*`, `executor_*`), which increased navigation cost and made intent less obvious during maintenance.

## Package Boundaries
- `scripts/_codex_orchestrator/runtime/`
  - Owns runtime state creation, history collection, route bindings, artifact planning/persistence, and workspace lifecycle.
  - New runtime submodules should be added under this package instead of creating new `runtime_*` files at package root.
- `scripts/_codex_orchestrator/prompt/`
  - Owns prompt helper construction, prompt value shaping, and final rendering.
  - New prompt-related logic should live here instead of adding new `prompt_*` files at package root.
- `scripts/_codex_orchestrator/execution/`
  - Owns codex execution request types, command planning, and streaming IO behavior.
  - New execution-related logic should live here instead of adding new `executor_*` files at package root.

## Root-Level Modules
Keep package-root files for cross-domain orchestration only (for example `executor.py`, `orchestrator_cli.py`, `routing.py`, `paths.py`).
Avoid adding new root-level files that represent a domain slice already owned by `runtime/`, `prompt/`, or `execution/`.

## Entrypoint Layer
- `scripts/codex_automation_loops.py` is a strict CLI entrypoint and should not re-export orchestration internals.
- Native workflow task/flow wrappers should live in `scripts/_codex_orchestrator/native_workflows/entrypoints.py`.
- When adding new orchestration behavior, prefer extending `native_workflows/entrypoints.py` and keep `codex_automation_loops.py` focused on CLI wiring only.

## Naming Rules
- Prefer domain package modules:
  - `runtime/<noun>.py`
  - `prompt/<noun>.py`
  - `execution/<noun>.py`
- Avoid proliferating similarly prefixed root files such as:
  - `runtime_<noun>.py`
  - `prompt_<noun>.py`
  - `executor_<noun>.py`

## Compatibility Strategy
- Compatibility shims are removed. Do not add backward-compatible re-export modules or fallback execution paths.
- Imports should target `_codex_orchestrator.prompt`, `_codex_orchestrator.runtime`, and other package APIs directly.
- Missing dependencies are treated as hard failures at import/runtime boundaries; no optional fallback path is supported.
