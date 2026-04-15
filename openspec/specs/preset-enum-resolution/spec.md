# preset-enum-resolution Specification

## Purpose
TBD - created by archiving change fix-preset-enum-resolution. Update Purpose after archive.
## Requirements
### Requirement: Preset identifier semantics
The CLI `--preset` parameter MUST be treated as a preset identifier, not a file path.

#### Scenario: Identifier value is accepted
- **WHEN** a user passes `--preset implement_loop`
- **THEN** the system SHALL interpret `implement_loop` as a preset identifier
- **THEN** the system SHALL resolve it to the built-in preset config file `implement_loop.yaml`

#### Scenario: Path-like value is rejected
- **WHEN** a user passes `--preset presets/implement_loop.yaml` or any value containing path separators
- **THEN** argument validation SHALL fail before workflow execution
- **THEN** the error message SHALL state that `--preset` expects a preset identifier

#### Scenario: Empty or whitespace-only identifier is rejected
- **WHEN** a user passes an empty or whitespace-only value to `--preset`
- **THEN** argument validation SHALL fail before workflow execution
- **THEN** the error message SHALL state that `--preset` requires a non-empty preset identifier

#### Scenario: Identifier with `.yaml` suffix is rejected
- **WHEN** a user passes `--preset implement_loop.yaml` without path separators
- **THEN** argument validation SHALL fail before workflow execution
- **THEN** the error message SHALL state that `--preset` accepts extensionless preset identifiers
- **THEN** the error message SHALL include a migration hint to use `implement_loop` instead of `implement_loop.yaml`

### Requirement: CWD-independent preset resolution
Preset identifier lookup MUST be deterministic and independent of the command invocation directory.

#### Scenario: Same preset from different cwd resolves identically
- **WHEN** the same command with `--preset implement_loop` is run from two different current working directories
- **THEN** both invocations SHALL resolve to the same built-in preset file under repository `presets/`

#### Scenario: Lookup base is repository preset directory
- **WHEN** the orchestrator resolves a valid preset identifier
- **THEN** it SHALL use the project’s built-in preset directory as the lookup base
- **THEN** it SHALL NOT depend on `Path.cwd()` for preset file location

### Requirement: Actionable unknown-preset diagnostics
Unknown preset identifiers MUST produce actionable errors.

#### Scenario: Unknown preset is reported with available options
- **WHEN** a user passes an identifier that does not exist in the built-in preset directory
- **THEN** execution SHALL fail with a clear unknown-preset error
- **THEN** the error MUST include available preset identifiers to guide correction

