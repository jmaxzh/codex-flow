## Context

现有编排器配置模型只支持在单个 preset 文件中声明完整 `workflow.start + workflow.nodes`。这导致以下问题：

- 复用成本高：已有预设（如文档 review 循环）无法被新预设直接复用，只能复制节点定义。
- 维护风险高：复制后若上游 preset 更新，派生流程无法自动继承修复。
- 当前新增需求明确：需要基于 `doc_reviewer_loop` 形成 `doc_doctor`。每轮必须先让 review 阶段自循环并完整结束（`pass=true`），然后由程序根据“该轮 review 阶段是否出现过 `pass=false`”决定分支：未出现失败直接结束，出现失败则执行 `doc_fix` 并回到 review 复检。

约束：

- 保持现有 runtime 执行语义不变（节点执行顺序、输出契约、历史收集行为保持一致）。
- `doc_fix` 不使用 `pass` 控制流判断。
- `doc_fix` 输入仅为“原始任务意图 + 全历史评审”。

## Goals / Non-Goals

**Goals:**

- 提供配置层组合能力，使新 preset 可以导入并复用已有 preset workflow。
- 提供导入节点的受控覆盖能力（至少覆盖路由边）以支持连接新节点。
- 落地内置 `doc_doctor` preset，串联 `doc_reviewer_loop` 与 `doc_fix_role`。
- 保证 `doc_fix` 入参严格来自：
  - `context.defaults.user_instruction`
  - `context.runtime.doc_review_history`

**Non-Goals:**

- 不引入新的 runtime 执行引擎或并行调度机制。
- 不改变 `parse_output_json` 与 `outputs.<node_id>` 的既有契约。
- 不在本次引入复杂继承链（例如远程 preset、跨仓库 preset）。

## Decisions

### 1) 新增 workflow 组合 DSL：`imports + node_overrides + nodes`，并扩展节点成功分流字段

决策：在 `workflow` 下新增两个可选字段：

- `imports`: `[{ preset: "<preset-id>" }]`（条目对象仅允许 `preset` 字段）
- `node_overrides`: `{ "<node_id>": { on_success?, on_failure?, route_bindings?, success_next_node_from? } }`（覆盖对象仅允许这四个键）

并保留现有 `start` 与 `nodes` 字段。

同时在节点 DSL 新增可选字段：

- `success_next_node_from`: `<dotted-source-path>`
  - 仅在节点执行结果 `pass=true` 时生效
  - 运行时从该路径读取字符串作为下一跳节点 id
  - 路径不存在时回退到原 `on_success`

组合约束：

- `workflow.start` 在组合 preset 中仍为必填，且必须显式声明（不从 imports 隐式继承）。
- 组合 preset 的本地 `workflow.nodes` 可省略或为空数组；编译器按“仅导入节点”处理。
- `workflow.node_overrides` 仅允许作用于已导入节点，不允许覆盖本地节点（本地节点应直接在 `workflow.nodes` 中修改）。
- `imports` 仅导入被导入 preset 的 `workflow.nodes`；`run`、`executor`、`context` 等非 workflow 字段不继承、不合并。
- `imports[]` 条目若包含除 `preset` 之外的键，编译期报错（不静默忽略）。
- `workflow.node_overrides.<node_id>` 若包含除 `on_success`/`on_failure`/`route_bindings`/`success_next_node_from` 之外的键，编译期报错（不静默忽略）。
- `workflow` 根级若出现非 `start`/`imports`/`node_overrides`/`nodes` 的未知键（如 `workflow.import`、`workflow.node_override`），编译期报错（不静默忽略）。

编译顺序：

1. 先按 `imports` 顺序加载被导入 preset 的 workflow.nodes（不导入 run/executor/context 等非 workflow 字段）
2. 应用 `node_overrides` 到已导入节点
3. 追加当前文件本地 `nodes`（若省略则视为空数组）
4. 统一执行 node id 唯一性、transition 有效性、`workflow.start` 指向有效性与“组合后节点非空”校验

`node_overrides` 语义：

- `on_success` / `on_failure`：直接替换目标节点对应字段。
- `route_bindings`：按路由维度覆盖；若提供 `success` 或 `failure`，则替换该路由的整张映射表，未提供的路由保持被导入节点原值。

理由：

- 满足“组合已有预设”能力，同时保持对现有 DSL 的兼容。
- `node_overrides` 最小化覆盖范围，降低误改 prompt/input_map 的风险。
- 显式 `workflow.start` + 组合后统一校验可避免“隐式入口继承”导致的实现分叉。
- `success_next_node_from` 让阶段后分流可由程序读取状态决定，不再依赖额外提示词节点二次判断。

备选方案：

- 方案A：仅允许复制模板、不支持 import。拒绝，无法解决复用问题。
- 方案B：允许任意字段 override（包括 prompt/input_map/parse_output_json）。暂不采用，灵活但风险更高。

### 2) 限制导入范围为“内置 preset 标识符”，且仅允许单层导入

决策：`imports[].preset` 复用现有 `--preset` 的 identifier 解析逻辑，仅允许仓库 `presets/` 下的内置 preset；导入展开仅做一层，不递归加载被导入 preset 的 `workflow.imports`。

理由：

- 与已有 `preset-enum-resolution` 一致，避免路径依赖和执行目录差异。
- 无需引入额外安全与可移植性规则。
- 通过“单层导入”直接规避循环导入与递归加载复杂度，符合本次非目标范围。

