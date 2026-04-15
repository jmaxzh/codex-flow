# prompt-file-reference Specification

## Purpose
TBD - created by archiving change support-prompt-file-references. Update Purpose after archive.
## Requirements
### Requirement: Unified prompt template engine
The system MUST use a single template engine (Jinja2) for prompt rendering, including prompt-file includes and `inputs` variable interpolation.

#### Scenario: Strict undefined behavior is enabled
- **WHEN** template rendering resolves `inputs` or other variables
- **THEN** undefined variables SHALL fail rendering instead of silently becoming empty text

#### Scenario: Prompt without include remains valid
- **WHEN** `workflow.nodes[n].prompt` is a non-empty string and does not use include helper
- **THEN** configuration loading and prompt rendering SHALL succeed with the same unified Jinja2 rendering flow

#### Scenario: Include and inputs can be mixed in one prompt
- **WHEN** `workflow.nodes[n].prompt` contains both `{{ prompt_file("./x.md") }}` and `{{ inputs.some_key }}`
- **THEN** rendering SHALL resolve both include content and input variables in one unified rendering flow

#### Scenario: Missing inputs path still fails fast
- **WHEN** `{{ inputs.some_key }}` cannot be resolved from node input context
- **THEN** rendering SHALL fail instead of silently rendering empty text

#### Scenario: Non-string inputs are rendered as JSON text
- **WHEN** `{{ inputs.some_key }}` resolves to a non-string value (for example object, array, number, or boolean)
- **THEN** rendering SHALL inject JSON text instead of Python repr-style text

### Requirement: Prompt file include helper syntax
The system MUST support file include helper calls inside node `prompt` templates using `{{ prompt_file("<relative_path>") }}`.

#### Scenario: Multiple includes are supported
- **WHEN** `workflow.nodes[n].prompt` contains two or more `{{ prompt_file("<relative_path>") }}` expressions
- **THEN** rendering SHALL inject each referenced file content in template order

#### Scenario: Repeated include path is supported
- **WHEN** `workflow.nodes[n].prompt` contains the same `{{ prompt_file("<relative_path>") }}` more than once
- **THEN** each occurrence SHALL be replaced by the referenced file content

#### Scenario: Literal relative path is the recommended ordinary-user style
- **WHEN** documentation and examples describe `prompt_file(...)` usage
- **THEN** they SHALL present literal relative paths as the primary style for ordinary users

#### Scenario: Built-in presets prefer role-only file extraction
- **WHEN** built-in workflow presets use `prompt_file(...)` to organize long prompts
- **THEN** they SHALL prioritize extracting only reusable role text into external files, while keeping node-specific output protocol in YAML `prompt`

### Requirement: Prompt file path resolution and validation
Include paths MUST follow a minimal, config-relative rule set.

#### Scenario: Relative path resolves from config directory
- **WHEN** `{{ prompt_file("<relative_path>") }}` is used
- **THEN** `<relative_path>` SHALL be resolved relative to the current workflow config file directory only

#### Scenario: Absolute path is rejected
- **WHEN** `<relative_path>` is actually an absolute path
- **THEN** rendering SHALL fail with an error identifying the failing node prompt field

#### Scenario: Parent-segment relative path is allowed
- **WHEN** `<relative_path>` contains parent segments such as `..`
- **THEN** resolution SHALL use normal config-directory-relative path resolution and this spec SHALL NOT require dedicated directory-boundary guard logic

#### Scenario: Resolution is independent of current working directory
- **WHEN** the same workflow config is executed from different current working directories
- **THEN** include resolution SHALL target the same files under the config directory and load successfully

#### Scenario: Resolution is independent of runtime project_root
- **WHEN** `run.project_root` differs from workflow config location
- **THEN** include resolution SHALL still use the workflow config file directory and produce consistent results

### Requirement: Include loading and helper errors
The system MUST fail fast with field-level errors for invalid helper usage or unreadable files.

#### Scenario: Include helper call is invalid
- **WHEN** `prompt` contains invalid include helper usage (for example missing argument, empty string path, non-string argument)
- **THEN** rendering SHALL fail with an error identifying the failing node prompt field

#### Scenario: Included file cannot be loaded
- **WHEN** an include path points to a missing or unreadable file
- **THEN** rendering SHALL fail with an error identifying the failing node prompt field and failure reason, and SHOULD include the include path when available

#### Scenario: Prompt field type is invalid
- **WHEN** `workflow.nodes[n].prompt` is missing or not a non-empty string
- **THEN** prompt preparation or rendering SHALL fail before node execution with an error identifying `workflow.nodes[n].prompt`

#### Scenario: Path-related errors are actionable but minimal
- **WHEN** include loading fails due to path validation or file loading
- **THEN** error message SHALL include failing node prompt location and failure reason, SHOULD include include path when available, and MAY include a brief fix hint

#### Scenario: Prompt render errors keep stable field location
- **WHEN** template rendering stage fails for syntax errors, undefined variables, `prompt_file` helper validation, or include file loading
- **THEN** error output SHALL identify the failing node prompt field (for example by `node_id` or `workflow.nodes[n].prompt`) without requiring a fixed formatting contract

### Requirement: Simplicity-first implementation boundary
This capability MUST prioritize ordinary-user workflows and MUST NOT require complexity for extreme or compatibility scenarios.

#### Scenario: Legacy syntax is not specially handled
- **WHEN** `workflow.nodes[n].prompt` uses unsupported legacy syntax such as `{{prompt_file:<relative_path>}}`
- **THEN** the system MAY fail with normal template-rendering errors and SHALL NOT require dedicated compatibility logic

#### Scenario: Computed include argument is out of supported scope
- **WHEN** `prompt_file(...)` receives a computed or non-literal argument form
- **THEN** this spec SHALL NOT require compatibility guarantees for it, and runtime behavior MAY follow normal template/helper evaluation plus parameter validation

#### Scenario: Legacy syntax migration guidance is documented
- **WHEN** documentation explains unsupported legacy syntax such as `{{prompt_file:<relative_path>}}`
- **THEN** it SHALL provide a minimal manual migration note to `{{ prompt_file("<relative_path>") }}` without requiring runtime compatibility logic

#### Scenario: No recursive include detection contract
- **WHEN** included file text contains template-like content
- **THEN** this spec SHALL NOT require recursive include scanning or dedicated recursive-include errors

#### Scenario: Included file text is not rendered a second time
- **WHEN** `prompt_file(...)` loads file content that itself contains template expressions
- **THEN** this spec SHALL NOT require second-pass template rendering of the loaded content

#### Scenario: Unsupported include-template behavior is explicitly documented
- **WHEN** included file content contains template expressions such as `{{ ... }}`
- **THEN** documentation SHALL explicitly state these expressions are treated as plain text and are not a pending feature question

