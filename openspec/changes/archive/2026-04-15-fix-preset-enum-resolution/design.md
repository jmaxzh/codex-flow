## Context

The orchestrator CLI documents `--preset` as a preset selector (examples use `implement_loop`, `refactor_loop`, `reviewer_loop`). Current implementation accepts both names and file paths, and resolves relative values against `Path.cwd()`. This causes environment-dependent failures when running the script outside the repository root.

The desired behavior is product-level determinism: `--preset` should map to built-in presets shipped by this project, independent of caller location.

## Goals / Non-Goals

**Goals:**
- Make preset resolution deterministic across directories.
- Enforce identifier-only semantics for `--preset`.
- Provide clear validation and discoverability for supported preset names.
- Align implementation, tests, and docs to one contract.

**Non-Goals:**
- Supporting arbitrary external preset file paths via CLI.
- Introducing new preset loading backends (remote URL, env var, plugin lookup).
- Changing workflow schema, execution engine, or runtime state semantics.

## Decisions

1. Resolve `--preset` against repository `presets/` directory, not `cwd`.
- Decision: derive a stable base directory from script location (`Path(__file__).resolve().parent.parent`) and load `<repo_root>/presets/<name>.yaml`.
- Why: repository-local path is invariant to invocation directory.
- Alternative considered: continue supporting path-like values. Rejected because it preserves ambiguous semantics and cwd sensitivity.

2. Treat `--preset` as identifier-only input.
- Decision: accept only extensionless preset identifiers (file stem), reject values containing path separators (`/`, `\\`), reject empty/whitespace-only identifiers, and reject `.yaml`-suffixed values like `implement_loop.yaml` with a migration hint to use `implement_loop`.
- Why: explicit boundary prevents accidental path-mode behavior and matches user mental model ("preset enum").
- Alternative considered: dual-mode (`name` or `path`) with smarter heuristics. Rejected because heuristics are brittle and keep confusing behavior.

3. Improve unknown preset diagnostics.
- Decision: on missing preset, include normalized lookup path and available preset identifiers discovered in `presets/`.
- Why: reduces triage time and makes valid choices obvious.
- Alternative considered: generic "file not found" only. Rejected due to poor usability.

4. Keep preset file suffix convention.
- Decision: continue auto-appending `.yaml` for bare identifiers.
- Why: backward-compatible with existing CLI examples and scripts.

## Risks / Trade-offs

- [Risk] Existing automation that passed explicit preset file paths will break.
  -> Mitigation: mark as BREAKING in proposal, add explicit validation error with migration hint ("use preset id").

- [Risk] Script relocation could break computed repository root.
  -> Mitigation: derive from current file path relative structure already used by this repo layout; add tests that pin expected resolver behavior.

- [Trade-off] Reduced flexibility for ad-hoc local presets.
  -> Mitigation: encourage adding reusable presets under repository `presets/` or future dedicated option (out of scope here).
