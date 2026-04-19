# preset-workflow-composition Specification

## Purpose
TBD - created by archiving change compose-preset-workflows-add-doc-doctor. Update Purpose after archive.
## Requirements
### Requirement: Workflow can import built-in preset nodes
The orchestrator configuration MUST allow a workflow to import node definitions from one or more built-in preset identifiers before compiling local nodes.

#### Scenario: Single preset import composes imported and local nodes
- **WHEN** a preset defines `workflow.imports` with one built-in preset id and also defines local `workflow.nodes`
- **THEN** the compiler SHALL include imported nodes and local nodes in one compiled workflow graph
- **THEN** the compiled workflow SHALL be validated by the same node-id and transition checks as non-composed presets

#### Scenario: Multiple imports apply in declaration order
- **WHEN** a preset defines `workflow.imports` with multiple built-in preset identifiers
- **THEN** the compiler SHALL process imports in declaration order
- **THEN** duplicate node ids across imported/local nodes SHALL fail compilation with an actionable duplicate-node error

#### Scenario: Import does not merge non-workflow fields
- **WHEN** a preset imports another preset and also declares local non-workflow sections
- **THEN** the compiler SHALL import only `workflow.nodes` from imported presets
- **THEN** imported preset fields outside `workflow` (including `run`, `executor`, `context`) SHALL NOT be inherited or merged

### Requirement: Composed workflow keeps explicit entry contract
The orchestrator configuration MUST keep explicit `workflow.start` validation after composition, while allowing local `workflow.nodes` to be omitted.

#### Scenario: Imports-only workflow compiles with explicit start
- **WHEN** a preset defines `workflow.imports` and omits local `workflow.nodes`
- **THEN** the compiler SHALL treat local nodes as an empty list and compile with imported nodes only
- **THEN** `workflow.start` SHALL still be explicitly declared in the composed preset
- **THEN** `workflow.start` SHALL target a node that exists in the final compiled graph

#### Scenario: Imports-only workflow compiles when local nodes is empty array
- **WHEN** a preset defines `workflow.imports` and sets local `workflow.nodes` to `[]`
- **THEN** the compiler SHALL treat local nodes as an empty list and compile with imported nodes only
- **THEN** `workflow.start` SHALL still be explicitly declared in the composed preset
- **THEN** `workflow.start` SHALL target a node that exists in the final compiled graph

#### Scenario: Composed workflow omits explicit start
- **WHEN** a preset defines `workflow.imports` but omits `workflow.start`
- **THEN** compilation SHALL fail with an error indicating `workflow.start` is required on the composed preset itself

#### Scenario: Composed workflow with empty final node set is rejected
- **WHEN** a preset has no importable nodes and no local nodes after composition
- **THEN** compilation SHALL fail because the final workflow graph is empty

### Requirement: Imported nodes can be rewired by controlled overrides
The orchestrator configuration MUST allow rewiring imported nodes through `workflow.node_overrides` without requiring full node duplication.

#### Scenario: Override updates imported node success route
- **WHEN** `workflow.node_overrides.<node_id>.on_success` is configured for an imported node
- **THEN** the compiled node SHALL use the overridden `on_success` value
- **THEN** transition validation SHALL enforce that the new target exists or equals `END`

#### Scenario: Override updates imported node failure route
- **WHEN** `workflow.node_overrides.<node_id>.on_failure` is configured for an imported node
- **THEN** the compiled node SHALL use the overridden `on_failure` value
- **THEN** transition validation SHALL enforce that the new target exists or equals `END`

#### Scenario: Override updates route bindings with route-level replacement
- **WHEN** `workflow.node_overrides.<node_id>.route_bindings` is configured for an imported node
- **THEN** each provided route key (`success` or `failure`) SHALL replace that route's full mapping on the imported node
- **THEN** any route not provided in override SHALL keep the imported node's original mapping
- **THEN** route binding validation SHALL use the same source/target path rules as regular node `route_bindings`

#### Scenario: Override object contains unknown fields
- **WHEN** `workflow.node_overrides.<node_id>` includes keys other than `on_success`, `on_failure`, `route_bindings`, or `success_next_node_from`
- **THEN** compilation SHALL fail with an unknown-field validation error for that override object

#### Scenario: Override references non-imported node
- **WHEN** `workflow.node_overrides` contains a node id that is not present in imported nodes (including local-only nodes)
- **THEN** compilation SHALL fail with an error indicating override target must be an imported node id

### Requirement: Imported preset references follow built-in preset identifier rules
Imported preset references MUST use the same built-in preset identifier semantics as CLI `--preset`.

#### Scenario: Import uses unknown preset identifier
- **WHEN** `workflow.imports[].preset` references an identifier that does not exist in repository built-in presets
- **THEN** compilation SHALL fail with an unknown-preset error
- **THEN** the error SHALL include available built-in preset identifiers

#### Scenario: Import uses path-like preset value
- **WHEN** `workflow.imports[].preset` contains path separators or `.yaml` suffix values that violate identifier rules
- **THEN** compilation SHALL fail with an identifier-validation error

#### Scenario: Import entry contains unknown fields
- **WHEN** an object in `workflow.imports[]` includes keys other than `preset`
- **THEN** compilation SHALL fail with an unknown-field validation error for that import entry

### Requirement: Workflow root fields are strictly validated for all presets
The orchestrator configuration MUST reject unknown keys at `workflow` root level for all presets.

#### Scenario: Workflow root contains unknown fields
- **WHEN** a preset sets unknown keys under `workflow` (for example `workflow.import` or `workflow.node_override`)
- **THEN** compilation SHALL fail with an unknown-field validation error for `workflow`
- **THEN** the compiler SHALL NOT silently ignore unknown `workflow` root keys

### Requirement: Nodes support optional success-route override source
The orchestrator configuration MUST allow nodes to declare an optional `success_next_node_from` dotted source path for deterministic programmatic branching on successful node completion.

#### Scenario: Compiler accepts success_next_node_from with allowed source prefix
- **WHEN** a node sets `success_next_node_from` to a valid source path under `context.defaults.*`, `context.runtime.*`, or `outputs.*`
- **THEN** compilation SHALL succeed and persist compiled source metadata for runtime resolution

#### Scenario: Compiler rejects invalid success_next_node_from path
- **WHEN** a node sets `success_next_node_from` to a path outside allowed source prefixes
- **THEN** compilation SHALL fail with source-path validation error

### Requirement: Preset imports are single-level and non-recursive
The orchestrator configuration MUST resolve `workflow.imports` in one level only and MUST reject nested imports in imported presets.

#### Scenario: Imported preset declares nested imports
- **WHEN** a preset listed in `workflow.imports` itself contains `workflow.imports`
- **THEN** compilation SHALL fail with an error indicating nested imports are not supported
- **THEN** the compiler SHALL NOT recursively expand imported presets

