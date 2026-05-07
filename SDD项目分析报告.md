# SDD 项目架构与功能设计分析报告

> 项目地址：https://github.com/Sssstardust/SDD
> 分析日期：2026-05-07

---

## 一、项目总体评价

这是一个设计思路清晰、定位明确的 **AI 辅助研发规范治理平台**。核心价值在于将软件设计阶段标准化、可量化、可追溯，并通过 MCP 协议与主流 AI 编码助手深度集成。

**项目定位：** SDD 工具库作为中立的编排层，附加到业务仓库上，驱动整个软件设计生命周期，而不侵入业务代码本身。

---

## 二、项目结构概览

```
SDD/
├── mcp-servers/
│   ├── sdd-pipeline/        # 主入口：13 个 pipeline 工具（JSON-RPC 2.0）
│   ├── project-explorer/    # 代码库扫描与索引
│   ├── arch-standard/       # 架构规则查询（9 条规则文件）
│   └── polyquery/           # 多数据库只读查询接口
├── scripts/                 # ~62 个 Python 编排脚本
├── skills/
│   ├── requirement-analyzer/   # PRD → 结构化需求
│   ├── sdd-generation/         # 设计包生成
│   └── sdd-assistant/          # AI 工作流规则
├── templates/               # Codex / Gemini CLI / OpenCode 三套 Agent 模板
├── specs/                   # 示例项目规格与报告
└── docs/                    # 架构标准文档
```

**核心技术栈：**

| 技术 | 用途 |
|------|------|
| Python 3.13+ | 核心流程编排（约 80% 代码量） |
| TypeScript / Node.js 18+ | 四个 MCP Server |
| Java | Gate 5 生成的测试桩 |
| MCP 协议 | AI Agent 与工具链的标准化接口 |
| MySQL / PG / MongoDB / Redis / Oracle / SQLite | polyquery 支持的数据库 |

---

## 三、架构层面建议

### 3.1 MCP Server 职责边界可进一步清晰化

**现状：** `sdd-pipeline` 是所有核心流程的入口，通过 `spawnSync` 调用 Python 脚本，实质上是"胖代理层"。所有 13 个工具汇聚在一个 server 中。

**问题：**
- 随工具数量增长，`server.ts` 会变成难以维护的单体文件
- `spawnSync` 同步阻塞对长时任务（如 Gate 5 执行 Java 测试）存在超时风险

**建议：**
- 将 pipeline 工具按生命周期分组，考虑拆分为 `sdd-design` / `sdd-gate` / `sdd-baseline` 三个独立 MCP Server
- 引入异步任务机制：`spawnSync` 改为 `spawn` + 轮询状态文件，或用 `child_process.exec` + Promise 包装
- `arch-standard` 目前只读规则文件，可合并进 `project-explorer` 或作为 `sdd-pipeline` 的资源端点，减少部署复杂度

---

### 3.2 状态管理分散，缺乏统一状态机

**现状：** 流程状态散落在多个 JSON 文件中（`flow-status.json`、`attached-project.json`、`sdd-index-design.json` 等），通过各个 Python 脚本各自读写。

**问题：**
- 并发场景下存在竞争条件风险
- AI Agent 推断当前流程状态时需要读多个文件交叉验证，容易出现不一致判断

**建议：**
- 引入 `project-state.json` 作为**单一真相来源（SSOT）**，记录当前 feature 所处 Gate 阶段、最近一次 gate 结果、未解决的 AMBIGUOUS 项
- `flow_state.py` 扩展为完整状态机模型，所有脚本通过它读写，而不是直接操作各自的 JSON
- 对状态文件写入加简单文件锁（`fcntl` 或 `portalocker`）

---

### 3.3 Python 脚本层缺乏统一错误契约

**现状：** 约 62 个 Python 脚本各自处理错误，通过 stdout/stderr 输出，MCP Server 解析文本判断成功失败。

**问题：** 文本解析脆弱，一旦脚本输出格式变化，MCP 层会静默失败；错误信息对 AI Agent 不够结构化，难以做精准错误恢复。

**建议：**

统一脚本输出协议，所有脚本退出时输出标准 JSON：

```json
{
  "status": "ok|error|warn",
  "data": {},
  "message": "...",
  "errors": []
}
```

- MCP Server 通过 exit code + JSON 解析双重确认，而非只解析文本
- 将公共逻辑（`json_io.py`、`sdd_yaml.py`、`versioning.py`）封装成内部包，减少脚本间重复 import 路径问题

---

### 3.4 多项目隔离需要更严格的命名空间设计

**现状：** `.spec/attached-project.json` 是工作目录级别的单文件，一个 SDD 实例只能 attach 一个项目。

**问题：** 微服务架构下，团队需要同时维护多个业务项目，频繁切换 attachment 导致工作流不连贯。

