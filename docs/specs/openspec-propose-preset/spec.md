# openspec-propose-preset Specification

## Purpose
TBD - created by archiving change compose-preset-workflows-add-doc-doctor. Update Purpose after archive.
## Requirements
### Requirement: Built-in openspec_propose preset is available
The orchestrator MUST provide a built-in preset identifier `openspec_propose`.

#### Scenario: openspec_propose preset can be resolved by identifier
- **WHEN** a user runs workflow orchestration with `--preset openspec_propose`
- **THEN** the system SHALL resolve to the built-in native flow implementation `openspec_propose`

### Requirement: openspec_propose workflow composes staged review and conditional fix loop
The `openspec_propose` preset SHALL implement a staged remediation loop where each round first completes review convergence, then conditionally runs fix via programmatic runtime routing in flow code.

#### Scenario: Stage id remains openspec_propose_review in routing and history contracts
- **WHEN** `openspec_propose` flow defines and routes review stage execution
- **THEN** stage id SHALL be exactly `openspec_propose_review`
- **THEN** flow wiring/tests/history keys SHALL use `openspec_propose_review` consistently
- **THEN** implementation SHALL NOT silently rename it to `openspec_propose_doc_reviewer`

#### Scenario: openspec_propose starts from review node
- **WHEN** `openspec_propose` preset starts execution
- **THEN** the first stage SHALL execute `openspec_propose_review`

#### Scenario: pass=true only marks review-stage completion
- **WHEN** stage `openspec_propose_review` produces `pass=true`
- **THEN** the system SHALL treat this as "review stage finished" for the current round
- **THEN** this signal alone SHALL NOT imply `openspec_propose_revise` must run
- **THEN** post-stage routing SHALL be decided by runtime stage marker state in flow logic, not extra prompt judgement

#### Scenario: Review failure keeps review self-loop
- **WHEN** stage `openspec_propose_review` produces `pass=false`
- **THEN** the flow SHALL route back to `openspec_propose_review`
- **THEN** the failure route SHALL set runtime stage marker for entering `openspec_propose_revise`

#### Scenario: End directly when review stage has no prior failure
- **WHEN** the current review stage has finished (`pass=true`)
- **AND** runtime stage marker for fix is absent
- **THEN** the flow SHALL route to end
- **THEN** `openspec_propose_revise` SHALL NOT execute in this round

#### Scenario: Enter fix when review stage had prior failures
- **WHEN** the current review stage has finished (`pass=true`)
- **AND** runtime stage marker indicates `openspec_propose_revise`
- **THEN** the flow SHALL route to stage `openspec_propose_revise`

#### Scenario: Fix success returns to review re-check
- **WHEN** stage `openspec_propose_revise` executes successfully
- **THEN** the flow SHALL route back to `openspec_propose_review`
- **THEN** success route SHALL reset stage marker to end target for the next completion decision

#### Scenario: Loop keeps the same stage-complete then decision rule across rounds
- **WHEN** `openspec_propose_revise` has returned to `openspec_propose_review` for re-check
- **THEN** the next round SHALL again complete review stage first (self-loop until `pass=true`)
- **THEN** after stage completion, routing SHALL again be decided by runtime stage marker state

### Requirement: Programmatic success-route override supports openspec_propose staged branching
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

### Requirement: openspec_propose preserves review-history accumulation contract
The review stage in `openspec_propose` MUST keep appending outputs to full review history for downstream fix consumption.

#### Scenario: Review stage still writes into doc_review_history
- **WHEN** `openspec_propose` executes review stage iterations
- **THEN** outputs from `openspec_propose_review` SHALL append to `context.runtime.doc_review_history`
- **THEN** `openspec_propose_revise` SHALL read review history from `context.runtime.doc_review_history`

### Requirement: openspec_propose declares required local non-workflow config
The `openspec_propose` preset MUST declare required local runtime defaults without relying on workflow import inheritance.

#### Scenario: openspec_propose runs without explicit user_instruction override
- **WHEN** a user runs `--preset openspec_propose` without passing `--context user_instruction=<...>`
- **THEN** the preset SHALL still provide `context.defaults.user_instruction`
- **THEN** `openspec_propose_revise` input mapping to `context.defaults.user_instruction` SHALL resolve successfully

#### Scenario: openspec_propose declares local stage-routing constants
- **WHEN** `openspec_propose` executes as a native flow
- **THEN** default fix target marker SHALL equal `openspec_propose_revise`
- **THEN** default end target marker SHALL equal `END`

### Requirement: openspec_propose_revise consumes only instruction and full review history
The `openspec_propose_revise` stage in `openspec_propose` MUST receive only original task intent and full document review history as inputs.

#### Scenario: openspec_propose_revise input map includes only required sources
- **WHEN** `openspec_propose_revise` executes in `openspec_propose`
- **THEN** its prompt inputs SHALL include `context.defaults.user_instruction`
- **THEN** its prompt inputs SHALL include `context.runtime.doc_review_history`
- **THEN** it SHALL NOT require a separate field representing only the latest review round

#### Scenario: openspec_propose_revise prompt consumes both mapped inputs
- **WHEN** `openspec_propose_revise` executes in `openspec_propose`
- **THEN** `openspec_propose_revise` prompt rendering SHALL inject values from `user_instruction` and `doc_review_history`
- **THEN** compliance for this prompt-consumption contract SHALL be enforced by preset wiring tests

#### Scenario: openspec_propose_revise does not write review history
- **WHEN** `openspec_propose_revise` executes in `openspec_propose`
- **THEN** it SHALL NOT append into `context.runtime.doc_review_history`

### Requirement: openspec_propose_revise runs after review convergence and does not use pass-based routing
The `openspec_propose_revise` stage in `openspec_propose` MUST run as plain-text execution without JSON control-line pass evaluation, and MUST return to review for re-check.

#### Scenario: openspec_propose_revise runs without control JSON contract
- **WHEN** `openspec_propose_revise` executes in `openspec_propose`
- **THEN** `openspec_propose_revise` SHALL be configured with `parse_output_json=false`
- **THEN** workflow routing from `openspec_propose_revise` SHALL continue to `openspec_propose_review` on successful execution
- **THEN** runtime execution exceptions from `openspec_propose_revise` SHALL fail the run directly and SHALL NOT be treated as pass-based branch selection
