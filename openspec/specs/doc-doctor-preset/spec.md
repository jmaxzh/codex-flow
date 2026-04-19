# doc-doctor-preset Specification

## Purpose
TBD - created by archiving change compose-preset-workflows-add-doc-doctor. Update Purpose after archive.
## Requirements
### Requirement: Built-in doc_doctor preset is available
The orchestrator MUST provide a built-in preset identifier `doc_doctor`.

#### Scenario: doc_doctor preset can be resolved by identifier
- **WHEN** a user runs workflow orchestration with `--preset doc_doctor`
- **THEN** the system SHALL resolve to the built-in preset file under repository `presets/`

### Requirement: doc_doctor workflow composes staged review and conditional fix loop
The `doc_doctor` preset SHALL compose the existing document review loop and a fix node into a staged remediation loop where each round first completes review convergence, then conditionally runs fix via programmatic runtime routing (without prompt-based decision nodes).

#### Scenario: doc_doctor starts from review node
- **WHEN** `doc_doctor` preset is compiled
- **THEN** `workflow.start` SHALL equal `doc_reviwer`

#### Scenario: pass=true only marks review-stage completion
- **WHEN** node `doc_reviwer` produces `pass=true`
- **THEN** the system SHALL treat this as "review stage finished" for the current round
- **THEN** this signal alone SHALL NOT imply `doc_fix` must run
- **THEN** post-stage routing SHALL be decided by runtime stage marker state, not by extra prompt judgement

#### Scenario: Review failure keeps review self-loop
- **WHEN** node `doc_reviwer` produces `pass=false`
- **THEN** the workflow SHALL route back to `doc_reviwer`
- **THEN** the failure route SHALL write `context.runtime.doc_review_next_node` from `context.defaults.doc_review_fix_node`

#### Scenario: End directly when review stage has no prior failure
- **WHEN** the current review stage has finished (`pass=true`)
- **AND** `context.runtime.doc_review_next_node` is absent
- **THEN** the workflow SHALL route to `END`
- **THEN** `doc_fix` SHALL NOT execute in this round

#### Scenario: Enter fix when review stage had prior failures
- **WHEN** the current review stage has finished (`pass=true`)
- **AND** runtime `success_next_node_from` resolves to `doc_fix`
- **THEN** the workflow SHALL route to node `doc_fix`

#### Scenario: Fix success returns to review re-check
- **WHEN** node `doc_fix` executes successfully
- **THEN** the workflow SHALL route back to `doc_reviwer`
- **THEN** success route SHALL reset `context.runtime.doc_review_next_node` from `context.defaults.doc_review_end_node`

#### Scenario: Loop keeps the same stage-complete then decision rule across rounds
- **WHEN** `doc_fix` has returned to `doc_reviwer` for re-check
- **THEN** the next round SHALL again complete review stage first (self-loop until `pass=true`)
- **THEN** after stage completion, routing SHALL again be decided by runtime `doc_review_next_node` marker:
- **THEN** marker absent/`END` routes to `END`, and marker `doc_fix` routes to `doc_fix`

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
The imported review node in `doc_doctor` MUST keep appending outputs to full review history for downstream fix consumption.

#### Scenario: Review node still writes into doc_review_history
- **WHEN** `doc_doctor` is compiled from imported `doc_reviewer_loop` nodes plus local rewiring
- **THEN** node `doc_reviwer` SHALL keep `collect_history_to: context.runtime.doc_review_history`
- **THEN** `doc_fix` SHALL read review history from `context.runtime.doc_review_history`

### Requirement: doc_doctor declares required local non-workflow config
Because imports only compose workflow nodes, the `doc_doctor` preset MUST declare required non-workflow top-level config locally, including `run` and `context.defaults.user_instruction`.

#### Scenario: doc_doctor runs without explicit user_instruction override
- **WHEN** a user runs `--preset doc_doctor` without passing `--context user_instruction=<...>`
- **THEN** the preset SHALL still provide `context.defaults.user_instruction` from its local config
- **THEN** `doc_fix` input mapping to `context.defaults.user_instruction` SHALL resolve successfully

#### Scenario: doc_doctor satisfies local top-level run contract
- **WHEN** `doc_doctor` is compiled as a composed preset
- **THEN** `doc_doctor` SHALL provide required top-level `run` configuration locally
- **THEN** compilation SHALL NOT depend on inheriting `run` from imported presets

#### Scenario: doc_doctor declares local stage-routing constants
- **WHEN** `doc_doctor` is compiled as a composed preset
- **THEN** `context.defaults.doc_review_fix_node` SHALL equal `"doc_fix"`
- **THEN** `context.defaults.doc_review_end_node` SHALL equal `"END"`

### Requirement: doc_fix consumes only instruction and full review history
The `doc_fix` node in `doc_doctor` MUST receive only original task intent and full document review history as inputs.

#### Scenario: doc_fix input map includes only required sources
- **WHEN** `doc_fix` is compiled in `doc_doctor`
- **THEN** its input mapping SHALL include `context.defaults.user_instruction`
- **THEN** its input mapping SHALL include `context.runtime.doc_review_history`
- **THEN** its input mapping SHALL contain exactly these two bindings and no additional inputs
- **THEN** it SHALL NOT require a separate field representing only the latest review round

#### Scenario: doc_fix prompt consumes both mapped inputs
- **WHEN** `doc_fix` is compiled in `doc_doctor`
- **THEN** `doc_fix.prompt` SHALL reference `inputs.user_instruction`
- **THEN** `doc_fix.prompt` SHALL reference `inputs.doc_review_history`
- **THEN** runtime prompt rendering for `doc_fix` SHALL inject values from these two mapped inputs into the execution prompt
- **THEN** compliance for this prompt-consumption contract SHALL be enforced by preset wiring tests asserting these two prompt references
- **THEN** this requirement SHALL NOT require introducing generic compile-time static analysis of prompt template contents

#### Scenario: doc_fix does not write review history
- **WHEN** `doc_fix` is compiled in `doc_doctor`
- **THEN** `doc_fix` SHALL NOT configure `collect_history_to`
- **THEN** it SHALL NOT write into `context.runtime.doc_review_history`

### Requirement: doc_fix runs after review convergence and does not use pass-based routing
The `doc_fix` node in `doc_doctor` MUST run as plain-text execution without JSON control-line pass evaluation, and MUST return to review for re-check.

#### Scenario: doc_fix runs without control JSON contract
- **WHEN** `doc_fix` executes in `doc_doctor`
- **THEN** `doc_fix` SHALL be configured with `parse_output_json=false`
- **THEN** workflow routing from `doc_fix` SHALL follow non-JSON node behavior and continue to `doc_reviwer` on successful execution
- **THEN** `doc_fix.on_failure` SHALL be configured as `END` for transition-contract completeness
- **THEN** runtime execution exceptions from `doc_fix` SHALL fail the run directly and SHALL NOT be treated as `on_failure` branch routing

