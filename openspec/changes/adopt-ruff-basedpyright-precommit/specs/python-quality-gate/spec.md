## ADDED Requirements

### Requirement: Unified Python Quality Stack
The repository SHALL define a single Python quality stack composed of Ruff, basedpyright, and pre-commit, with no parallel legacy lint/type stacks active.

#### Scenario: Canonical toolchain is declared
- **WHEN** repository quality configuration is inspected
- **THEN** Ruff, basedpyright, and pre-commit are present as the only active Python quality tools
- **AND** no legacy Python lint/format/type tool remains configured for enforcement

### Requirement: Ruff Lint and Format Enforcement
The repository MUST configure Ruff to enforce linting and formatting for all Python sources under `scripts/` and `tests/`.

#### Scenario: Ruff detects violations
- **WHEN** Ruff checks Python files with violations
- **THEN** the quality gate fails until violations are fixed

#### Scenario: Ruff autofix path is available
- **WHEN** developers run the canonical pre-commit stage command (`pre-commit run --all-files --hook-stage pre-commit`)
- **THEN** Ruff lint autofix is executed before formatting to reduce manual remediation

#### Scenario: Ruff stage bindings are deterministic
- **WHEN** pre-commit hook stages are configured
- **THEN** Ruff mutating hooks (lint autofix and formatter write mode) run only in `pre-commit` stage
- **AND** `pre-push` stage runs only non-mutating Ruff checks

### Requirement: Strict Type Checking with basedpyright
The repository MUST enforce basedpyright in strict mode with warnings treated as failures.

#### Scenario: Strict mode is configured explicitly
- **WHEN** `pyproject.toml` is inspected
- **THEN** `tool.basedpyright.typeCheckingMode` is set to `strict`

#### Scenario: Type issues are present
- **WHEN** basedpyright is run on Python sources under `scripts/` and `tests/` using `--warnings`
- **THEN** any reported error or warning causes the quality gate to fail

### Requirement: Single Gate in Local and CI
The repository SHALL use the same pre-commit entrypoint for local checks and CI checks.

#### Scenario: Local and CI parity
- **WHEN** the quality gate is executed locally and in CI
- **THEN** both flows run the same pre-commit hook set and enforcement semantics
- **AND** both flows execute `pre-commit run --all-files --hook-stage pre-commit` and `pre-commit run --all-files --hook-stage pre-push`

#### Scenario: Mandatory hook phases are enforced
- **WHEN** a developer runs `git commit`
- **THEN** `pre-commit` stage hooks execute and block the commit on failure
- **AND** failure semantics match `pre-commit run --all-files --hook-stage pre-commit`

#### Scenario: Push-time phase is enforced
- **WHEN** a developer runs `git push`
- **THEN** `pre-push` stage hooks execute and block the push on failure
- **AND** failure semantics match `pre-commit run --all-files --hook-stage pre-push`

#### Scenario: Gate hooks enforce full-scope execution during git-triggered runs
- **WHEN** gate hooks are triggered by `git commit` or `git push`
- **THEN** hooks evaluate the full configured scope under `scripts/` and `tests/`, not only changed files
- **AND** hook configuration encodes full-scope behavior for gate hooks

#### Scenario: basedpyright stage coverage is explicit
- **WHEN** hook stage bindings are inspected
- **THEN** basedpyright gate hooks are bound to both `pre-commit` and `pre-push`

### Requirement: Deterministic Tool Versions
The repository MUST pin explicit versions for Ruff, basedpyright, and pre-commit.

#### Scenario: Tooling reproducibility
- **WHEN** a developer installs project quality dependencies on a clean environment
- **THEN** the installed quality tool versions match repository-pinned versions

#### Scenario: CI installation source is deterministic
- **WHEN** CI installs quality gate tooling
- **THEN** installation uses repository-pinned dependency definitions
- **AND** CI does not install floating latest versions for quality gate tools

#### Scenario: Version pin conflicts resolve deterministically
- **WHEN** dependency-file pins and pre-commit hook `rev` are inconsistent for the same quality tool
- **THEN** the pre-commit hook `rev` is authoritative for hook execution
- **AND** repository dependency-file pins are updated to the same version in the same change

#### Scenario: Version authority scope is explicit
- **WHEN** a hook is defined with `repo: local`
- **THEN** the hook-`rev` authority rule is not applicable to that hook

### Requirement: Python Runtime Baseline
The repository MUST define Python 3.13 as the runtime baseline for the Python quality gate.

#### Scenario: Runtime baseline is configured consistently
- **WHEN** Python quality configuration and CI workflow are inspected
- **THEN** CI uses Python 3.13 for the quality job
- **AND** `tool.basedpyright.pythonVersion` is set to `3.13`
- **AND** `tool.ruff.target-version` is set to `py313`
- **AND** pre-commit hook runtime is pinned via `default_language_version.python: python3.13`
