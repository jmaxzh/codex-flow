## Context

This repository includes Python automation logic and tests but lacks a unified quality gate. Without a single lint/format/type baseline, developers receive feedback late and code style drifts across files.

The chosen stack is Ruff + basedpyright + pre-commit, applied as a hard cutover with no compatibility layer. The implementation must make local checks and CI checks identical.

## Goals / Non-Goals

**Goals:**
- Establish one authoritative quality configuration for Python code in `pyproject.toml`.
- Enforce Ruff linting/formatting and basedpyright strict typing in both local and CI flows.
- Fail fast on warnings and errors to guarantee deterministic quality outcomes.
- Remove redundant legacy tooling and prevent split-brain quality policies.
- Freeze execution baseline to Python 3.13 in CI and tool configuration to keep diagnostics deterministic.

**Non-Goals:**
- Gradual migration using baselines, soft-fail modes, or temporary ignores for backward compatibility.
- Supporting multiple concurrent Python quality stacks.
- Broad refactoring beyond what is needed to satisfy the new quality gate.

## Decisions

1. Use Ruff as unified linter + formatter.
- Rationale: Ruff replaces fragmented lint/format tools with one fast engine and one config surface.
- Alternative considered: keep Black/isort/flake8 + add Ruff incrementally.
- Rejected because this preserves duplicate policy surfaces and contradicts one-shot migration.

2. Use basedpyright as the only type checker with strict mode and warning-fail execution.
- Rationale: strict semantics with deterministic CI behavior match the one-shot quality goal.
- Alternative considered: mypy or pyright compatibility mode.
- Rejected because this change prioritizes strictness and immediate enforcement over compatibility.

3. Use pre-commit as the mandatory local gate and run the same gate in CI.
- Rationale: same command path minimizes “works locally but fails in CI” divergence.
- Alternative considered: CI-only enforcement.
- Rejected due to slower feedback and higher rework cost.

4. Define explicit gate phases and canonical stage commands.
- Decision: install both `pre-commit` and `pre-push` hooks locally. `git commit` maps to `pre-commit` semantics and `git push` maps to `pre-push` semantics. Canonical verification commands are `pre-commit run --all-files --hook-stage pre-commit` and `pre-commit run --all-files --hook-stage pre-push`, and both must pass locally and in CI.
- Rationale: this closes ambiguity around trigger semantics and ensures uniform enforcement behavior per stage.
- Alternative considered: `pre-commit` only.
- Rejected because it leaves push-time enforcement undefined.

5. Adopt explicit pinned versions for core quality tools with a conflict rule.
- Rationale: prevents behavior drift from upstream auto-upgrades and makes failures reproducible.
- Alternative considered: floating version ranges.
- Rejected because reproducibility is required for strict gating.
- Conflict rule: pre-commit hook `rev` is authoritative for hook-executed tools from external hook repositories; dependency-file pins MUST be aligned to the same version in the same change to avoid drift. For `repo: local` hooks, this `rev` authority rule does not apply.

6. Scope quality checks to repository-owned Python sources under `scripts/` and `tests/`.
- Decision: Ruff and basedpyright enforcement scope is explicitly anchored to `scripts/` and `tests/` in tool and hook configuration.
- Rationale: these are the project-owned Python directories in this repository and match the implementation surface.
- Alternative considered: broad “repository Python code” or “full-project gate” wording without explicit path anchors.
- Rejected because it introduces interpretation drift.

7. Define Python runtime baseline in one place and mirror it in execution surfaces.
- Decision: set Python baseline to 3.13, enforce it in CI (`actions/setup-python`), Ruff (`target-version = "py313"`), basedpyright (`pythonVersion = "3.13"`), and pre-commit hook runtime (`default_language_version.python = python3.13`).
- Rationale: same tool versions can emit different diagnostics by Python version; one baseline is required for reproducibility.
- Alternative considered: relying on runner default Python or multi-version matrix.
- Rejected because this change requires deterministic single-path gating.

8. Encode warning-fail semantics as executable basedpyright invocation.
- Decision: run basedpyright with `--warnings` in pre-commit hooks and CI gate stage commands.
- Rationale: goal statements alone are not sufficient; the failing behavior must be guaranteed by command-level enforcement.
- Alternative considered: relying only on strict mode defaults.
- Rejected because strict mode does not, by itself, define warning-as-failure behavior.

9. Bind hook stages explicitly by behavior and keep both stages full-scope.
- Decision: bind basedpyright gate hooks to both `pre-commit` and `pre-push`; bind Ruff mutating hooks (autofix/format write) only to `pre-commit`; bind non-mutating validation hooks to `pre-push`; configure gate hooks to run against the full `scripts/` and `tests/` scope during git-triggered stages.
- Rationale: prevents push-time file rewrites, guarantees type-check presence in both phases, and avoids changed-files/full-repo semantic drift.
- Alternative considered: rely on default stages and changed-file execution.
- Rejected because defaults can silently skip required checks in one stage and diverge from CI full-scope behavior.

10. Use repository-pinned install entrypoints in CI for quality tooling.
- Decision: CI installs `pre-commit` and quality tools from repository dependency definitions (lock/pin source), then runs canonical stage commands.
- Rationale: preserves deterministic versions between local and CI gate execution.
- Alternative considered: ad-hoc floating installs in workflow steps.
- Rejected because it can bypass repository pins and introduce non-reproducible diagnostics.

## Risks / Trade-offs

- [Initial migration breakage] Existing code may fail strict lint/type gates immediately. → Mitigation: perform a single remediation pass in the same change before enabling gate in CI.
- [Developer friction increase] Hard gate on commit/push may slow early iterations. → Mitigation: keep hooks fast, run Ruff auto-fix first in `pre-commit`, and document canonical stage commands.
- [Dependency compatibility drift] Future tool releases may change diagnostics. → Mitigation: pin versions and upgrade intentionally via dedicated maintenance changes.
- [False positives in strict typing] Strict inference may flag legitimate dynamic patterns. → Mitigation: require explicit typing patterns or narrow, justified inline suppressions.
