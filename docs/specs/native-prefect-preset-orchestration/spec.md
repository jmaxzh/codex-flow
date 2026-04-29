# native-prefect-preset-orchestration Specification

## Purpose
TBD - created by archiving change switch-to-native-prefect-workflows. Update Purpose after archive.
## Requirements
### Requirement: Built-in presets are implemented as native Prefect flows
The system SHALL define each built-in preset workflow as a native Prefect flow in Python code, not as interpreted workflow-node DSL.

#### Scenario: OpenSpec implement preset runs as native flow
- **WHEN** a user executes the `openspec_implement` preset
- **THEN** the orchestrator SHALL run a dedicated native Prefect flow for `openspec_implement`
- **THEN** control flow SHALL be expressed in Python flow logic rather than interpreted from `workflow.nodes`

#### Scenario: Quality review loop preset runs as native flow
- **WHEN** a user executes the `quality_review_loop` preset
- **THEN** the orchestrator SHALL run a dedicated native Prefect flow for `quality_review_loop`
- **THEN** loop continuation SHALL be decided by flow code using parsed node control semantics

#### Scenario: Reviewer presets run as native flows
- **WHEN** a user executes `bug_review_loop` or `doc_review_loop`
- **THEN** each preset SHALL run through its own native Prefect flow
- **THEN** review history accumulation SHALL be handled by flow runtime state updates without DSL graph compilation

#### Scenario: OpenSpec propose preset runs as native staged flow
- **WHEN** a user executes `openspec_propose`
- **THEN** the orchestrator SHALL run a dedicated native Prefect flow that encodes review convergence and conditional fix routing directly in code

### Requirement: Preset module directory contains only per-preset workflow modules
The `scripts/_codex_orchestrator/native_workflows/presets/` directory MUST contain only files where each file represents one preset workflow definition; shared helper modules MUST live outside this directory.

#### Scenario: Shared workflow helpers are stored in dedicated common directory
- **WHEN** implementation requires reusable workflow helper code across multiple presets
- **THEN** that helper code SHALL be placed under `scripts/_codex_orchestrator/native_workflows/preset_common/` (or another non-`presets/` common location)
- **THEN** files under `scripts/_codex_orchestrator/native_workflows/presets/` SHALL remain per-preset workflow modules only

### Requirement: Workflow DSL graph compilation is removed from runtime path
The system MUST NOT require workflow graph compilation from `workflow.nodes`-style DSL for built-in preset execution.

#### Scenario: Runtime does not compile workflow graph
- **WHEN** the orchestrator starts a built-in preset run
- **THEN** it SHALL dispatch to a flow registry entry
- **THEN** it SHALL NOT compile `workflow.nodes` into an internal execution graph before running

### Requirement: Common node execution utilities remain reusable across flows
Native preset flows SHALL use shared execution utilities for prompt rendering, model execution, output parsing, and artifact persistence.

#### Scenario: Native flows share rendering and execution primitives
- **WHEN** two different presets execute nodes that require prompt rendering and `codex exec`
- **THEN** both SHALL use shared utility functions/tasks for these concerns
- **THEN** behavior for prompt render strictness, output capture, and file persistence SHALL remain consistent across presets

### Requirement: CLI preset contract remains identifier-based with context overrides
The CLI SHALL continue to accept `--preset` and repeatable `--context` overrides while dispatching to native flow implementations.

#### Scenario: Context overrides are injected for native preset run
- **WHEN** a user provides one or more `--context key value` pairs for a built-in preset
- **THEN** the orchestrator SHALL merge overrides into runtime defaults passed to the selected native flow
- **THEN** key collision resolution SHALL remain last-write-wins for repeated keys

### Requirement: Flow registry entries follow one callable contract
Each built-in preset registry entry SHALL expose a unified callable contract so CLI dispatch does not require preset-specific branching.

#### Scenario: Registry callable accepts normalized launch inputs
- **WHEN** CLI dispatch selects a built-in preset flow from the registry
- **THEN** the selected callable SHALL accept the normalized context overrides from `--context` after last-write-wins merge
- **THEN** the selected callable SHALL accept launch cwd context from CLI for deterministic relative-path behavior

#### Scenario: Registry callable returns unified run summary object
- **WHEN** a built-in preset flow run completes successfully
- **THEN** the flow callable SHALL return one run summary object with top-level fields `status`, `run_id`, `run_state_dir`, `final_node`, `steps_executed`, and `outputs`

#### Scenario: Flow execution failures propagate through the same boundary
- **WHEN** any built-in preset flow raises execution error (for example render/parse/route/runtime failure)
- **THEN** registry dispatch SHALL propagate the failure through the same callable boundary
- **THEN** CLI error handling SHALL treat it as a failed run and SHALL NOT convert it to a successful run summary

### Requirement: Loop presets enforce deterministic step-limit termination
Any native preset flow with loop behavior SHALL enforce `run.max_steps` as a hard upper bound with explicit failure semantics.

#### Scenario: Step counting is based on executed stages
- **WHEN** a loop preset flow executes one stage attempt
- **THEN** the runtime step counter SHALL increment by one for that executed stage

#### Scenario: Run fails if END is not reached within max_steps
- **WHEN** loop execution reaches `run.max_steps` and current node is still not `END`
- **THEN** the flow run SHALL terminate with an explicit max-steps error
- **THEN** the run SHALL be treated as failed (not completed)

#### Scenario: Run succeeds when END is reached within max_steps
- **WHEN** loop execution reaches `END` before exceeding `run.max_steps`
- **THEN** the flow run SHALL finalize as completed and produce the normal run summary contract

### Requirement: One-shot replacement without DSL compatibility mode
The migration SHALL be a one-shot replacement and SHALL NOT provide runtime compatibility mode for legacy workflow DSL execution.

#### Scenario: No dual-path execution mode exists
- **WHEN** the native Prefect migration is applied
- **THEN** built-in preset execution SHALL use only native flow dispatch
- **THEN** the system SHALL NOT expose a switch to choose legacy DSL execution path
