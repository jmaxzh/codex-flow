# Feature Specification: OpenSpec Workflow Rename

**Feature Branch**: `[002-refactor-openspec-workflows]`  
**Created**: 2026-04-22  
**Status**: Draft  
**Input**: User description: "需求 1： scripts/_codex_orchestrator/native_workflows/presets.py 的提示词模板必须独立成 presets/prompts 下的预设工作流提示词模板文件；需求 2 ： implement_loop 改名为 openspec_implement, 所有文件和资源命名要以 openspec_implement 开头；需求 3：doc_doctor 改名为 openspec_propose, 所有文件和资源命名要以 openspec_propose 开头。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 统一重命名预设工作流 (Priority: P1)

作为维护者，我可以仅通过新的预设名称 `openspec_implement` 与 `openspec_propose` 调用对应工作流，并在代码、配置、文档、测试与运行产物中看到一致命名。

**Why this priority**: 这是本次变更的核心目标，若命名不统一会导致 CLI 不可用、测试失效或文档误导。

**Independent Test**: 使用新名称执行预设命令并验证入口、路由、资源路径、日志/产物命名全部一致且无旧名称残留。

**Acceptance Scenarios**:

1. **Given** 仓库完成重构, **When** 维护者在 CLI 中调用 `openspec_implement`, **Then** 系统加载对应工作流且不依赖 `implement_loop` 名称。
2. **Given** 仓库完成重构, **When** 维护者在 CLI 中调用 `openspec_propose`, **Then** 系统加载对应工作流且不依赖 `doc_doctor` 名称。

---

### User Story 2 - 提示词模板外置化 (Priority: P1)

作为维护者，我可以在 `presets/prompts/` 下独立维护预设工作流提示词模板，而不需要在 `scripts/_codex_orchestrator/native_workflows/presets.py` 内嵌修改模板文本。

**Why this priority**: 模板与代码解耦可提升可维护性，且是需求 1 的明确约束。

**Independent Test**: 检查 `presets.py` 中不再内嵌这两个工作流的完整模板文本，模板文件存在于 `presets/prompts/` 下并被实际加载。

**Acceptance Scenarios**:

1. **Given** 维护者需要修改 `openspec_implement` 模板, **When** 仅编辑 `presets/prompts/` 下对应模板文件, **Then** 运行时可生效且无需修改 `presets.py`。
2. **Given** 维护者需要修改 `openspec_propose` 模板, **When** 仅编辑 `presets/prompts/` 下对应模板文件, **Then** 运行时可生效且无需修改 `presets.py`。

---

### User Story 3 - 文档与测试同步 (Priority: P2)

作为维护者，我可以在文档和测试中只看到新的工作流命名，避免团队继续使用旧名称。

**Why this priority**: 可用性由执行入口决定（P1），而文档/测试一致性决定后续迭代成本与回归风险。

**Independent Test**: 全量测试通过，且仓库中文档与测试引用新名称并与运行行为一致。

**Acceptance Scenarios**:

1. **Given** 已完成代码改名, **When** 运行相关测试套件, **Then** 涉及预设名称的断言使用 `openspec_implement` 和 `openspec_propose` 并通过。
2. **Given** 已完成代码改名, **When** 查阅用户可见文档, **Then** 不再要求使用 `implement_loop` 或 `doc_doctor`。

### Edge Cases

- 当用户仍传入旧预设名时，系统如何反馈（明确报错或兼容映射）必须保持一致并可测试。
- 当仅重命名了入口但遗漏模板文件名、资源目录名或测试数据名时，必须能被自动化测试发现。
- 当提示词模板文件缺失或命名不匹配时，系统必须给出明确失败信号而不是静默降级到旧内嵌模板。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 将 `scripts/_codex_orchestrator/native_workflows/presets.py` 中与目标预设工作流相关的提示词模板外置到 `presets/prompts/` 下的独立模板文件。
- **FR-002**: 系统 MUST 通过文件化模板加载机制为 `openspec_implement` 和 `openspec_propose` 提供提示词内容，且不再依赖 `presets.py` 内嵌模板正文。
- **FR-003**: 系统 MUST 将原 `implement_loop` 工作流重命名为 `openspec_implement`，并保证相关文件与资源命名以 `openspec_implement` 开头。
- **FR-004**: 系统 MUST 将原 `doc_doctor` 工作流重命名为 `openspec_propose`，并保证相关文件与资源命名以 `openspec_propose` 开头。
- **FR-005**: 系统 MUST 在 CLI 参数解析、工作流注册表、提示词模板引用、测试用例、文档说明和示例命令中统一使用新名称。
- **FR-006**: 系统 MUST 定义并实现对旧名称输入的预期行为（拒绝并提示迁移，或明确兼容映射），且该行为需有自动化测试覆盖。
- **FR-007**: 系统 MUST 确保仓库内新增或重命名的与这两个工作流相关资源（文件名、目录名、标识符）遵循 `openspec_implement*` / `openspec_propose*` 前缀规则。

### Contract & Observability Requirements *(mandatory)*

- **CO-001**: 工作流契约发生变更：可调用预设标识从 `implement_loop`/`doc_doctor` 变为 `openspec_implement`/`openspec_propose`。相关契约文档需在 `docs/specs/` 中更新，并说明对旧名称的兼容或迁移策略。
- **CO-002**: 自动化测试证据必须覆盖预设注册、CLI 调用、模板加载与错误路径，至少包含 `tests/test_codex_orchestrator.py` 及对应 `tests/codex_orchestrator_cases_*.py` 的命名/行为验证。
- **CO-003**: `.codex-loop-state/` 运行产物若包含预设名字段、日志标签、摘要标题或输出文件名，必须反映新名称；如无变化需在变更说明中明确“无运行产物格式变化”。

### Key Entities *(include if feature involves data)*

- **Workflow Preset Identifier**: 预设工作流的唯一调用标识（如 `openspec_implement`、`openspec_propose`），用于 CLI 入口、注册映射与日志归类。
- **Prompt Template Asset**: 位于 `presets/prompts/` 下的可独立维护模板文件，按预设标识进行一一映射。
- **Workflow Registration Entry**: 预设注册配置条目，定义标识、模板引用、流程行为与可见名称。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% 与目标预设相关的用户可见入口（CLI 帮助、示例命令、文档）只使用 `openspec_implement` 与 `openspec_propose`。
- **SC-002**: 针对两个预设的自动化测试通过率达到 100%，且包含模板外置加载与旧名称行为验证。
- **SC-003**: 维护者可在不修改 `presets.py` 的情况下完成两类模板文本更新并被运行流程正确读取（两类模板各至少验证一次）。
- **SC-004**: 仓库扫描结果中，目标范围内不再存在需继续使用 `implement_loop`/`doc_doctor` 的必需引用（明确允许的迁移说明或历史记录除外）。

## Assumptions

- 本次范围聚焦于两个既有预设工作流，不引入新的第三个预设。
- 旧名称默认不再作为主入口；若保留兼容别名，必须在文档与测试中明确其生命周期。
- 现有工作流执行语义保持不变，本次主要调整命名一致性与模板管理方式。
- 现有 CI 流程可用于验证命名重构与模板外置化，不需要额外引入新测试框架。
