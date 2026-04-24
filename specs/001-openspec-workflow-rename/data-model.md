# Data Model: OpenSpec Workflow Rename

## Entity: WorkflowPresetIdentifier

- Description: CLI 与注册表使用的内置预设唯一标识。
- Fields:
  - `id` (str): 预设标识（例如 `openspec_implement`、`openspec_propose`）。
  - `runner` (callable): 对应 native flow 入口函数。
  - `is_builtin` (bool): 是否为内置预设。
- Validation Rules:
  - 必须为非空字符串。
  - 不允许路径分隔符。
  - 不接受 `.yaml` 后缀输入。
  - 必须存在于 `BUILTIN_FLOW_REGISTRY`，否则抛出 unknown preset 错误并附可用列表。
- State Transitions:
  - `raw_cli_value -> normalized_identifier -> registry_lookup_success|failure`

## Entity: WorkflowRegistrationEntry

- Description: `scripts/_codex_orchestrator/native_workflows/registry.py` 中的预设注册条目。
- Fields:
  - `key` (str): 注册键，必须与 CLI 标识一致。
  - `flow_runner` (FlowRunner): `Callable[[dict[str, str], str], dict[str, Any]]`。
- Relationships:
  - `WorkflowPresetIdentifier.id` 一对一映射 `WorkflowRegistrationEntry.key`。
- Validation Rules:
  - 注册键集合必须包含 `openspec_implement`、`openspec_propose`。
  - 列表输出需排序稳定（`sorted(BUILTIN_FLOW_REGISTRY)`）。

## Entity: PromptTemplateAsset

- Description: `presets/prompts/` 下独立维护的提示词模板文件。
- Fields:
  - `asset_path` (str): 相对仓库路径。
  - `preset_prefix` (enum): `openspec_implement` | `openspec_propose`。
  - `consumer_stage_id` (str): 被哪个 stage 消费。
  - `required` (bool): 运行时是否必须存在（是）。
- Relationships:
  - 每个目标 preset 的关键 stage 至少引用一个模板资产。
  - `presets.py` stage prompt 通过 `prompt_file(...)` 指向资产。
- Validation Rules:
  - 命名须匹配前缀规则：`openspec_implement*` 或 `openspec_propose*`。
  - 文件缺失时必须抛出明确运行错误，不可回退到旧内嵌模板。

## Entity: RuntimeArtifactLabel

- Description: `.codex-loop-state/` 内与节点相关的输出键、步骤前缀、元数据标签。
- Fields:
  - `node_id` (str)
  - `outputs_key` (str)
  - `step_prefix` (str)
- Validation Rules:
  - 节点标识改名后，输出键与步骤前缀同步反映新标识。
  - 目录结构保持不变（仍写入 `.codex-loop-state/`）。

## Entity: LegacyPresetMigrationPolicy

- Description: 旧预设名迁移行为约束。
- Fields:
  - `legacy_identifier` (str): `implement_loop` 或 `doc_doctor`。
  - `behavior` (enum): `reject_with_hint`。
  - `hint_targets` (list[str]): 新可用标识列表。
- Validation Rules:
  - 对旧名称调用必须失败并给出可用预设列表。
  - 测试需覆盖至少一个旧名称失败样例。
