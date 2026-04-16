## Why

当前节点在 `parse_output_json=true` 时只解析最后一个非空行并将其作为节点输出，导致模型给出的完整结论文本无法被结构化复用。随着工作流需要同时消费“业务结论”和“流程控制信号”，必须将两者拆分为可独立映射的节点输出。

## What Changes

- 为启用 JSON 解析的节点引入“双输出”契约：
- `result`：节点完整结论文本（末行控制 JSON 之前的完整输出内容）
- `control`：最后一个非空行的严格 JSON object（用于流程控制）
- 保持“最后一个非空行必须是严格 JSON object”的约束，并继续要求 `control.pass` 为 boolean。
- 路由决策统一基于 `control.pass`（不再依赖结论文本中的重复语义字段）。
- 更新运行时输出与映射约定：`outputs.<node_id>` 从单值升级为对象，并显式暴露 `outputs.<node_id>.result` 与 `outputs.<node_id>.control` 两个可独立引用路径。
- 更新内置 preset 与文档示例，移除“在 JSON 中重复结论文本”的要求，改为“正文给结论，末行 JSON 仅给控制字段”。
- **BREAKING**：旧配置若将 `outputs.<node_id>` 直接当作“控制 JSON 对象”使用，需要迁移到 `outputs.<node_id>.control`。
- **BREAKING**：`collect_history_to` 在 `parse_output_json=true` 时的历史条目形态从旧控制对象升级为 `{result, control}`，依赖历史结构的下游需同步迁移读取路径。

## Capabilities

### New Capabilities
- `node-output-contract`: 定义节点完整输出与末行控制 JSON 的分离契约、运行时数据形态、路由与映射语义。

### Modified Capabilities
- None.

## Impact

- Affected code: `scripts/codex_automation_loops.py`（输出解析、路由判断、运行时输出写入、状态持久化）
- Affected presets/docs: `presets/*.yaml`, `README.md`
- Affected tests: `tests/test_codex_orchestrator.py`
- Runtime impact: 下游节点可分别消费 `result` 与 `control`；流程控制继续由末行 JSON 驱动，避免在 JSON 中重复业务结论文本。
