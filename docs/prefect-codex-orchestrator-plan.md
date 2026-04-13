# Prefect + Codex 任务编排引擎改造方案（配置文件唯一入口）

## 1. 目标约束（最终版）

1. 启动不接受任何业务 CLI 参数。
2. 所有提示词只允许配置文件内联文本，不支持 `file`。
3. 不再内置固定阶段语义（`implement/review/check/fix` 全部移除）。
4. 工作流完全由配置定义任意节点与跳转。
5. 输出契约固定：每个节点输出必须是 JSON object，且必须有 `pass: boolean`。
6. 路由固定：`pass=true -> on_success`，`pass=false -> on_failure`。
7. 节点完整 JSON 原样透传给后续节点使用。
8. `codex-cli` 作为执行器，Prefect 作为编排与可观测层。

## 2. 配置 DSL（最小通用版）

```yaml
version: 1

run:
  project_root: /abs/path/to/target
  state_dir: .codex-loop-state
  max_steps: 50

executor:
  cmd: ["codex", "exec", "--skip-git-repo-check"]

context:
  static:
    spec: "docs/xxx.md"
    coding_rules: "..."

workflow:
  start: plan
  nodes:
    - id: plan
      prompt: |
        你是规划器。输入: {{inputs.spec}}
        输出 JSON，必须包含 pass 字段。
      input_map:
        spec: "context.static.spec"
      on_success: implement
      on_failure: END

    - id: implement
      prompt: |
        根据规划结果执行。规划输出: {{inputs.plan_output}}
        输出 JSON，必须包含 pass 字段。
      input_map:
        plan_output: "outputs.plan"
      on_success: verify
      on_failure: fix

    - id: verify
      prompt: |
        验证实现结果。实现输出: {{inputs.impl_output}}
        输出 JSON，必须包含 pass 字段。
      input_map:
        impl_output: "outputs.implement"
      on_success: END
      on_failure: fix

    - id: fix
      prompt: |
        根据失败信息修复。验证输出: {{inputs.verify_output}}
        输出 JSON，必须包含 pass 字段。
      input_map:
        verify_output: "outputs.verify"
      on_success: verify
      on_failure: END
```

## 3. 四个核心方法（简化固定版）

### 3.1 `render_prompt(node_prompt: str, prompt_inputs: dict) -> str`

职责：仅根据提示词模板与输入数据渲染最终文本。

约束：
1. 只传 prompt 所需输入，不传控制流上下文。
2. 严格模板渲染，缺变量即失败。
3. 不参与路由判断，不处理执行结果。

### 3.2 `parse_and_validate_output(raw_output: str) -> tuple[dict, bool]`

职责：固定契约解析与校验。

固定规则：
1. 输出必须是 JSON object。
2. 必须包含 `pass` 字段。
3. `pass` 必须是 boolean。

返回：
1. 完整 JSON（原样透传给后续节点）。
2. `pass_flag`（用于路由）。

### 3.3 `persist_state_and_logs(...)`

职责：落盘状态和日志。

原则：
1. 固定复用项目当前已有状态与日志落盘机制。
2. 不新造一套存储协议，仅泛化为“节点无关”。
3. 每步至少保存：
   - 渲染后 prompt
   - codex 原始输出
   - 解析后 JSON
   - 节点执行元信息（step、node_id、attempt、next_node）

### 3.4 `resolve_next_node(node, pass_flag) -> str`

职责：按 `pass` 结果做最小路由。

规则：
1. `pass_flag=True` -> `node.on_success`
2. `pass_flag=False` -> `node.on_failure`
3. `END` 表示流程结束。
4. 目标节点不存在则 fast-fail。

## 4. Prefect 编排结构

1. `@flow run_workflow()`：固定读取 `./orchestrator.yaml`。
2. `@task load_config()`：读取并校验配置完整性。
3. `@task build_prompt_inputs(node, state)`：按 `input_map` 从 `context.static` 和 `outputs.*` 取值。
4. `@task render_prompt(...)`。
5. `@task run_codex_exec(...)`。
6. `@task parse_and_validate_output(...)`。
7. `@task persist_state_and_logs(...)`。
8. `@task resolve_next_node(...)`。
9. `run_workflow` 中循环执行，直到 `END` 或达到 `max_steps`。

## 5. 代码改造步骤

1. 抽象通用配置模型与校验器，移除固定模式字段。
2. 将现有执行/日志逻辑改造成节点无关通用函数。
3. 实现四个核心方法（固定契约 + 最小路由）。
4. 用 Prefect flow/task 连接成状态机执行。
5. 删除旧 `implement-loop/review-loop/all` 入口与参数解析。
6. 更新 README 为“仅配置文件启动”。

## 6. 测试与验收

1. 配置缺节点、缺 `on_success/on_failure` 时启动失败。
2. 模型输出缺 `pass` 或 `pass` 非 boolean 时失败。
3. `pass=true` 必走 `on_success`，`pass=false` 必走 `on_failure`。
4. 下游节点可读取上游节点完整 JSON。
5. `max_steps` 生效，防止无限循环。
6. 运行不依赖业务 CLI 参数。

## 7. 里程碑建议

1. M1：DSL + 校验器 + 四方法骨架。
2. M2：Prefect flow 跑通单条线性 workflow。
3. M3：分支/循环 + 日志复用 + fail-fast 完整闭环。
4. M4：替换旧入口并补全文档与测试。
