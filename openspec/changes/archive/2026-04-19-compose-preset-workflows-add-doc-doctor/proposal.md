## Why

当前编排器把每个预设视为独立 workflow，缺少“复用已有预设并组合成新预设”的能力，导致新增流程只能复制粘贴节点配置。现在需要在不破坏现有运行语义的前提下，支持组合式预设，并落地一个 `doc_doctor` 预设把 `doc_reviewer_loop` 与文档修复角色串起来。

## What Changes

- 新增预设组合能力：允许新预设导入已有预设 workflow，并在组合层覆盖节点连线与映射。
- 新增 `doc_doctor` 内置预设：复用 `doc_reviewer_loop` 的 review 自循环阶段；每轮 review 阶段先自循环直至 `pass=true` 才结束，再由程序根据“本轮是否出现过 `pass=false`”做阶段后分流：无失败直接 `END`，出现失败则进入 `doc_fix` 并回到 `doc_reviwer` 复检。
- 新增程序化分流能力：节点可声明 `success_next_node_from`，在 `pass=true` 时由运行时从指定路径读取下一跳，避免通过提示词节点做二次判定。
- 明确阶段后条件分流：`review pass=true && 未记录失败 -> END`；`review pass=true && 已记录失败 -> doc_fix -> doc_reviwer`。
- 约束 `doc_fix` 为纯执行节点：不参与 `pass` 控制判断，采用 `parse_output_json=false`，执行成功后固定回到 `doc_reviwer` 复检。
- 明确 `doc_fix` 入参：仅接收“原始任务意图 + 全历史评审”，不单独传递“本轮新增问题”。
- 明确组合边界：`imports` 仅导入 `workflow.nodes`；被导入 preset 的 `run`、`executor`、`context` 等非 workflow 字段一律不继承、不合并，`doc_doctor` 需本地声明 `context.defaults.user_instruction`。
- 更新 CLI 预设清单、README 示例与测试断言，覆盖新预设与组合语义。

## Capabilities

### New Capabilities
- `preset-workflow-composition`: 允许内置预设在配置层组合并复用已有预设 workflow，同时支持受控节点覆盖。
- `doc-doctor-preset`: 提供 `doc_doctor` 分阶段修复预设，每轮先完成 review 阶段，再按“该轮是否检出问题”决定 `END` 或 `doc_fix -> doc_reviwer` 复检闭环。

### Modified Capabilities
- `preset-enum-resolution`: 内置预设集合新增 `doc_doctor` 标识符，并在 unknown-preset 诊断中可见。

## Impact

- Affected code:
  - `scripts/_codex_orchestrator/config_compiler.py`（组合 DSL 解析与编译、`success_next_node_from` 编译）
  - `scripts/_codex_orchestrator/runtime.py`（`pass=true` 场景的程序化下一跳决策）
  - `scripts/_codex_orchestrator/paths.py`（可用预设枚举）
  - `scripts/codex_automation_loops.py`（主流程配置加载路径不变，接入新配置能力）
  - `presets/`（新增 `doc_doctor.yaml`，复用 prompt role 文件）
- Affected tests:
  - `tests/codex_orchestrator_cases_config.py`
  - `tests/codex_orchestrator_cases_presets_cli.py`
  - 需要新增组合预设与 `doc_doctor` wiring 回归测试
- Affected docs:
  - `README.md`（组合预设 DSL、`doc_doctor` 用法）
