# preset-enum-resolution Specification

## Purpose
TBD - created by archiving change fix-preset-enum-resolution. Update Purpose after archive.
## Requirements
### Requirement: Preset identifier semantics
The CLI `--preset` parameter MUST be treated as a built-in preset identifier that resolves to a native flow entry, not a file path.

#### Scenario: Identifier value is accepted
- **WHEN** a user passes `--preset openspec_implement`
- **THEN** the system SHALL interpret `openspec_implement` as a preset identifier
- **THEN** the system SHALL resolve it to the built-in native flow implementation for `openspec_implement`

#### Scenario: Path-like value is rejected
- **WHEN** a user passes `--preset presets/openspec_implement.yaml` or any value containing path separators
- **THEN** argument validation SHALL fail before workflow execution
- **THEN** the error message SHALL state that `--preset` expects a preset identifier

#### Scenario: Empty or whitespace-only identifier is rejected
- **WHEN** a user passes an empty or whitespace-only value to `--preset`
- **THEN** argument validation SHALL fail before workflow execution
- **THEN** the error message SHALL state that `--preset` requires a non-empty preset identifier

#### Scenario: Identifier with `.yaml` suffix is rejected
- **WHEN** a user passes `--preset openspec_implement.yaml` without path separators
- **THEN** argument validation SHALL fail before workflow execution
- **THEN** the error message SHALL state that `--preset` accepts extensionless preset identifiers
- **THEN** the error message SHALL include a migration hint to use `openspec_implement` instead of `openspec_implement.yaml`

### Requirement: CWD-independent preset resolution
Preset identifier lookup MUST be deterministic and independent of the command invocation directory.

#### Scenario: Same preset from different cwd resolves identically
- **WHEN** the same command with `--preset openspec_implement` is run from two different current working directories
- **THEN** both invocations SHALL resolve to the same built-in native flow identifier

#### Scenario: Lookup base is built-in flow registry
- **WHEN** the orchestrator resolves a valid preset identifier
- **THEN** it SHALL use the code-defined built-in preset flow registry as the lookup base
- **THEN** it SHALL NOT depend on `Path.cwd()` for preset resolution

### Requirement: Actionable unknown-preset diagnostics
Unknown preset identifiers MUST produce actionable errors.

#### Scenario: Unknown preset is reported with available options
- **WHEN** a user passes an identifier that does not exist in the built-in preset registry
- **THEN** execution SHALL fail with a clear unknown-preset error
- **THEN** the error MUST include available preset identifiers to guide correction

### Requirement: New built-in presets are discoverable through identifier diagnostics
When a new built-in preset is added, unknown-preset diagnostics MUST include that identifier in the available preset list.

#### Scenario: unknown preset diagnostics list includes openspec_propose
- **WHEN** a user passes an unknown preset identifier after `openspec_propose` is present in the built-in registry
- **THEN** the unknown-preset error SHALL include `openspec_propose` in the available built-in preset identifiers list

### Requirement: New built-in preset identifiers resolve through the same deterministic lookup
New built-in presets MUST resolve via the same identifier lookup semantics.

#### Scenario: openspec_propose resolves deterministically from different cwd
- **WHEN** preset resolution for `openspec_propose` is evaluated from different current working directories
- **THEN** both resolutions SHALL point to the same built-in native flow identifier
- **THEN** resolution SHALL NOT depend on invocation `cwd`

### Requirement: Legacy and openspec identifiers coexist for backward compatibility
Legacy preset identifiers from previous contracts MUST remain available while openspec identifiers are also supported.

#### Scenario: implement_loop remains resolvable after openspec rollout
- **WHEN** a user passes `--preset implement_loop`
- **THEN** the system SHALL resolve it to the built-in native flow implementation for `implement_loop`
- **THEN** `openspec_implement` and `openspec_propose` SHALL remain valid built-in preset identifiers

#### Scenario: doc_doctor remains resolvable after openspec rollout
- **WHEN** a user passes `--preset doc_doctor`
- **THEN** the system SHALL resolve it to the built-in native flow implementation for `doc_doctor`
- **THEN** `openspec_implement` and `openspec_propose` SHALL remain valid built-in preset identifiers
