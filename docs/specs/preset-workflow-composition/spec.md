# preset-workflow-composition Specification

## Purpose
TBD - created by archiving change compose-preset-workflows-add-doc-doctor. Update Purpose after archive.
## Requirements
### Requirement: Workflow root fields are strictly validated for all presets
The orchestrator MUST reject deprecated workflow-composition DSL fields and require native preset-flow orchestration behavior.

#### Scenario: Deprecated workflow DSL fields are rejected with actionable diagnostics
- **WHEN** a preset configuration includes legacy workflow-composition fields (for example `workflow.imports`, `workflow.node_overrides`, or node-level `success_next_node_from`)
- **THEN** validation SHALL fail with an error that points to the deprecated field path
- **THEN** the error SHALL direct users to native preset-flow orchestration instead of YAML graph composition

#### Scenario: Native built-in preset execution does not depend on workflow composition schema
- **WHEN** a user executes a built-in preset through preset identifier resolution
- **THEN** orchestration SHALL run through native Prefect flow implementations
- **THEN** execution SHALL NOT require `workflow` composition sections to be present in preset files

