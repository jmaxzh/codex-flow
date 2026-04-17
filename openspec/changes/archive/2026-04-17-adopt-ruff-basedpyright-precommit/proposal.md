## Why

The repository currently has Python code but no unified linting, formatting, type-checking, or commit-time quality gates. This causes inconsistent code quality and late feedback in CI, so we need a single modern toolchain adopted in one move.

This follow-up tightens maintainability constraints: the gate must prohibit global/file-level lint/type ignore shortcuts, enforce function complexity thresholds, and introduce a script-file size control to prevent monolithic automation files from regrowing.

## What Changes

- Add a single Python quality stack based on Ruff, basedpyright, and pre-commit.
- Define one canonical configuration source in `pyproject.toml` for lint/format/type rules.
- Set Python runtime baseline to 3.13 across local, hooks, and CI (`actions/setup-python`, `tool.basedpyright.pythonVersion`, and `tool.ruff.target-version`).
- Enforce strict basedpyright checking with warnings treated as failures by running basedpyright with `--warnings` in hooks and CI.
- Enforce git hook-time blocking at `pre-commit` and `pre-push` using one canonical gate entrypoint (`pre-commit run --all-files`) with explicit hook stages and identical pass/fail semantics in local and CI.
- Enforce Ruff complexity/size-style constraints: McCabe complexity (`C901`) and Pylint-compatible thresholds for branches/returns/args/statements.
- Introduce a repository-local script-size gate for `scripts/*.py` to keep orchestrator modules split and maintainable.
- Prohibit ignore-based bypasses in gate configuration: no Ruff `per-file-ignores`/global ignore lists for managed paths, no inline `noqa`/`type: ignore` suppressions in `scripts/` and `tests/` unless explicitly allowed by a future dedicated change.
- Remove legacy/overlapping Python quality tools and their configurations from repository workflows. **BREAKING**

## Capabilities

### New Capabilities
- `python-quality-gate`: Define and enforce a unified Python lint/format/type gate across local development and CI.

### Modified Capabilities
- None.

## Impact

- Affected code: Python sources under `scripts/` and `tests/`, plus repository-level tooling config.
- Affected workflows: developer commit/push flow and CI validation pipeline, with both `pre-commit` and `pre-push` stage semantics enforced in each environment.
- New dependencies: `ruff`, `basedpyright`, and `pre-commit` (version-pinned).
- Removed dependencies/configuration: legacy Python lint/format/type tooling where present.
- Version authority: runtime and rule baselines come from `pyproject.toml`; if dependency-file pins and pre-commit hook `rev` differ, hook `rev` is authoritative for hook execution and dependency pins are updated to match in the same change.
