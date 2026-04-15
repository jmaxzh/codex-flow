## Why

`--preset` currently resolves relative paths from the caller's current working directory, so the same command behaves differently across directories. This conflicts with the expected product contract: `--preset` should be a stable preset enum selector, not a path lookup mode.

## What Changes

- Redefine `--preset` as a preset identifier (enum-like name), not a `name-or-path` hybrid input.
- Resolve preset identifiers against built-in presets bundled with this project (repository `presets/`), independent of invocation `cwd`.
- Reject path-like `--preset` values (for example values containing `/` or `\\`) with actionable validation errors.
- Improve error output for invalid preset names to include available preset identifiers.
- Update CLI help text, README usage, and tests to reflect identifier-only behavior.
- **BREAKING**: remove support for passing custom preset file paths via `--preset`.

## Capabilities

### New Capabilities
- `preset-enum-resolution`: Define deterministic, cwd-independent preset selection semantics for the orchestrator CLI.

### Modified Capabilities
- None.

## Impact

- Affected code: `scripts/codex_automation_loops.py` (`--preset` parsing/validation, preset resolution).
- Affected docs: `README.md` (`--preset` usage and parameter contract).
- Affected tests: `tests/test_codex_orchestrator.py` (preset resolution and CLI validation expectations).
- Runtime behavior: same preset identifier produces the same config target regardless of where the command is executed.
