<!--
Sync Impact Report
Version change: N/A (template) -> 1.0.0
Modified principles:
- N/A (initial ratification from template placeholders)
Added sections:
- Engineering Constraints
- Delivery Workflow & Quality Gates
Removed sections:
- None
Templates requiring updates:
- ✅ .specify/templates/plan-template.md
- ✅ .specify/templates/spec-template.md
- ✅ .specify/templates/tasks-template.md
- ⚠ pending .specify/templates/commands/*.md (directory not present in this repository)
Follow-up TODOs:
- None
-->
# Codex Flow Constitution

## Core Principles

### 0. User Requirements
- Chinese Respone.

### I. Spec-First Delivery
Every behavior change MUST start with an explicit spec artifact in `docs/specs/` or
`.specify/specs/` that defines scope, acceptance criteria, and boundaries before
implementation tasks begin. Work that bypasses specification is non-compliant unless
it is an emergency fix with documented post-hoc spec updates in the same branch.
Rationale: this repository coordinates automation behavior and requires traceable intent.

### II. Deterministic Workflow Contracts
Workflow nodes, preset routing, prompt rendering, and output contracts MUST remain
deterministic and documented. Any change that alters runtime inputs/outputs, control
signals, or orchestration paths MUST include contract updates and compatibility notes.
Rationale: orchestration regressions are costly and usually surface only under chaining.

### III. Quality Gates Are Non-Negotiable
All production changes MUST pass repository quality gates before merge: `ruff check`,
`ruff format`, `basedpyright --warnings`, and `python3 -m pytest -q` (or scoped
equivalents with justification). Hook failures from `scripts/setup_hooks.sh` MUST be
resolved rather than bypassed.
Rationale: strict static and runtime checks are required to keep loops safe to automate.

### IV. Test Evidence for Behavioral Changes
Any behavioral change MUST include automated test evidence in `tests/`, with new tests
added when existing coverage does not prove the updated behavior. Test organization MUST
follow domain case files (`codex_orchestrator_cases_*.py`) and explicit `test_<behavior>`
naming. Rationale: automation refactors without evidence create silent regressions.

### V. Observable and Minimal Runtime Effects
Runtime state and logs MUST remain inspectable in `.codex-loop-state/` and changes to
artifact formats or locations MUST be documented. Modules under `scripts/` MUST stay
focused, small, and typed to preserve maintainability. Rationale: operators need fast
debug paths and minimal cognitive load during incident response.

## Engineering Constraints

- Runtime target MUST remain Python 3.13 unless a constitution amendment approves change.
- Code style MUST follow repository standards: 4-space indentation, LF, double quotes,
  and max line length 130.
- Public behavior contracts in `docs/specs/` are the source of truth and MUST be updated
  with user-visible or contract-level behavior changes.
- Runtime artifacts MUST be written under `.codex-loop-state/` only; ad-hoc output paths
  require explicit justification in spec/plan docs.

## Delivery Workflow & Quality Gates

1. Define or update specification artifacts before implementation.
2. Create an implementation plan that records constitution gate checks.
3. Execute tasks with explicit file paths and traceability to user stories/requirements.
4. Validate with lint, format, type-check, and tests before merge.
5. Update docs/specs whenever workflow behavior, contracts, or operator guidance changes.

Compliance review is REQUIRED in PRs: reviewers MUST verify constitution adherence or
require a documented exception with expiry and owner.

## Governance

This constitution supersedes local workflow habits and informal conventions.

Amendment procedure:
1. Propose changes through a PR that includes rationale, impact analysis, and required
   template updates.
2. Obtain approval from maintainers responsible for orchestration/runtime quality.
3. Apply migration updates in the same change set (templates, docs, and guidance files).

Versioning policy:
- MAJOR: incompatible governance changes or principle removals/redefinitions.
- MINOR: new principle/section or materially expanded mandatory guidance.
- PATCH: clarifications, wording improvements, and non-semantic refinements.

Compliance expectations:
- Every plan MUST contain an explicit Constitution Check section.
- Every tasks file MUST represent required verification work for behavioral changes.
- Every merge-ready change MUST provide evidence that required checks passed.

**Version**: 1.0.0 | **Ratified**: 2026-04-20 | **Last Amended**: 2026-04-20
