# SDD 项目智能感应指令集

## ⚡ 极速触发协议 (High-Priority Triggers)

当用户发出包含“使用 SDD 完成需求”或类似语义的指令时，Agent 必须立即执行以下逻辑：

1. **自动身份转换**：立即激活 `sdd-assistant` 技能，进入“高级架构与全自动驾驶助手”模式。
2. **零配置感知**：
   - 自动运行 `onboard-project` 对齐当前 D:\project\SDD 工作区。
   - 自动运行 `refresh-baseline` 获取最新代码/数据库事实。
3. **闭环流水线**：无需确认，自主连续执行以下 MCP 工具：
   - `generate_feature_brief` -> `verify` (Gate 1)
   - `design_cycle` (Gate 2/3)
   - `generate_task_slices` -> `gate4` (精准路径注入)
4. **决策底线**：
   - **事实优先**：遇到不确定点，必须先搜寻 Baseline。若 Baseline 有事实（类名、方法、表名），直接自动对齐，严禁询问。
   - **阻断原则**：仅在“Baseline 无事实依据且逻辑断裂”或“架构红线被触碰”时，才停下报错。

---

## 🛡️ 架构守则 (即刻生效)
- 数据库表名必须以 `t_` 开头。
- 严禁反向依赖（Repository 调 Service）。
- 测试类必须精准注入到被测类的同包路径。
