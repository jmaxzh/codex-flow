## ADDED Requirements

### Requirement: New built-in presets are discoverable through identifier diagnostics
When a new built-in preset is added, unknown-preset diagnostics MUST include that identifier in the available preset list.

#### Scenario: unknown preset diagnostics list includes doc_doctor
- **WHEN** a user passes an unknown preset identifier after `doc_doctor` is added
- **THEN** the unknown-preset error SHALL include `doc_doctor` in the available built-in preset identifiers list

### Requirement: New built-in preset identifiers resolve through the same deterministic lookup
New built-in presets MUST resolve via the same repository `presets/` identifier lookup semantics.

#### Scenario: doc_doctor resolves deterministically from different cwd
- **WHEN** `resolve_preset_path("doc_doctor")` is evaluated from different current working directories
- **THEN** both resolutions SHALL point to the same built-in preset file `presets/doc_doctor.yaml`
- **THEN** resolution SHALL NOT depend on invocation `cwd`
