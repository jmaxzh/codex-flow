## 1. 配置编译层支持组合预设

- [x] 1.1 扩展 `config_compiler` 的 workflow 解析，新增 `workflow.imports` 与 `workflow.node_overrides` 字段校验与编译逻辑（含 `workflow` 根级仅允许 `start/imports/node_overrides/nodes`、`imports[]` 仅允许 `preset`、`node_overrides.<node_id>` 仅允许 `on_success/on_failure/route_bindings/success_next_node_from`，未知键报错）。
- [x] 1.2 实现导入 preset 的节点合并流程（按声明顺序导入，再应用 override，再追加本地 nodes），并复用现有 transition 校验。
- [x] 1.3 增加组合错误处理：未知导入 preset、路径型非法 preset 值、override 目标非导入节点/不存在、被导入 preset 含二级 imports、组合后 node id 冲突。

## 2. 新增 doc_doctor 预设并接入 doc_fix 角色

- [x] 2.1 调整 `presets/doc_doctor.yaml`：导入 `doc_reviewer_loop`，保持 `doc_reviwer.on_failure=doc_reviwer` 自循环；使用程序化阶段标记与 `success_next_node_from` 进行阶段后分流（无失败 `-> END`，有失败 `-> doc_fix -> doc_reviwer`），去除提示词判定节点。
- [x] 2.2 在 `doc_doctor` 中调整 `doc_fix` 节点，配置 `parse_output_json=false`、`on_success=doc_reviwer`、`on_failure=END`（仅作为转移字段契约，不作为异常兜底机制），并在成功后重置阶段标记。
- [x] 2.3 配置 `doc_fix.input_map` 精确为且仅为 `context.defaults.user_instruction` 与 `context.runtime.doc_review_history` 两项，并在 `doc_fix.prompt` 中显式消费 `inputs.user_instruction` 与 `inputs.doc_review_history`（包含 `prompt_file(...)` 组合场景）；且 `doc_fix` 不得配置 `collect_history_to`（尤其不得写入 `context.runtime.doc_review_history`）。
- [x] 2.4 在 `doc_doctor` 本地声明 `context.defaults.user_instruction` 与阶段分流常量，避免依赖 imports 隐式继承上下文。

## 3. 运行时分流能力扩展

- [x] 3.1 在 `config_compiler` 增加可选节点字段 `success_next_node_from` 的编译与校验（沿用 source path 规则）。
- [x] 3.2 在 runtime 增加 `pass=true` 路径的程序化下一跳解析：路径缺失回退 `on_success`，路径命中则覆盖下一跳，并校验目标合法。

## 4. 测试覆盖

- [x] 4.1 在配置编译测试中补充 `success_next_node_from` 用例（合法路径编译、非法路径报错），并保持组合 DSL 原有回归覆盖。
- [x] 4.2 在 runtime 测试中新增程序化下一跳覆盖用例（命中覆盖、缺失回退、非法目标失败）。
- [x] 4.3 在预设 wiring 测试中调整 `doc_doctor` 结构断言，覆盖 `workflow.start=doc_reviwer`、`doc_reviwer` 的阶段标记写入与 `success_next_node_from`、`doc_fix.on_failure=END`（结构契约）、`doc_fix` 输入精确两项约束、`doc_fix.prompt` 显式消费两项输入、`doc_fix` 不写 `collect_history_to` 与 `doc_reviwer.collect_history_to=context.runtime.doc_review_history` 前提。
- [x] 4.4 更新 preset 解析相关测试断言，确保 unknown-preset 可用列表包含 `doc_doctor`。

## 5. 文档与验收

- [x] 5.1 更新 `README.md`：补充 `success_next_node_from` 程序化分流说明与 `doc_doctor`“review 先收敛、程序分流决定是否 fix、fix 后回 review 复检”的示例。
- [x] 5.2 执行并记录相关测试与质量门禁（至少包含 orchestrator 单测与 pre-commit 对应检查）。