**建议：**
- `.spec/` 改为支持多项目 profile：`.spec/projects/<project-id>/attached-project.json`
- `sdd-pipeline` MCP 工具调用时增加 `projectId` 必填参数，从根本上支持多项目并行
- `project-explorer` 的扫描缓存（`cache.ts`）也按 projectId 分桶

---

## 四、功能设计建议

### 4.1 Feature Brief 的歧义处理流程需结构化

**现状：** `[AMBIGUOUS: ...]` 标记由 AI 自行判断并插入文档，无追踪机制，不清楚哪些已解决、哪些被跳过。

**建议：**
- 引入 `ambiguity-tracker.json`，每条歧义有唯一 ID、状态（open/resolved/waived）、解决方式
- Gate 1 增加检查：如有 `status=open` 的歧义项，直接阻断设计阶段推进
- 设计文档中用 `[AMBIGUOUS#001]` 引用 ID，而非嵌入完整描述，保持文档可读性

---

### 4.2 Gate 系统的反馈粒度可以更细

**现状：** Gate 1-4 输出结论性报告，AI Agent 只能知道通过/失败，具体违规规则和设计节点需要手动解读报告文件。

**建议：**

Gate 输出增加结构化的 `violations` 数组：

```json
{
  "gate": 1,
  "passed": false,
  "violations": [
    {
      "rule": "layering-001",
      "location": "PaymentService.java:32",
      "detail": "Service 直接调用了 Repository 之外的 DAO 层"
    }
  ]
}
```

让 AI Agent 直接定位问题并生成修复建议，而不是再去读报告文件。

---

### 4.3 polyquery 的安全边界需要加固

**现状：** polyquery 标注为只读，但只读限制依赖使用者自律（`.env.example` 配置只读账号）。

**问题：** MCP 工具暴露给 AI Agent 后，Agent 可能拼出 DDL 语句绕过只读意图；生产数据库凭证一旦泄露风险极高。

**建议：**
- 在 `polyquery` server 内部做 SQL AST 解析，拦截任何非 SELECT 操作，不依赖账号权限
- 增加查询白名单机制：只允许查询 `schema-context.json` 中声明的表
- 文档中明确要求只连接**只读副本或快照数据库**，禁止连接生产主库

---

### 4.4 AI Agent 模板需保障功能对等性

**现状：** `templates/` 下有 Codex、Gemini CLI、OpenCode 三套模板，各自维护，内容可能逐渐漂移。

**建议：**
- 提取一份**规范性 Agent Capability Manifest**（YAML 格式），列出所有 SDD 工作流步骤和对应的 MCP 工具调用
- 三套模板都从这份 manifest 生成，或至少以它为 checklist 验证功能对等性
- 在 CI（GitHub Actions）中加检查：对比三套模板中 MCP 工具调用列表是否一致

---

### 4.5 缺少可观测性层

**现状：** 流程执行情况只通过本地 JSON 文件留存，没有聚合视图。

**建议：**

扩展 `build_project_console.py` 输出 `console.html` 静态报告，包含：
- 各 feature 当前所在 Gate 阶段
- Gate 通过率趋势图
- 未解决歧义项统计
- Baseline 版本历史

对项目经理和架构师评审整体研发质量很有价值。

---

## 五、优先级汇总

| 优先级 | 建议 | 影响范围 |
|--------|------|----------|
| 高 | 统一脚本输出 JSON 协议（3.3） | 稳定性、可维护性 |
| 高 | `spawnSync` 改异步 + 状态轮询（3.1） | 长任务可靠性 |
| 高 | polyquery SQL 拦截层（4.3） | 安全性 |
| 中 | 单一状态机 project-state.json（3.2） | 一致性 |
| 中 | Gate violation 结构化输出（4.2） | AI Agent 效率 |
| 中 | 歧义追踪机制（4.1） | 设计质量 |
| 低 | MCP Server 拆分（3.1） | 可维护性（当前规模不紧迫） |
| 低 | Agent 模板对等性 CI 检查（4.4） | 多 Agent 一致性 |
| 低 | 可观测性静态报告（4.5） | 管理可见性 |

---

## 六、总结

SDD 项目的**设计理念非常扎实**：

- 用 **Gate 驱动设计质量**，确保实现前设计已充分验证
- 用 **MCP 桥接 AI 工具链**，让 AI Agent 成为真正可用的研发助手
- 用 **Baseline 保障设计溯源**，建立完整的设计决策历史

主要改进空间集中在两个方向：

1. **工程健壮性**：错误契约统一、异步调用改造、安全边界加固
2. **AI Agent 可用性**：更结构化的反馈输出，减少 Agent 解读原始文件的负担，让 AI 更精准地辅助开发决策

这套工具如果进一步完善，有潜力成为团队级 AI 辅助研发的基础设施标准。
