# Research: OpenSpec Workflow Rename

## Decision 1: 旧预设名不做兼容别名，统一拒绝并提示迁移

- Decision: 对 `implement_loop` 与 `doc_doctor` 输入不保留运行时别名，保持为 unknown preset 错误，并通过可用列表引导迁移到 `openspec_implement` 与 `openspec_propose`。
- Rationale: 需求要求入口统一命名，保留别名会导致长期双轨、文档与测试语义分叉，且增加后续清理成本。
- Alternatives considered:
  - 兼容别名到新名称：短期平滑，但违背“统一使用新名称”的目标并提升维护负担。
  - 警告后继续执行：会弱化错误可见性，不利于团队彻底迁移。

## Decision 2: 模板正文从 `presets.py` 外置到 `presets/prompts/` 目标文件

- Decision: `presets.py` 仅保留工作流阶段编排、输入映射、路由绑定；每个目标节点提示词通过 `prompt_file(...)` 引用 `presets/prompts/` 下独立模板。
- Rationale: 满足 FR-001/FR-002，降低 Python 代码内长字符串维护成本，强化模板资产可测试性（存在性/路径/命名）。
- Alternatives considered:
  - 保持内嵌模板：不满足需求。
  - 外置到 `presets/prompts/shared/`：共享目录语义不清，且需求强调目标工作流独立模板资产。

## Decision 3: 新命名规则覆盖“标识 + 资源 + 测试 + 文档”全链路

- Decision: 采用 `openspec_implement*` 与 `openspec_propose*` 前缀规则，覆盖注册键、函数名、节点标识、模板文件名、测试用例描述和文档示例命令。
- Rationale: 统一前缀可直接支持仓库扫描与审计（SC-004），减少遗漏重命名点。
- Alternatives considered:
  - 仅替换 CLI 可见名称：内部符号仍残留旧名，易产生行为漂移。
  - 局部替换（只改 registry）：会在 `.codex-loop-state/` 产物键和测试断言中留下旧痕迹。

## Decision 4: 契约文档按“最小必要修改”策略更新

- Decision: 更新 `docs/specs/` 中与预设标识和场景相关的规范，明确新标识与旧标识迁移策略；不改动与本次需求无关的执行语义条款。
- Rationale: 保持规范稳定性，同时满足 CO-001 可追溯要求。
- Alternatives considered:
  - 新增单独大而全规格：可行但会复制既有规范内容，增加维护成本。
  - 只改代码不改文档：违反宪章 II（Deterministic Workflow Contracts）。

## Decision 5: 测试覆盖优先放在回归风险高的四类路径

- Decision: 优先覆盖 registry 列表、CLI 参数解析与错误提示、runtime 节点输出键/路由、模板文件加载失败路径。
- Rationale: 以上路径直接决定“可调用、可执行、可诊断、可维护”四个核心结果。
- Alternatives considered:
  - 仅做快乐路径：无法发现模板缺失和旧名误用。
  - 仅做端到端：定位成本高，且对命名细粒度断言不足。
