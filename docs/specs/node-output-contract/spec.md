# node-output-contract Specification

## Purpose
TBD - created by archiving change split-node-result-and-control-output. Update Purpose after archive.
## Requirements
### Requirement: Dual outputs for JSON-parsed nodes
For any node-stage with `parse_output_json=true`, the system MUST persist output as a two-part object with separate `result` and `control` fields.

#### Scenario: Output object contains both result and control
- **WHEN** a node-stage with `parse_output_json=true` finishes execution and its raw model output has a valid control JSON object on the last non-empty line
- **THEN** `outputs.<node_id>` SHALL be an object
- **THEN** `outputs.<node_id>.result` SHALL contain the complete textual output before the control line
- **THEN** `outputs.<node_id>.control` SHALL equal the parsed JSON object from the last non-empty line

#### Scenario: Result can be empty while control remains valid
- **WHEN** the raw output contains no characters before a valid JSON control line (that control line is the entire output)
- **THEN** `outputs.<node_id>.result` SHALL be an empty string
- **THEN** `outputs.<node_id>.control` SHALL still be the parsed JSON object

### Requirement: Last non-empty line remains strict control JSON
The system MUST keep the strict last-line JSON contract for control semantics.

#### Scenario: Last non-empty line is not JSON
- **WHEN** the last non-empty line is not valid JSON text
- **THEN** node output parsing SHALL fail before route selection
- **THEN** the workflow run SHALL terminate with error for this step and SHALL NOT enter pass-based branch routing

#### Scenario: Last non-empty line JSON is not object
- **WHEN** the last non-empty line parses as valid JSON but is not an object
- **THEN** node output parsing SHALL fail before route selection
- **THEN** the workflow run SHALL terminate with error for this step and SHALL NOT enter pass-based branch routing

#### Scenario: Control object misses pass
- **WHEN** the last non-empty line parses to an object that lacks `pass`
- **THEN** node output parsing SHALL fail before route selection
- **THEN** the workflow run SHALL terminate with error for this step and SHALL NOT enter pass-based branch routing

#### Scenario: Control pass is not boolean
- **WHEN** control object contains `pass` but its value is not boolean
- **THEN** node output parsing SHALL fail before route selection
- **THEN** the workflow run SHALL terminate with error for this step and SHALL NOT enter pass-based branch routing

### Requirement: Route control is derived only from control.pass
For node-stages with `parse_output_json=true`, route decisions MUST be based on `outputs.<node_id>.control.pass` and MUST NOT require conclusion duplication in control JSON.

#### Scenario: Success route uses control pass true
- **WHEN** `parse_output_json=true` and `outputs.<node_id>.control.pass` is `true`
- **THEN** orchestrator flow logic SHALL route to the stage's success branch

#### Scenario: Failure route uses control pass false
- **WHEN** `parse_output_json=true` and `outputs.<node_id>.control.pass` is `false`
- **THEN** orchestrator flow logic SHALL route to the stage's failure branch

#### Scenario: Conclusion does not need duplication inside control JSON
- **WHEN** node-stage conclusion is fully expressed in `outputs.<node_id>.result`
- **THEN** orchestrator SHALL NOT require duplicated conclusion fields in `outputs.<node_id>.control`

### Requirement: Mapping and history can consume split outputs independently
Downstream input mapping and history collection MUST support independent consumption of `result` and `control` from each node output object.

#### Scenario: Input mapping can reference control path
- **WHEN** a downstream stage input source uses `outputs.<node_id>.control`
- **THEN** mapping resolution SHALL succeed and inject the control object to target input

#### Scenario: Input mapping can reference result path
- **WHEN** a downstream stage input source uses `outputs.<node_id>.result`
- **THEN** input resolution SHALL succeed and inject textual conclusion into prompt inputs

#### Scenario: History stores full split output object
- **WHEN** a stage with history collection and `parse_output_json=true` is executed
- **THEN** the collected history entry SHALL append the full `outputs.<node_id>` object including both `result` and `control`

#### Scenario: History for plain-text stages remains string
- **WHEN** a stage with history collection and `parse_output_json=false` is executed
- **THEN** the collected history entry SHALL append the same plain-text string value as `outputs.<node_id>`

### Requirement: Result text is preserved without trailing normalization
For `parse_output_json=true`, `result` MUST keep the exact text before the control line and MUST NOT apply `rstrip`/trim normalization.

#### Scenario: Result keeps original trailing whitespace before control line
- **WHEN** raw model output contains trailing spaces or newline characters in the content block before the last non-empty control JSON line
- **THEN** `outputs.<node_id>.result` SHALL preserve that content block as-is, excluding only the control line itself

#### Scenario: Whitespace-only prefix before control line is preserved
- **WHEN** raw model output contains only whitespace or blank lines before the last non-empty control JSON line
- **THEN** `outputs.<node_id>.result` SHALL preserve that whitespace prefix exactly as-is and SHALL NOT be normalized to an empty string

### Requirement: Persisted artifacts use the same node output shape as runtime outputs
The persisted artifacts MUST use the same node output shape as `runtime_state.outputs.<node_id>`.

#### Scenario: JSON-parsed stage persists split object shape
- **WHEN** `parse_output_json=true` and output parsing succeeds
- **THEN** `runtime_state.json` SHALL store `outputs.<node_id>` as `{result, control}`
- **THEN** the corresponding step `__parsed.json` SHALL persist the same `{result, control}` object shape
- **THEN** `run_summary.json` SHALL persist `outputs.<node_id>` under `outputs` with the same `{result, control}` object shape

#### Scenario: Plain-text stage persists string shape
- **WHEN** `parse_output_json=false`
- **THEN** `runtime_state.json` SHALL store `outputs.<node_id>` as a string
- **THEN** the corresponding step `__parsed.json` SHALL persist the same string value
- **THEN** `run_summary.json` SHALL persist `outputs.<node_id>` under `outputs` with the same string value

### Requirement: Plain-text node output behavior remains unchanged
Node-stages with `parse_output_json=false` MUST keep current plain-text output behavior.

#### Scenario: Plain-text stages still store string output
- **WHEN** `parse_output_json=false`
- **THEN** `outputs.<node_id>` SHALL remain a string value
- **THEN** route selection SHALL continue using implicit success (`pass=true`) behavior

