# Tasks: OpenSpec Workflow Rename

**Input**: Design documents from `/specs/001-openspec-workflow-rename/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Include automated tests for all behavioral changes in CLI preset resolution, native flow runtime behavior, prompt template loading, and legacy-name migration errors.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare target prompt assets and shared test scaffolding before behavior changes.

- [X] T001 Create prompt asset files `presets/prompts/openspec_implement_implement_first.md`, `presets/prompts/openspec_implement_review.md`, `presets/prompts/openspec_implement_fix.md`, `presets/prompts/openspec_propose_review.md`, and `presets/prompts/openspec_propose_revise.md`
- [X] T002 [P] Add reusable prompt-asset fixture/helpers for OpenSpec presets in `tests/codex_orchestrator_cases_prompt.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish shared naming and dispatch contracts that block all user-story work.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Rename flow runner symbols to OpenSpec-prefixed names in `scripts/_codex_orchestrator/native_workflows/presets.py`
- [X] T004 Update built-in registry imports and key mapping to OpenSpec identifiers in `scripts/_codex_orchestrator/native_workflows/registry.py`
- [X] T005 [P] Update canonical preset examples in CLI/help and identifier validation messaging in `scripts/codex_automation_loops.py` and `scripts/_codex_orchestrator/paths.py`
- [X] T006 [P] Update baseline builtin preset list/order assertions for new identifiers in `tests/codex_orchestrator_cases_config.py`

**Checkpoint**: Shared naming/dispatch foundation is ready for story-specific implementation.

---

## Phase 3: User Story 1 - 统一重命名预设工作流 (Priority: P1) 🎯 MVP

**Goal**: 仅通过 `openspec_implement` 与 `openspec_propose` 调用工作流，并让运行时标识与产物键保持一致。

**Independent Test**: 使用 `run_workflow_direct("openspec_implement", ...)` 与 `run_workflow_direct("openspec_propose", ...)` 成功执行；旧名称触发 unknown preset 且提示新可用名称。

### Tests for User Story 1

- [X] T007 [P] [US1] Add CLI preset resolution tests for new identifiers and legacy-name rejection diagnostics in `tests/codex_orchestrator_cases_presets_cli.py`
- [X] T008 [P] [US1] Add runtime dispatch coverage for `openspec_implement` and `openspec_propose` entrypoints in `tests/codex_orchestrator_cases_runtime.py`

### Implementation for User Story 1

- [X] T009 [US1] Rename implement workflow stage ids/output keys/route bindings to `openspec_implement*` in `scripts/_codex_orchestrator/native_workflows/presets.py`
- [X] T010 [US1] Rename doc-doctor workflow entrypoint and runtime marker error strings to `openspec_propose*` in `scripts/_codex_orchestrator/native_workflows/presets.py`
- [X] T011 [US1] Switch built-in preset identifiers to `openspec_implement`/`openspec_propose` and remove legacy keys in `scripts/_codex_orchestrator/native_workflows/registry.py`
- [X] T012 [US1] Update CLI dispatch expectations and available-presets assertions to new names in `scripts/codex_automation_loops.py` and `tests/codex_orchestrator_cases_presets_cli.py`
- [X] T013 [US1] Update runtime artifact assertions for renamed node/output keys in `tests/codex_orchestrator_cases_runtime.py`

**Checkpoint**: US1 should be independently runnable with new preset names only.

---

## Phase 4: User Story 2 - 提示词模板外置化 (Priority: P1)

**Goal**: 将两个目标预设的提示词正文完全外置到 `presets/prompts/` 并由运行时文件加载。

**Independent Test**: 修改 `presets/prompts/openspec_implement*.md` 或 `presets/prompts/openspec_propose*.md` 后无需改动 `presets.py` 即可生效；缺失模板文件时运行明确失败。

### Tests for User Story 2

- [X] T014 [P] [US2] Add prompt rendering tests that assert OpenSpec stage templates are loaded from `prompt_file(...)` assets in `tests/codex_orchestrator_cases_prompt.py`
- [X] T015 [P] [US2] Add missing-template failure regression coverage for OpenSpec presets in `tests/codex_orchestrator_cases_runtime.py`

### Implementation for User Story 2

- [X] T016 [US2] Move OpenSpec implement-first prompt body to `presets/prompts/openspec_implement_implement_first.md`
- [X] T017 [US2] Move OpenSpec implement-check/loop prompt bodies to `presets/prompts/openspec_implement_review.md` and `presets/prompts/openspec_implement_fix.md`
- [X] T018 [US2] Move OpenSpec propose review/fix prompt bodies to `presets/prompts/openspec_propose_review.md` and `presets/prompts/openspec_propose_revise.md`
- [X] T019 [US2] Replace inline multiline prompts with `prompt_file("./openspec_*.md")` wiring in `scripts/_codex_orchestrator/native_workflows/presets.py`

**Checkpoint**: US2 templates are file-based, editable, and validated by runtime tests.

---

## Phase 5: User Story 3 - 文档与测试同步 (Priority: P2)

**Goal**: 文档与测试统一迁移到新名称，避免团队继续使用旧入口。

**Independent Test**: 相关测试全部通过；`docs/specs/` 中用户可见主入口仅保留新名称，旧名称仅出现在迁移说明或历史上下文。

### Tests for User Story 3

