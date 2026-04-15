## Why

当前工作流节点只能在配置文件里内联 `prompt` 文本，提示词较长时可读性差、复用困难，也不利于版本化维护。引入 `prompt_file(...)` 后，如果把 role、输出协议、任务指令都拆到外部文件，又会让提示词结构过于零散，降低配置可读性。需要在“可复用”与“就地可读”之间做收敛：仅把 role 放到独立文件，输出协议继续留在配置文件中。

## What Changes

- 为工作流节点新增“提示词文件注入”能力：在 `prompt` 文本中通过模板 helper 引入外部文件内容。
- 注入方式采用 Jinja2 helper（不走 `inputs`）：`{{ prompt_file("./prompts/part.md") }}`，支持一个 `prompt` 中引入多个文件。
- include 与 `{{ inputs.* }}` 变量渲染统一由同一模板引擎（Jinja2）处理，不再采用多阶段、不同语法规则的渲染链路。
- Jinja2 环境采用经典严格模式（`StrictUndefined`），确保缺失 `inputs` 路径时失败而不是静默渲染为空字符串。
- `inputs` 渲染保持现有可读语义：非字符串值按 JSON 文本注入提示词（便于模型消费结构化上下文）。
- `prompt_file` 路径必须是相对路径，且按“相对当前配置文件目录”解析。
- 相对路径允许包含 `..`，按配置目录做常规路径解析；不新增目录越界防护逻辑。
- 路径解析与调用时 `cwd`、`run.project_root` 无关，仅由配置文件位置决定（极简规则）。
- `prompt_file` 以“字符串字面量相对路径”为普通用户主路径；不为动态/表达式路径增加专门支持、AST 校验或兼容分支（行为不纳入兼容承诺）。
- 增加 helper 调用边界与路径校验：对非法调用（缺参、空路径、绝对路径、非字符串路径）、文件不可读场景统一明确报错。
- 采用单次渲染模型：`prompt_file()` 仅负责读文件并返回文本；引入文本不做二次模板渲染，不增加递归 include 检测逻辑。include 文件中的 `{{ ... }}` 会按普通文本保留，不会再被渲染。
- 在文档中把“include 文件内模板表达式不支持”作为固定边界写明，不再作为待决问题反复讨论。
- 内置 preset 与文档示例采用统一组织约定：仅将 role 拆分到独立提示词文件；输出协议（JSON 字段契约）继续内联在节点 `prompt` 配置中，避免提示词过度碎片化。
- 错误信息保持最小可执行：字段定位 + 失败原因；路径类错误在可得时附原始路径与简短修复提示。
- 统一包装模板错误（如语法错误、未定义变量、helper 参数错误、文件读取失败），稳定输出失败节点提示词字段定位（`node_id` 或 `workflow.nodes[n].prompt` 均可）。
- 增加“旧语法手动迁移”文档段落：仅给出从 `{{prompt_file:...}}` 到 `{{ prompt_file("...") }}` 的替换示例与检查清单，不引入运行时兼容逻辑。
- 更新预设示例与文档，演示“主模板（内联输出协议）+ role 文件 + inputs 变量共存”的写法。
- 为配置加载、提示词渲染与运行流程补充测试覆盖。

## Constraints (Hard Limits)

- 仅面向普通用户主路径，不为黑客/专业开发者极端使用行为增加实现分支。
- 项目当前零用户，不引入旧语法兼容层或回滚兼容代码；迁移仅提供文档化手动指引。
- 不新增递归 include 扫描、旧语法特判等额外机制。
- 不新增固定仓库根、symlink 越界防护等复杂路径安全策略；仅保留相对路径（可含 `..`）与可读性校验。
- 不为动态/表达式路径参数增加兼容逻辑、静态分析或额外运行时分支。
- 不要求结构化“全字段”诊断信息，避免为报错格式增加复杂实现。

## Capabilities

### New Capabilities
- `prompt-file-reference`: 允许 workflow 节点在 `prompt` 内通过相对路径 helper 引用外部提示词文件，并在渲染时完成加载与校验。

### Modified Capabilities
- None.

## Impact

- Affected code: `scripts/codex_automation_loops.py`（模板渲染引擎、`prompt_file` helper、基础路径校验、提示词渲染输入）
- Affected dependencies: `requirements.txt`（新增 Jinja2）
- Affected configs/docs: `presets/*.yaml`, `README.md`
- Affected tests: `tests/test_codex_orchestrator.py`
- Runtime behavior: 节点提示词从“仅内联 prompt”扩展为“内联模板 + `prompt_file` helper + inputs 统一渲染”；内置 preset 推荐“role 外置 + 输出协议内联”的组织方式。采用单次渲染与极简路径规则，不引入旧语法兼容、递归 include 检测或复杂路径安全逻辑。

## Explicitly Ignored In This Change

- 不做旧语法 `{{prompt_file:...}}` 的定制错误识别与自动替换。
- 不做 include 文件中的递归 include 检测与专门错误分类。
- 不将动态/表达式路径参数纳入兼容承诺，也不为其增加专门兼容与错误分支。
- 不做“不可读”错误跨平台细分（权限/目录类型/编码等统一按读取失败处理）。
