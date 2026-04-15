## 1. Preset Resolution Contract Update

- [x] 1.1 Refactor `scripts/codex_automation_loops.py` preset resolver to use repository `presets/` as lookup root instead of `Path.cwd()`.
- [x] 1.2 Enforce identifier-only validation for `--preset` and reject path-like values, empty/whitespace-only values, and `.yaml`-suffixed identifiers with clear migration-oriented error messages.
- [x] 1.3 Keep `.yaml` suffix auto-append behavior for bare preset identifiers.
- [x] 1.4 Improve unknown preset errors to include available built-in preset identifiers.

## 2. CLI and Documentation Alignment

- [x] 2.1 Update CLI help text for `--preset` to describe identifier-only semantics.
- [x] 2.2 Update `README.md` parameter documentation and examples to remove `name-or-path` wording.
- [x] 2.3 Add a migration note describing breaking change for users previously passing preset file paths.

## 3. Test Coverage

- [x] 3.1 Update existing tests that assert cwd-relative preset path behavior.
- [x] 3.2 Add tests proving preset resolution is identical across different `cwd` values.
- [x] 3.3 Add tests for `--preset` validation rejections (path-like, empty/whitespace-only, and `.yaml`-suffixed values) and unknown preset diagnostics (including available preset identifiers).
- [x] 3.4 Run `tests/test_codex_orchestrator.py` and confirm all affected cases pass.
