## Context

当前编排器对 `parse_output_json=true` 节点仅抽取最后一个非空行并解析 JSON，解析后的对象被直接写入 `outputs.<node_id>`。这导致两类需求冲突：
- 业务方希望保留完整结论文本供下游节点复用；
- 编排层仅需要最小控制信号（尤其 `pass`）进行路由。

现有数据形态把“结论内容”和“控制信号”耦合在一个 JSON 中，迫使提示词要求在 JSON 里重复输出结论，增加噪音并降低下游处理清晰度。

## Goals / Non-Goals

**Goals:**
- 将节点输出拆分为两个稳定字段：`result`（结论文本）与 `control`（末行控制 JSON）。
- 保留并强化“最后一个非空行必须是严格 JSON object”的控制契约。
- 让路由判断仅依赖 `control.pass`，与结论文本解耦。
- 让下游可通过 `outputs.<node_id>.result` 和 `outputs.<node_id>.control` 独立消费。
- 为历史收集、状态持久化、文档与 preset 提供一致语义。

**Non-Goals:**
- 不改变 `parse_output_json=false` 节点的输出行为。
- 不引入新的节点级路由语法（仍使用 `on_success/on_failure`）。
- 不增加对末行 JSON 之外结构化控制块的解析能力。
- 不在本次变更中引入自动迁移工具（仅提供文档化迁移指引）。

## Decisions

1. 输出契约采用对象封装而非并列根键。
- 规则：当 `parse_output_json=true` 时，`outputs.<node_id>` SHALL 为对象，包含：
  - `result`：去除末行控制 JSON 后的完整文本（可为空字符串）
  - `control`：末行 JSON object（必须含 boolean `pass`）
- 理由：保持 `outputs.<node_id>` 单节点命名空间，便于后续拓展元数据。
- 备选方案：把 `outputs.<node_id>_result` / `_control` 平铺到根层。
  - 放弃原因：命名污染，且破坏现有 `outputs.<node_id>` 访问直觉。

2. 路由语义固定为 `control.pass`。
- 规则：当 `parse_output_json=true` 时，`resolve_next_node` 的 `pass_flag` 来源必须是 `outputs.<node_id>.control.pass`。
- 规则：当 `parse_output_json=false` 时，保持现有隐式成功语义（`pass_flag=True`），不读取 `outputs.<node_id>.control`。
- 理由：确保流程控制只依赖控制信号，不依赖结论文本或额外业务字段。
- 备选方案：允许从 `result` 中推断 pass（例如关键字）。
  - 放弃原因：不可测试、易歧义、不可维护。

3. 文本切分规则采用“末行控制 JSON 前的完整内容”。
- 规则：先定位最后一个非空行并解析为 JSON；再将该行之前的原始内容作为 `result`。
- 规则：`result` 不做 `rstrip`/trim 规整，完整保留控制行之前的原始文本。
- 理由：最小规则，和当前“末行控制”契约一致。
- 备选方案：要求显式分隔符（如 `---CONTROL---`）。
  - 放弃原因：增加提示词复杂度并引入额外失败模式。

4. `parse_output_json=false` 维持现状。
- 规则：该分支仍输出纯文本字符串，并默认 `pass_flag=True`。
- 理由：避免无关节点被迫迁移，降低改动面。

5. 兼容策略采用“显式 BREAKING + 文档迁移”。
- 规则：文档明确旧配置中将 `outputs.<node_id>` 当控制 JSON 使用的路径需要迁移到 `outputs.<node_id>.control`。
- 规则：文档明确 `collect_history_to` 的历史条目在 `parse_output_json=true` 时将从“原控制对象”升级为 `{result, control}` 封装对象，并提供旧/新示例。
- 规则：内置 preset 与 README 示例全部迁移到新路径。
- 理由：当前项目处于低兼容负担阶段，优先语义清晰。

6. 解析失败语义固定为“步骤报错并终止运行”。
- 规则：当 `parse_output_json=true` 且末行控制 JSON 校验失败（非 JSON、非 object、缺失/非法 `pass`）时，当前步骤直接抛错并终止 workflow run。
- 规则：该失败不进入节点 `on_failure` 路由，`on_failure` 仅用于 `control.pass=false` 的业务失败分支。
- 理由：与现有执行器异常路径一致，避免把“输出格式错误”误当作可路由业务失败。

7. 持久化语义与运行态同构。
- 规则：`runtime_state.json`、`run_summary.json` 与每步 `__parsed.json` 必须与 `runtime_state.outputs.<node_id>` 保持同形态。
- 规则：`parse_output_json=true` 时为 `{result, control}`；`parse_output_json=false` 时为 string。
- 规则：`collect_history_to` 在 `parse_output_json=true` 时总是追加完整封装对象（与 `outputs.<node_id>` 一致）。
- 理由：保证调试回放、状态快照、历史消费与运行态一致，避免仅内存态升级造成语义分叉。

## Risks / Trade-offs

- [Risk] 现有 workflow 的 `route_bindings`/`input_map` 若直接读取 `outputs.<node_id>`，行为会变化 → Mitigation: 在文档和 preset 中给出明确迁移对照，并补充回归测试覆盖典型映射路径。
- [Trade-off] `outputs.<node_id>` 从“控制对象”升级为“封装对象”，下游读取需要多一层路径 → Mitigation: 通过清晰命名（`result/control`）换取长期可维护性。
- [Risk] 文本切分边界处理不一致可能造成 `result` 丢行 → Mitigation: 增加多行、空行、仅 JSON 行等解析测试。

## Migration Plan

1. 代码层：更新输出解析函数，返回 `result/control/pass_flag`；更新运行时 `outputs` 写入形态。
2. 路由层：确保路由判断始终使用 `control.pass`。
3. 配置层：迁移内置 preset 的 `input_map/route_bindings` 到 `outputs.<node_id>.control` 或 `.result`。
4. 文档层：更新 README 输出契约与迁移说明，删除“结论必须在 JSON 重复输出”的描述。
5. 测试层：新增双输出契约测试并更新旧断言。
6. 验证层：运行 orchestrator 测试集，确认 `parse_output_json=false` 分支无回归。

Rollback strategy:
- 若发布后出现兼容问题，可临时回滚到前一版本脚本与 preset；本变更不引入数据迁移脚本，回滚成本仅为代码与配置回退。

## Open Questions

- None.