- [X] T020 [P] [US3] Update residual legacy preset literals in core/prompt tests in `tests/codex_orchestrator_cases_core.py` and `tests/codex_orchestrator_cases_prompt.py`
- [X] T021 [P] [US3] Add/adjust migration-behavior tests to assert legacy ids fail with new available list in `tests/codex_orchestrator_cases_presets_cli.py`

### Implementation for User Story 3

- [X] T022 [US3] Update preset naming scenarios to OpenSpec identifiers in `docs/specs/native-prefect-preset-orchestration/spec.md`
- [X] T023 [US3] Update enum-resolution examples and unknown-preset diagnostics to OpenSpec identifiers in `docs/specs/preset-enum-resolution/spec.md`
- [X] T024 [US3] Rename `docs/specs/doc-doctor-preset/spec.md` to `docs/specs/openspec-propose-preset/spec.md` and migrate its requirement wording to `openspec_propose`

**Checkpoint**: US3 eliminates active documentation/test guidance that depends on legacy preset names.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final consistency checks and verification evidence.

- [X] T025 [P] Scan for legacy identifiers and record allowed migration-only residues in `specs/001-openspec-workflow-rename/quickstart.md`
- [X] T026 Run focused regression commands for preset/config/runtime/prompt behavior against `tests/codex_orchestrator_cases_config.py`, `tests/codex_orchestrator_cases_presets_cli.py`, `tests/codex_orchestrator_cases_runtime.py`, and `tests/codex_orchestrator_cases_prompt.py`
- [X] T027 Run full quality gates (`ruff check scripts tests`, `ruff format scripts tests`, `basedpyright --warnings scripts tests`, `python3 -m pytest -q`) and record results in `specs/001-openspec-workflow-rename/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies, can start immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1, blocks all user-story phases.
- **Phase 3 (US1)**: Depends on Phase 2.
- **Phase 4 (US2)**: Depends on Phase 2 and should follow US1 naming migration for consistent asset prefixes.
- **Phase 5 (US3)**: Depends on US1 and US2 completion.
- **Phase 6 (Polish)**: Depends on all selected user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Starts after Foundational phase; no dependency on other user stories.
- **US2 (P1)**: Starts after Foundational; relies on renamed preset identifiers introduced by US1.
- **US3 (P2)**: Starts after US1 + US2 to synchronize tests/docs with final behavior.

### Within Each User Story

- Write/adjust tests first and confirm they fail before implementation changes.
- Update runtime/registry wiring before asserting final diagnostics text.
- Keep each story independently runnable using its own acceptance command path.

### Parallel Opportunities

- Setup: `T002` can run in parallel with `T001` after file targets are created.
- Foundational: `T005` and `T006` can run in parallel after `T003`/`T004` baseline rename.
- US1: `T007` and `T008` can run in parallel; `T012` and `T013` can be split once `T011` is merged.
- US2: `T014` and `T015` can run in parallel; `T017` and `T018` can run in parallel before final wiring `T019`.
- US3: `T020` and `T021` can run in parallel; `T022` and `T023` can run in parallel before `T024` rename finalization.

---

## Parallel Example: User Story 1

```bash
# Parallel test authoring for US1:
Task T007 -> tests/codex_orchestrator_cases_presets_cli.py
Task T008 -> tests/codex_orchestrator_cases_runtime.py

# After registry rename, split assertion updates:
Task T012 -> scripts/codex_automation_loops.py + tests/codex_orchestrator_cases_presets_cli.py
Task T013 -> tests/codex_orchestrator_cases_runtime.py
```

---

## Parallel Example: User Story 2

```bash
# Parallel prompt asset extraction:
Task T017 -> presets/prompts/openspec_implement_review.md + presets/prompts/openspec_implement_fix.md
Task T018 -> presets/prompts/openspec_propose_review.md + presets/prompts/openspec_propose_revise.md

# Parallel validation tasks:
Task T014 -> tests/codex_orchestrator_cases_prompt.py
Task T015 -> tests/codex_orchestrator_cases_runtime.py
```

---

## Parallel Example: User Story 3

```bash
# Parallel docs migration updates:
Task T022 -> docs/specs/native-prefect-preset-orchestration/spec.md
Task T023 -> docs/specs/preset-enum-resolution/spec.md

# Parallel test cleanup:
Task T020 -> tests/codex_orchestrator_cases_core.py + tests/codex_orchestrator_cases_prompt.py
Task T021 -> tests/codex_orchestrator_cases_presets_cli.py
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete US1 (Phase 3) to make new preset identifiers executable.
3. Validate US1 independently with focused CLI/runtime tests.

### Incremental Delivery

1. Ship US1 rename contract (`openspec_implement` / `openspec_propose`).
2. Ship US2 prompt externalization with file-based templates.
3. Ship US3 docs/test synchronization and contract path rename.
4. Run Phase 6 quality gates and capture final evidence.

### Parallel Team Strategy

1. One engineer owns registry/runtime rename path (`registry.py`, `presets.py`, runtime tests).
2. One engineer owns prompt asset extraction and prompt tests.
3. One engineer owns docs/spec contract migration and residual test cleanup.
4. Integrate on Phase 6 verification gates.

---

## Notes

- [P] tasks denote parallelizable work across different files or non-blocking concerns.
- Story labels map every behavioral task to a user story for independent delivery.
- Legacy identifiers (`implement_loop`, `doc_doctor`) should remain only in explicit migration diagnostics/history context.
