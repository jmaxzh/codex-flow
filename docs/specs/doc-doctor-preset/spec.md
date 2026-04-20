# doc-doctor-preset Specification

## Purpose
TBD - created by archiving change compose-preset-workflows-add-doc-doctor. Update Purpose after archive.
## Requirements
### Requirement: Built-in doc_doctor preset is available
The orchestrator MUST provide a built-in preset identifier `doc_doctor`.

#### Scenario: doc_doctor preset can be resolved by identifier
- **WHEN** a user runs workflow orchestration with `--preset doc_doctor`
- **THEN** the system SHALL resolve to the built-in native flow implementation `doc_doctor`

### Requirement: doc_doctor workflow composes staged review and conditional fix loop
The `doc_doctor` preset SHALL implement a staged remediation loop where each round first completes review convergence, then conditionally runs fix via programmatic runtime routing in flow code.

#### Scenario: Stage id remains doc_reviwer in routing and history contracts
- **WHEN** `doc_doctor` flow defines and routes review stage execution
- **THEN** stage id SHALL be exactly `doc_reviwer`
- **THEN** flow wiring/tests/history keys SHALL use `doc_reviwer` consistently
- **THEN** implementation SHALL NOT silently rename it to `doc_reviewer`

#### Scenario: doc_doctor starts from review node
- **WHEN** `doc_doctor` preset starts execution
- **THEN** the first stage SHALL execute `doc_reviwer`

#### Scenario: pass=true only marks review-stage completion
- **WHEN** stage `doc_reviwer` produces `pass=true`
- **THEN** the system SHALL treat this as "review stage finished" for the current round
- **THEN** this signal alone SHALL NOT imply `doc_fix` must run
- **THEN** post-stage routing SHALL be decided by runtime stage marker state in flow logic, not extra prompt judgement

#### Scenario: Review failure keeps review self-loop
- **WHEN** stage `doc_reviwer` produces `pass=false`
- **THEN** the flow SHALL route back to `doc_reviwer`
- **THEN** the failure route SHALL set runtime stage marker for entering `doc_fix`

#### Scenario: End directly when review stage has no prior failure
- **WHEN** the current review stage has finished (`pass=true`)
- **AND** runtime stage marker for fix is absent
- **THEN** the flow SHALL route to end
- **THEN** `doc_fix` SHALL NOT execute in this round

#### Scenario: Enter fix when review stage had prior failures
- **WHEN** the current review stage has finished (`pass=true`)
- **AND** runtime stage marker indicates `doc_fix`
- **THEN** the flow SHALL route to stage `doc_fix`

#### Scenario: Fix success returns to review re-check
- **WHEN** stage `doc_fix` executes successfully
- **THEN** the flow SHALL route back to `doc_reviwer`
- **THEN** success route SHALL reset stage marker to end target for the next completion decision

#### Scenario: Loop keeps the same stage-complete then decision rule across rounds
- **WHEN** `doc_fix` has returned to `doc_reviwer` for re-check
- **THEN** the next round SHALL again complete review stage first (self-loop until `pass=true`)
- **THEN** after stage completion, routing SHALL again be decided by runtime stage marker state

### Requirement: Programmatic success-route override supports doc_doctor staged branching
The orchestrator MUST support optional node-level success-route override via dotted path so composed presets can make deterministic post-stage branching without LLM decision prompts.

#### Scenario: success_next_node_from overrides on_success when path resolves
- **WHEN** a node is configured with `success_next_node_from` and finishes with `pass=true`
- **AND** the configured path resolves to a non-empty string target
- **THEN** the runtime SHALL route to that resolved target instead of static `on_success`

#### Scenario: success_next_node_from falls back to on_success when path missing
- **WHEN** a node is configured with `success_next_node_from` and finishes with `pass=true`
- **AND** the configured path is not found in runtime state
- **THEN** the runtime SHALL keep static `on_success` target

#### Scenario: success_next_node_from validates resolved target
- **WHEN** a node is configured with `success_next_node_from` and finishes with `pass=true`
- **AND** the resolved value is not `END` and does not match any workflow node id
- **THEN** runtime execution SHALL fail with invalid next-node error

### Requirement: doc_doctor preserves review-history accumulation contract
The review stage in `doc_doctor` MUST keep appending outputs to full review history for downstream fix consumption.

#### Scenario: Review stage still writes into doc_review_history
- **WHEN** `doc_doctor` executes review stage iterations
- **THEN** outputs from `doc_reviwer` SHALL append to `context.runtime.doc_review_history`
- **THEN** `doc_fix` SHALL read review history from `context.runtime.doc_review_history`

### Requirement: doc_doctor declares required local non-workflow config
The `doc_doctor` preset MUST declare required local runtime defaults without relying on workflow import inheritance.

#### Scenario: doc_doctor runs without explicit user_instruction override
- **WHEN** a user runs `--preset doc_doctor` without passing `--context user_instruction=<...>`
- **THEN** the preset SHALL still provide `context.defaults.user_instruction`
- **THEN** `doc_fix` input mapping to `context.defaults.user_instruction` SHALL resolve successfully

#### Scenario: doc_doctor declares local stage-routing constants
- **WHEN** `doc_doctor` executes as a native flow
- **THEN** default fix target marker SHALL equal `doc_fix`
- **THEN** default end target marker SHALL equal `END`

### Requirement: doc_fix consumes only instruction and full review history
The `doc_fix` stage in `doc_doctor` MUST receive only original task intent and full document review history as inputs.

#### Scenario: doc_fix input map includes only required sources
- **WHEN** `doc_fix` executes in `doc_doctor`
- **THEN** its prompt inputs SHALL include `context.defaults.user_instruction`
- **THEN** its prompt inputs SHALL include `context.runtime.doc_review_history`
- **THEN** it SHALL NOT require a separate field representing only the latest review round

#### Scenario: doc_fix prompt consumes both mapped inputs
- **WHEN** `doc_fix` executes in `doc_doctor`
- **THEN** `doc_fix` prompt rendering SHALL inject values from `user_instruction` and `doc_review_history`
- **THEN** compliance for this prompt-consumption contract SHALL be enforced by preset wiring tests

#### Scenario: doc_fix does not write review history
- **WHEN** `doc_fix` executes in `doc_doctor`
- **THEN** it SHALL NOT append into `context.runtime.doc_review_history`

### Requirement: doc_fix runs after review convergence and does not use pass-based routing
The `doc_fix` stage in `doc_doctor` MUST run as plain-text execution without JSON control-line pass evaluation, and MUST return to review for re-check.

#### Scenario: doc_fix runs without control JSON contract
- **WHEN** `doc_fix` executes in `doc_doctor`
- **THEN** `doc_fix` SHALL be configured with `parse_output_json=false`
- **THEN** workflow routing from `doc_fix` SHALL continue to `doc_reviwer` on successful execution
- **THEN** runtime execution exceptions from `doc_fix` SHALL fail the run directly and SHALL NOT be treated as pass-based branch selection

