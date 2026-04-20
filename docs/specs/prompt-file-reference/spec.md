# prompt-file-reference Specification

## Purpose
TBD - created by archiving change support-prompt-file-references. Update Purpose after archive.
## Requirements
### Requirement: Unified prompt template engine
The system MUST use a single template engine (Jinja2) for prompt rendering, including prompt-file includes and runtime `inputs` interpolation in native preset flows.

#### Scenario: Strict undefined behavior is enabled
- **WHEN** template rendering resolves `inputs` or other variables
- **THEN** undefined variables SHALL fail rendering instead of silently becoming empty text

#### Scenario: Prompt without include remains valid
- **WHEN** a stage prompt is a non-empty string and does not use include helper
- **THEN** prompt rendering SHALL succeed with the same unified Jinja2 rendering flow

#### Scenario: Include and inputs can be mixed in one prompt
- **WHEN** a stage prompt contains both `{{ prompt_file("./x.md") }}` and `{{ inputs.some_key }}`
- **THEN** rendering SHALL resolve both include content and input variables in one unified rendering flow

#### Scenario: Missing inputs path still fails fast
- **WHEN** `{{ inputs.some_key }}` cannot be resolved from stage input context
- **THEN** rendering SHALL fail instead of silently rendering empty text

#### Scenario: Non-string inputs are rendered as JSON text
- **WHEN** `{{ inputs.some_key }}` resolves to a non-string value (for example object, array, number, or boolean)
- **THEN** rendering SHALL inject JSON text instead of Python repr-style text

### Requirement: Prompt file include helper syntax
The system MUST support file include helper calls inside stage prompts using `{{ prompt_file("<relative_path>") }}`.

#### Scenario: Multiple includes are supported
- **WHEN** a stage prompt contains two or more `{{ prompt_file("<relative_path>") }}` expressions
- **THEN** rendering SHALL inject each referenced file content in template order

#### Scenario: Repeated include path is supported
- **WHEN** a stage prompt contains the same `{{ prompt_file("<relative_path>") }}` more than once
- **THEN** each occurrence SHALL be replaced by the referenced file content

### Requirement: Prompt file path resolution and validation
Include paths MUST follow a minimal, preset-relative rule set in native flow execution.

#### Scenario: Relative path resolves from preset prompt base directory
- **WHEN** `{{ prompt_file("<relative_path>") }}` is used
- **THEN** `<relative_path>` SHALL be resolved relative to the preset-defined prompt base directory
- **THEN** for this migration the preset-defined prompt base directory SHALL remain under `presets/prompts/` (including `presets/prompts/shared/`)

#### Scenario: Absolute path is rejected
- **WHEN** `<relative_path>` is actually an absolute path
- **THEN** rendering SHALL fail with an error identifying the failing stage prompt field

#### Scenario: Resolution is independent of current working directory
- **WHEN** the same preset is executed from different current working directories
- **THEN** include resolution SHALL target the same prompt files under the preset prompt base directory and load successfully

#### Scenario: Resolution is independent of runtime project_root
- **WHEN** runtime `project_root` differs from orchestrator repository location
- **THEN** include resolution SHALL still use preset prompt base directory and produce consistent results

### Requirement: Include loading and helper errors
The system MUST fail fast with field-level errors for invalid helper usage or unreadable files.

#### Scenario: Include helper call is invalid
- **WHEN** a prompt contains invalid include helper usage (for example missing argument, empty string path, non-string argument)
- **THEN** rendering SHALL fail with an error identifying the failing stage prompt field

#### Scenario: Included file cannot be loaded
- **WHEN** an include path points to a missing or unreadable file
- **THEN** rendering SHALL fail with an error identifying the failing stage prompt field and failure reason, and SHOULD include the include path when available

#### Scenario: Prompt field type is invalid
- **WHEN** a stage prompt is missing or not a non-empty string
- **THEN** prompt preparation or rendering SHALL fail before stage execution with an error identifying the prompt field

### Requirement: Simplicity-first implementation boundary
This capability MUST prioritize ordinary-user workflows and MUST NOT require complexity for extreme or compatibility scenarios.

#### Scenario: Legacy syntax is not specially handled
- **WHEN** a prompt uses unsupported legacy syntax such as `{{prompt_file:<relative_path>}}`
- **THEN** the system MAY fail with normal template-rendering errors and SHALL NOT require dedicated compatibility logic

#### Scenario: No recursive include detection contract
- **WHEN** included file text contains template-like content
- **THEN** this spec SHALL NOT require recursive include scanning or dedicated recursive-include errors

