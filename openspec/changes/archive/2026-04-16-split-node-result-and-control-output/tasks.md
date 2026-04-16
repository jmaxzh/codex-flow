## 1. 输出解析与运行时数据结构

- [x] 1.1 重构 `parse_and_validate_output`，在保持末行 JSON 校验的前提下同时提取 `result`（末行前完整文本）与 `control`（末行 JSON object）。
- [x] 1.2 调整 `resolve_node_output` 返回结构：`parse_output_json=true` 时返回 `{result, control}` 与 `pass_flag`，`pass_flag` 来自 `control.pass`。
- [x] 1.3 更新 `run_workflow` 中 `runtime_state["outputs"][node_id]` 的写入逻辑，使 JSON 解析节点输出为对象封装，纯文本节点保持字符串行为不变。

## 2. 映射、历史与持久化兼容

- [x] 2.1 验证并必要时调整 `route_bindings` 与 `input_map` 路径解析，确保可稳定读取 `outputs.<node_id>.result` 与 `outputs.<node_id>.control`。
- [x] 2.2 验证并必要时调整 `collect_history_to` 行为，确保 `parse_output_json=true` 节点按完整封装对象（含 `result/control`）追加历史，`parse_output_json=false` 节点继续追加字符串。
- [x] 2.3 校验 `persist_state_and_logs` 的输出文件语义，确保 `runtime_state.json`、`run_summary.json` 与每步 `__parsed.json` 都按 `outputs.<node_id>` 同构落盘（`parse_output_json=true` 为 `{result, control}`，`parse_output_json=false` 为 string）且不破坏状态追踪。

## 3. 预设与文档迁移

- [x] 3.1 更新 `presets/*.yaml` 中依赖节点控制输出的映射路径，从 `outputs.<node_id>` 迁移到 `outputs.<node_id>.control`（按实际节点使用场景拆分 result/control）。
- [x] 3.2 更新 `README.md` 固定输出契约：明确 node 双输出模型，保留末行 JSON 控制约束，并删除“结论需在 JSON 重复输出”的要求。
- [x] 3.3 在 README 增加 BREAKING 迁移说明与旧新路径对照示例（`outputs.<node_id>` → `outputs.<node_id>.control` / `.result`）。
- [x] 3.4 在 README 的 BREAKING 迁移说明中补充 `collect_history_to` 条目形态变更（旧控制对象 → 新 `{result, control}`）及旧/新示例。

## 4. 测试与回归验证

- [x] 4.1 新增/更新单元测试覆盖：双输出成功解析、多行文本解析、仅控制行解析、末行非 JSON/非对象/缺失 pass/pass 非 bool 失败路径，以及 `result` 对 trailing whitespace 与 whitespace-only prefix 的保留断言。
- [x] 4.2 新增/更新流程测试覆盖：路由基于 `control.pass`，下游可分别消费 `result` 与 `control`，history 记录完整封装对象，且 `__parsed.json` 落盘 `{result, control}` 形态。
- [x] 4.3 新增/更新流程测试覆盖：`parse_output_json=true` 解析失败时步骤直接报错终止，且不会执行 `on_failure` 路由节点。
- [x] 4.4 保留并验证 `parse_output_json=false` 分支回归，确认输出与 history 仍为字符串、`__parsed.json` 同步保持字符串形态且行为不变。
- [x] 4.5 运行 `tests/test_codex_orchestrator.py` 并修复新增契约导致的断言更新，确保测试通过。
