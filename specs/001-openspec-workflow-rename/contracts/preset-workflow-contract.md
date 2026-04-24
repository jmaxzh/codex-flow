# Contract: OpenSpec Preset Workflow Identifier & Prompt Assets

## Scope

本契约定义 `openspec_implement` 与 `openspec_propose` 的入口标识、注册映射、模板资产加载与旧名称迁移行为。

## CLI Contract

- Command: `python3 scripts/codex_automation_loops.py --preset <identifier>`
- Accepted identifiers (for this feature):
  - `openspec_implement`
  - `openspec_propose`
- Rejected legacy identifiers:
  - `implement_loop`
  - `doc_doctor`
- Error behavior:
  - 对未知/旧名称抛出 `RuntimeError("Unknown preset identifier: '<id>'. Available built-in presets: ...")`
  - 可用列表中必须包含新标识。

## Registry Contract

- `BUILTIN_FLOW_REGISTRY` 必须满足：
  - key 与 CLI 标识一致。
  - `list_builtin_preset_identifiers()` 返回排序稳定列表。
- 目标映射：
  - `openspec_implement -> run_openspec_implement_flow`（命名示例）
  - `openspec_propose -> run_openspec_propose_flow`（命名示例）

## Prompt Template Asset Contract

- 目标预设提示词模板必须位于 `presets/prompts/` 下的独立文件。
- 模板命名必须遵循前缀：
  - `openspec_implement*`
  - `openspec_propose*`
- `presets.py` 不得包含这两个目标预设的完整模板正文。
- 运行时通过 `prompt_file(...)` 加载模板；文件缺失时必须失败并给出明确错误。

## Runtime Artifact Contract

- `.codex-loop-state/` 路径保持不变。
- 与节点标识耦合的输出键/步骤前缀需反映新命名。
- 若目录结构无变化，在变更说明中声明“无运行产物格式变化（仅标识名变化）”。

## Test Evidence Contract

必须覆盖以下行为：

1. 注册表包含新标识且排序稳定。
2. CLI 能解析新标识并拒绝旧标识。
3. 目标预设模板通过文件资产加载。
4. 模板缺失路径触发明确失败。
5. runtime 输出键/路由行为在重命名后仍与原语义一致。

## Documentation Contract

- `docs/specs/` 中与目标预设相关条目需同步更新到新标识。
- 文档中不得继续将旧名称作为主入口；如出现，仅能用于迁移说明。