备选方案：

- 支持路径导入（本地文件路径）。拒绝，与既有 preset 标识符语义冲突。

### 3) `doc_doctor` 采用“review 阶段结束后分流：END 或 fix -> review”闭环流程

决策：

- 导入 `doc_reviewer_loop` 并保持其自循环失败路由不变（`doc_reviwer.on_failure = doc_reviwer`），确保每轮 review 阶段先在内部收敛，直到 `pass=true` 才结束该阶段。
- `doc_doctor.workflow.start = doc_reviwer`，首次执行必须进入 review 阶段。
- 通过程序态状态完成阶段后分流，不引入 `doc_fix_decision` 提示词节点：
  - 在 `doc_reviwer` 的 failure 路由绑定中写入阶段标记：
    - `context.runtime.doc_review_next_node = context.defaults.doc_review_fix_node`
  - 在 `doc_reviwer` 上配置：
    - `on_success: END`
    - `success_next_node_from: context.runtime.doc_review_next_node`
  - 语义：
    - 当前轮 review 阶段若从未出现 `pass=false`，该路径不存在，`pass=true` 时回退走 `on_success=END`
    - 当前轮 review 阶段若出现过 `pass=false`，`pass=true` 时程序从路径读取 `doc_fix`，进入修复
- 新增 `doc_fix` 节点：
  - `parse_output_json: false`
  - `on_success: doc_reviwer`
  - `on_failure: END`（配置层转移字段完整性约束；不用于捕获执行异常）
  - `input_map` 精确且仅包含：
    - `user_instruction: context.defaults.user_instruction`
    - `doc_review_history: context.runtime.doc_review_history`
  - `prompt` 必须显式消费 `inputs.user_instruction` 与 `inputs.doc_review_history`（可通过模板直接引用或包裹 `prompt_file(...)` 的模板拼接引用）；该约束通过 preset wiring 测试断言，不引入通用编译期模板静态分析
- `doc_fix` 成功后通过 route binding 重置阶段标记：
  - `context.runtime.doc_review_next_node = context.defaults.doc_review_end_node`
- `doc_fix` 不配置 `collect_history_to`（尤其禁止写入 `context.runtime.doc_review_history`），避免污染评审历史。
- 在 `doc_doctor` 本地声明 `context.defaults.user_instruction`，并声明程序分流常量：
  - `context.defaults.doc_review_fix_node = "doc_fix"`
  - `context.defaults.doc_review_end_node = "END"`
  并本地满足既有顶层必填契约（至少包含 `run`）；`imports` 不继承被导入 preset 的 `run/executor/context`。
- 保持导入节点 `doc_reviwer.collect_history_to = context.runtime.doc_review_history` 不变，确保 `doc_fix` 始终读取全历史评审。

理由：

- `doc_fix` 不需要 pass 控制：`parse_output_json=false` 下执行成功即走 `on_success=doc_reviwer`，进入复检阶段。
- 通过程序态阶段标记 + `success_next_node_from`，可直接表达“有失败则修复、无失败则结束”，不依赖提示词二次判定。
- `parse_output_json=false` 节点执行异常会直接终止 run，不会走 `on_failure`；因此 `doc_fix.on_failure=END` 仅作为配置契约声明，不承诺运行时异常兜底。
- review 自循环阶段会把“每轮新增问题”持续追加到全历史，`doc_fix` 与后续复检都只读同一份全历史即可。
- 本地声明 `context.defaults.user_instruction` 可保证 `--preset doc_doctor` 在未传 `--context user_instruction` 时仍可运行。

备选方案：

- 给 `doc_fix` 增加 JSON 控制输出并基于 `pass` 分流。拒绝，不符合需求且增加提示词约束复杂度。

### 4) 最小化扩展 runtime 路由决策，不改变执行引擎模型

决策：在保持执行循环模型不变的前提下，新增一段成功分支动态下一跳解析逻辑（仅 `pass=true` 路径可选覆盖）；其余 runtime 行为（执行、输出、历史、落盘）保持不变。

理由：

- 该需求核心是“配置复用与分流控制”，无需引入新的执行引擎。
- 动态下一跳仅是对既有 `on_success` 的受控覆盖，回归面小。

## Risks / Trade-offs

- [Risk] 导入多个 preset 可能出现 node id 冲突 → Mitigation: 编译期直接报错并定位冲突 node id。
- [Risk] review/fix 闭环可能长期不收敛，导致无法达成最终 `END` → Mitigation: 复用现有 `run.max_steps` 上限并在文档中明确“每轮 review 阶段结束后，程序按是否出现过 `pass=false` 决定 `END` 或进入 `doc_fix` 再复检”。
- [Risk] 用户误以为 `doc_fix` 会读取“单轮新增问题”字段 → Mitigation: 在 `doc_doctor` preset 与 README 中明确入参仅两项（任务意图、全历史评审）。
- [Trade-off] 首版 `node_overrides` 只支持有限字段，灵活性受限 → Mitigation: 后续按真实需求再扩展覆盖字段。

## Migration Plan

1. 新增组合 DSL 的解析与校验，保持旧 preset 无改动可继续运行。
2. 新增 `doc_doctor.yaml`，并将其加入内置 preset 列表可见范围。
3. 更新测试与 README，确保 `--preset doc_doctor` 可发现、可执行。
4. 回滚策略：如出现不兼容，可回退组合 DSL 解析逻辑与 `doc_doctor.yaml`，原有 preset 行为不受影响。
