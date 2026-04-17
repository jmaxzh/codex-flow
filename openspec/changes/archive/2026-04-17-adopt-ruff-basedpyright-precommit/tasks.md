## 1. Toolchain Baseline

- [x] 1.1 Add pinned `ruff`, `basedpyright`, and `pre-commit` dependencies to the repository Python dependency management files.
- [x] 1.2 Create or update `pyproject.toml` with canonical `[tool.ruff]`, `[tool.ruff.lint]`, `[tool.ruff.format]`, and `[tool.basedpyright]` sections, including `target-version = "py313"`, `pythonVersion = "3.13"`, and `typeCheckingMode = "strict"`.
- [x] 1.3 Remove legacy Python lint/format/type configurations and related CI invocations.
- [x] 1.4 Set CI Python runtime for the quality gate job to 3.13 (`actions/setup-python`).
- [x] 1.5 Ensure CI installs quality tooling from repository-pinned dependency definitions (no floating latest install path).

## 2. Pre-commit and CI Gate

- [x] 2.1 Create `.pre-commit-config.yaml` with `default_language_version.python: python3.13`; bind Ruff mutating hooks (lint autofix, formatter write mode) to `pre-commit`; bind non-mutating Ruff checks to `pre-push`; scope to `scripts/` and `tests/`.
- [x] 2.2 Add a basedpyright hook configuration scoped to `scripts/` and `tests/`, bound to both `pre-commit` and `pre-push`, executed with `--warnings` so warnings/errors both fail.
- [x] 2.3 Add a repository bootstrap/setup step (documented command or script) that installs both `pre-commit` and `pre-push` hooks, and provide a verification step.
- [x] 2.4 Verify both stages succeed on a clean working tree: `pre-commit run --all-files --hook-stage pre-commit` and `pre-commit run --all-files --hook-stage pre-push`.
- [x] 2.5 Update CI pipeline to run both canonical stage commands as the Python quality gate: `pre-commit run --all-files --hook-stage pre-commit` and `pre-commit run --all-files --hook-stage pre-push`.
- [x] 2.6 Configure gate hooks to enforce full-scope checks for `scripts/` and `tests/` during git-triggered `pre-commit` and `pre-push` runs (not changed-files-only semantics).

## 3. One-shot Remediation

- [x] 3.1 Run Ruff autofix and formatting across Python files in `scripts/` and `tests/`, then commit resulting code normalization changes.
- [x] 3.2 Fix all basedpyright strict type diagnostics in `scripts/` and `tests/` without introducing baseline files.
- [x] 3.3 Re-run the full gate for both stages (`pre-commit run --all-files --hook-stage pre-commit` and `pre-commit run --all-files --hook-stage pre-push`) and capture green output for change verification.

## 4. Team Rollout

- [x] 4.1 Update repository documentation with required local setup and canonical quality gate commands for both stages: `pre-commit run --all-files --hook-stage pre-commit` and `pre-commit run --all-files --hook-stage pre-push`.
- [x] 4.2 Document the no-compatibility policy: legacy tool usage is unsupported after this change.
- [x] 4.3 Document version authority rule: pre-commit hook `rev` is authoritative for external hook repos and dependency-file pins must match it; clarify non-applicability to `repo: local` hooks.
- [x] 4.4 Add a lightweight validation step/checklist ensuring hook `rev` and dependency pins stay aligned whenever hook revisions change.

## 5. Maintainability Hardening (No-Ignore + Complexity + File Size)

- [x] 5.1 Remove Ruff ignore exemptions from managed scope (`scripts/`, `tests/`) and eliminate code patterns that required them.
- [x] 5.2 Enforce Ruff maintainability thresholds in `pyproject.toml`: `C901 <= 10`, `max-statements = 50`, `max-branches = 10`, `max-returns = 6`, `max-args = 6`.
- [x] 5.3 Add a repository-local gate hook that fails when any `scripts/*.py` exceeds 500 lines, and bind it to both `pre-commit` and `pre-push`.
- [x] 5.4 Add a repository-local gate hook that fails on inline suppressions (`# noqa`, `# type: ignore`) in `scripts/` and `tests/`, and bind it to both `pre-commit` and `pre-push`.
- [x] 5.5 Run full gate verification (`pre-commit` + `pre-push`, Ruff, basedpyright, targeted tests) and mark hardening complete.
