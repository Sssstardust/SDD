# SDD（规范驱动开发）项目文档

---

## 一、项目背景与核心定位

### 1.1 项目简介

SDD（Spec-Driven Development，规范驱动开发）是一套面向研发团队的 **AI 辅助全流程开发治理工具链**。项目通过将 AI 能力嵌入软件设计文档（Software Design Document）的生命周期管理中，以结构化、可审计、可量化的方式，规范从需求拆解到代码上线的完整研发流程。

该项目的核心理念是：**业务代码、SQL、配置留在各业务仓库；SDD 仓库统一管理流程编排、设计模板、质量门控、AI 工具集成和基线版本管理**，各业务项目以"附着模式（Attached Project Mode）"挂载至本工具链使用。

### 1.2 项目价值主张

| 核心价值 | 说明 |
| :--- | :--- |
| 研发流程标准化 | 强制执行五阶段门控流程，杜绝跳步、凑数 |
| AI 能力落地 | 将 AI 融入需求分析、设计生成、质量验证等关键环节 |
| 架构规范自动执行 | 9 大架构规范通过 MCP 自动校验，减少人工审查成本 |
| 设计与实现双向追踪 | 全生命周期可追溯，设计基线与真实代码保持同步 |
| 团队统一协作基线 | 多项目共享同一套工具，知识和规范沉淀可复用 |

---

## 二、项目结构总览

```
SDD/
├── scripts/          # Python 自动化脚本（60+个，核心执行引擎）
├── mcp-servers/      # MCP 服务器（4个，AI 工具扩展层）
│   ├── sdd-pipeline/      # 流程编排 MCP
│   ├── arch-standard/     # 架构规范 MCP
│   ├── polyquery/         # 多数据源查询 MCP
│   └── project-explorer/  # 代码库扫描 MCP
├── skills/           # AI 技能模块（3个，AI 能力封装层）
│   ├── requirement-analyzer/  # 需求解析器
│   ├── sdd-generation/        # 设计文档生成器
│   └── sdd-assistant/         # SDD 流程助手
├── specs/            # 功能规格实例（含完整生命周期示例）
│   ├── task-board/            # 任务看板（已全流程完成，含审批）
│   ├── pilot-payment-review/  # 支付审核试点
│   └── tob-oa-office-demo/    # ToB OA 办公自动化示例
├── docs/             # 技术文档与架构规范
│   └── arch-standards/   # 9 大架构约束规范文档
├── document/         # 项目设计文档、方案规划、汇报材料
├── templates/        # Agent 能力模板（支持多平台 AI 接入）
├── examples/         # 测试夹具与门控验证用例
└── .github/workflows/ # CI/CD 流水线配置
```

### 技术栈说明

| 层次 | 技术 | 说明 |
| :--- | :--- | :--- |
| 核心执行引擎 | Python 3.13+ | 占代码比例 81.1%，所有流程逻辑 |
| MCP 服务层 | TypeScript / Node.js 18+ | 占 18%，AI 工具能力扩展 |
| 质量验证层 | Java / javac | 门控第五阶段代码扫描 |
| 包管理 | uv（Python）/ npm（Node.js） | — |
| CI/CD | GitHub Actions | Windows Runner 全流程自动化验证支持 |
| 数据库 | PostgreSQL / MySQL / Oracle ... | 多源上下文 |

---

## 三、功能结构：五阶段门控流程

SDD 的核心功能是一套 **五阶段强制门控研发流程**，每个阶段通过 AI 辅助生成 + 自动化脚本验证 + 质量门放行，形成闭环。

```
需求输入（PRD）
    ↓
[阶段一] 需求解析 → 需求规格（功能概要）
    ↓
[阶段二] 技术方案生成 → 技术方案-v{N}.md + 设计包/（设计包）
    ↓  ← 质量门 Gate 1/2/3
[阶段三] 任务切片 → 任务切片/slice-*.md（开发任务拆解）
    ↓
[阶段四] 实现框架 → Gate 4 骨架验证（接口/模型是否对齐设计）
    ↓
[阶段五] 代码落地 → Gate 5 实现覆盖率验证 + 基线同步
    ↓
[发布门控] 发布门控 → 发布治理审计
    ↓
上线
```

### 3.1 各阶段详解与意义

#### 阶段一：需求解析（需求规格生成）

**触发**：研发人员或产品经理提交 PRD 文档（Markdown / Word 等）

**执行过程**：

- `requirement-analyzer` Skill 调用 AI 对 PRD 进行结构化解析
- 输出 `structured-prd.json`（含需求列表、实体、接口、歧义项、业务规则）
- 同步生成 `需求规格.md`（功能概要，人工可读版本）

**核心意义**：

- 将非结构化的产品文档转化为机器可读的标准化格式，消除"需求理解偏差"
- 主动识别并标记 `[AMBIGUOUS]`（歧义需求），强制在设计前澄清，而非开发中踩坑
- 为后续所有阶段提供统一的"需求源"，确保追踪链路完整

---

#### 阶段二：技术方案生成（设计 + Gate 1/2/3）

**触发**：需求规格通过后，由 `sdd-generation` Skill 调用 AI 生成

**生成物清单（设计包/）**：

| 产物 | 格式 | 说明 |
| :--- | :--- | :--- |
| `技术方案-v{N}.md` | Markdown | 主设计文档（分层架构、接口、状态机等） |
| `接口契约.openapi.yaml` | OpenAPI | 机器可验证的接口规范 |
| `数据模型.md` | Markdown | 实体字段定义 |
| `数据库变更.sql` | SQL | 含 UP/DOWN 脚本的迁移方案 |
| `外部调用策略.md` | Markdown | 外部依赖的超时/重试/熔断策略 |
| `异步事件契约.yaml` | YAML | 异步事件定义与消费方契约 |

**三道质量门**：

- **Gate 1**：设计完整性校验（必填章节、必要字段）
- **Gate 2**：设计真实性校验（接口/实体是否与代码库现状一致，避免"设计空中楼阁"）
- **Gate 3**：架构规范校验（调用方向、分层合规、幂等性声明等 9 大规范）

**核心意义**：

- AI 生成 + 自动门控双保险，设计文档质量可量化、可追责
- 设计包标准化，评审效率显著提升（有 OpenAPI 合同可直接验证，无需口头描述）
- `risk_tier=high` 的功能强制要求人工 `审批记录.json`，高风险变更有明确的审批留痕

---

#### 阶段三：任务切片（任务切片）

**触发**：设计文档通过 Gate 1/2/3 后，自动生成

**输出**：

- `tasks/slice-001-biz.md` 至 `slice-00N-*.md`（垂直切片 + 横切关注点）
- `任务列表.json`（机器可读的任务列表）

**切片类型**：业务逻辑、数据库层、异步处理、外部集成、权限控制等横切关注点

**核心意义**：

- 将设计文档拆解为开发人员可直接领取的、边界清晰的工作单元
- 任务与设计产物绑定，开发过程可追踪至设计决策
- 为 Gate 5 的覆盖率验证提供基准清单

---

#### 阶段四：实现框架验证（Gate 4 骨架校验）

**触发**：开发人员提交初始代码框架后执行

**验证内容**：

- 接口签名是否与 OpenAPI 合同一致
- 数据模型是否与 `数据模型.md` 对齐
- 关键服务方法是否存在（即使尚未实现）

**核心意义**：

- 在代码完成之前提前发现"开发偏离设计"的问题，降低返工成本
- 确保团队在统一的接口契约下并行开发，避免集成时的接口不兼容

---

#### 阶段五：实现覆盖验证（Gate 5 + 基线同步）

**触发**：代码开发完成后执行

**执行过程**：

- `check_design_test_coverage.py` 扫描 Java 源码（通过 `project-explorer` MCP）
- 逐一核查 `任务切片` 中每个任务对应的实现是否存在
- 计算需求到实现的覆盖率，输出 `verify-report.json`
- Gate 5 通过后，自动执行 `sync_baseline.py` 更新 `sdd-index-real.json`（真实基线）

**核心意义**：

- **闭合研发循环**：从需求 → 设计 → 实现全链路可验证，而非靠人工自述
- 基线同步确保下一个功能的设计生成能基于最新的真实代码状态，而非过时文档
- 量化团队研发合规率，为管理层提供可视化数据支撑

---

#### 发布门控（发布门控）

**触发**：准备上线前执行

**验证内容**：

- 所有前置 Gate 是否均已通过
- 高风险功能是否有 `审批记录.json`（审批留痕）
- 设计产物完整性最终确认
- 发布计划（`发布计划.md`）是否存在

**核心意义**：

- 作为上线前的最后一道质量关卡，防止未经完整验证的变更进入生产环境
- 审批记录可用于合规审计和事后追溯

---

## 四、解决的核心痛点

| # | 痛点描述 | SDD 的解决方案 |
| :--- | :--- | :--- |
| 1 | **需求理解偏差** — 研发对 PRD 理解不一致，开发完成后大量返工 | `requirement-analyzer` Skill 将 PRD 结构化，歧义强制澄清后才能推进 |
| 2 | **设计文档缺失或流于形式** — 设计文档要么没有，要么开发完再补，失去指导意义 | AI 在编码前生成完整设计包，门控强制"设计先行" |
| 3 | **架构规范执行靠人** — 代码评审中重复发现分层混乱、缺少熔断等问题 | 9 大架构规范通过 `arch-standard` MCP 自动校验，零人工干预 |
| 4 | **设计与代码不一致** — 设计文档与实际实现脱节，基线过时 | Gate 5 + 基线同步机制，实现完成后自动更新真实基线 |
| 5 | **高风险变更审批缺失** — 支付、核心业务变更缺乏明确审批流程和留痕 | `risk_tier=high` 强制 `审批记录.json`，审批可追溯 |
| 6 | **新人接入成本高** — 不了解规范，靠老人带的方式效率低下 | 工具链即规范，新人按工具提示执行即可达到合规标准 |
| 7 | **跨团队知识孤岛** — 各团队规范不统一，设计风格差异大 | SDD 仓库提供团队级统一工具，规范沉淀可共享复用 |
| 8 | **AI 工具碎片化使用** — AI 只用于写代码，未系统性融入研发流程 | AI 覆盖需求→设计→验证完整链路，效能提升有迹可循 |

---

## 五、Skill 模块说明

Skill 是本项目中对 AI 能力的封装单元，每个 Skill 包含 AI 提示词模板、结构化入参/出参定义、CLI 可执行入口，支持在 Codex CLI、Cursor、Kiro、VS Code、Claude Desktop、Gemini CLI 等多种 AI 开发环境中调用。

### 5.1 `requirement-analyzer` — 需求解析器

| 属性 | 说明 |
| :--- | :--- |
| **定位** | 将原始 PRD（Markdown / Word 等）转化为结构化 JSON |
| **输入** | 需求文档文件路径 |
| **输出** | `structured-prd.json`（含需求列表、实体、接口、歧义项）+ `需求规格.md` |
| **AI 代理名称** | 需求解析器（允许隐式调用） |
| **退出码语义** | 0=就绪 / 1=系统错误 / 2=需要人工澄清（不允许静默猜测） |
| **核心价值** | 消除需求理解偏差，为下游所有阶段提供唯一可信的需求源 |

**结构化输出字段**：

- `feature_type`、`risk_tier`（低/高风险评估）
- `requirements[]`（REQ-### 编号，优先级 P0/P1/P2）
- `ambiguities[]`（歧义清单，必须在设计前解决）
- `entities[]`、`apis[]`、`business_rules[]`、`dependencies[]`

---

### 5.2 `sdd-generation` — 设计文档生成器

| 属性 | 说明 |
| :--- | :--- |
| **定位** | 基于结构化需求 + 代码基线上下文，AI 生成完整技术方案 |
| **输入** | `structured-prd.json`、`需求规格.md`、`module-map.json`、`schema-context.json` |
| **输出** | `技术方案-v{N}.md` + `设计包/`（完整设计包） |
| **生成策略** | 最多 3 次重试循环：上下文组装 → AI 生成 → 结构验证 → Gate 验证，失败升级人工 |
| **AI 代理名称** | 设计生成器（允许隐式调用） |
| **核心价值** | 设计文档质量与速度双提升，且生成过程可重复、可验证 |

**关键特性**：

- 自动引入现有代码库的模块图（`module-map.json`）和数据库 Schema（`schema-context.json`），确保设计"脚踏实地"
- 支持通过 `--feedback gate-report.json` 将门控失败报告反馈给 AI，实现设计自动迭代修正

---

### 5.3 `sdd-assistant` — SDD 流程助手

| 属性 | 说明 |
| :--- | :--- |
| **定位** | AI Agent 工作流执行者，负责在对话中执行和管理完整 SDD 流程 |
| **核心职责** | 调用 MCP 工具、跟踪阶段状态、执行门控、处理冲突解决 |
| **关键规则** | 不可跳步、不可伪造通过、不可手动修改 `.spec/` 下的 JSON 文件 |
| **决策优先级** | 真实基线（sdd-index-real.json） > 设计基线（sdd-index-design.json） > 通用知识 |
| **核心价值** | 将流程规范固化为 AI 行为约束，人员合规性不依赖个人自律 |

---

## 六、MCP 服务器说明

MCP（Model Context Protocol）是 AI Agent 与外部工具/数据源交互的标准协议。本项目共 4 个 MCP 服务器，构成 AI 工具能力的基础设施层。

### 6.1 `sdd-pipeline` — 流程编排 MCP

| 属性 | 说明 |
| :--- | :--- |
| **版本** | v0.1.0（TypeScript） |
| **暴露工具数量** | 16 个 MCP 工具 |
| **核心价值** | AI Agent 与 SDD 完整流程的唯一交互入口，将 Python 脚本封装为结构化工具调用 |

**工具清单**：

| 工具名称 | 作用 |
| :--- | :--- |
| `list_pipeline_commands` | 列出所有可用流程命令 |
| `show_attachment` | 查看当前挂载的项目配置 |
| `refresh_baseline` | 更新模块图、Schema 上下文、治理产物 |
| `project_console_cycle` | 刷新项目状态 + 重新生成项目总览 |
| `project_next` | 获取当前项目的下一步操作建议 |
| `flow_status` | 查询指定功能目录的流程状态 |
| `validate_reports` | 验证单个功能的报告完整性 |
| `validate_all_reports` | 批量验证所有功能的报告 |
| `generate_task_slices` | 为功能生成任务切片 |
| `design_gates` | 执行设计阶段 Gate 1/2/3 |
| `gate5` | 运行需求覆盖率验证 |
| `release_gate` | 执行发布门控检查 |
| `onboard_project` | 新项目挂载 + 初始化流程 |
| `start_pipeline_task` | 启动异步任务（返回任务 ID） |
| `get_pipeline_task` | 轮询异步任务状态 |
| `read_pipeline_task_result` | 读取已完成异步任务结果 |

---

### 6.2 `arch-standard` — 架构规范 MCP

| 属性 | 说明 |
| :--- | :--- |
| **版本** | v0.1.0（TypeScript） |
| **暴露工具数量** | 4 个 MCP 工具 |
| **核心价值** | 将团队架构规范结构化、可查询，AI 在门控验证时实时调取规范条目进行比对 |

**工具清单** | 作用 |
| :--- | :--- |
| `list_rules` | 枚举所有可用架构规范及规则文件 |
| `get_rule` | 获取单条规则的完整内容和元数据 |
| `get_constraints` | 按规则 ID 过滤，返回结构化约束条目 |
| `get_feature_rules` | 按功能类型和能力标签，返回适用规范集合 |

**管理的 9 大规范**：

- 分层规范（严格上下调用，禁止逆向依赖）
- API 规范（必须有 OpenAPI 合同，完整字段描述）
- 异常处理规范（必须有异常处理表）
- 幂等性规范（状态变更、支付、库存扣减必须声明幂等策略）
- 命名规范（设计用中文语义名，DB 表名必须 `t_` 前缀）
- 支付规范、事务规范、外部调用规范、分层语义（机器可读 JSON）

---

### 6.3 `polyquery` — 多数据源查询 MCP

| 属性 | 说明 |
| :--- | :--- |
| **版本** | v1.2.0（TypeScript，MIT 开源） |
| **外部仓库** | https://github.com/Sssstardust/PolyQuery-MCP |
| **暴露工具数量** | 5 个 MCP 工具 |
| **支持数据源** | PostgreSQL / MySQL / Oracle / MongoDB / Redis / SQLite |
| **安全策略** | 默认只读模式，最大返回 1000 行，查询超时 30 秒，内置 SQL 注入防护 |
| **核心价值** | 让 AI 在设计生成和门控验证时能"看见"真实的数据库 Schema，而非凭空设计 |

**工具清单**：

| 工具名称 | 作用 |
| :--- | :--- |
| `query_database` | 执行只读 SQL / NoSQL 查询 |
| `list_tables` | 列出指定数据库的所有表/集合 |
| `describe_table` | 获取表结构（字段、类型、索引） |
| `test_connection` | 测试数据库连接可用性 |
| `list_databases` | 列出所有已配置的数据源 |

**已配置数据源**（来自 `polyquery.example.json`）：PostgreSQL（测试库 + 报表库）、Oracle（PDC + ToB）、MySQL（定价）

---

### 6.4 `project-explorer` — 代码库扫描 MCP

| 属性 | 说明 |
| :--- | :--- |
| **版本** | v0.1.0（TypeScript） |
| **暴露工具数量** | 3 个 MCP 工具 |
| **扫描目标** | Java 源码（`src/main/java` + `src/test/java`） |
| **缓存策略** | 30 分钟 TTL，最多 60 个类条目 |
| **核心价值** | 为 Gate 2（设计真实性）和 Gate 5（实现覆盖率）提供代码现状数据，实现"设计与代码的双向比对" |

**工具清单**：

| 工具名称 | 作用 |
| :--- | :--- |
| `scan_modules` | 关键词匹配扫描类/模块列表 |
| `verify_class_exists` | 验证指定类名是否存在于代码库中 |
| `get_class_detail` | 获取类的详细信息（方法签名、注解、字段） |

---

## 七、CI/CD 自动化集成

项目提供完整的 GitHub Actions 工作流模板（`.github/workflows/sdd-pipeline.example.yml`）：

**触发条件**：

- 手动触发（`workflow_dispatch`，可指定功能目录和严格模式）
- PR 提交变更至 `specs/`、`scripts/`、`docs/`、`mcp-servers/`、`examples/` 时自动触发

**流水线步骤**：

1. 环境准备（Python 3.13 + Node.js 20）
2. 构建并测试 MCP 服务器
3. 执行完整 SDD 流程（`refresh-baseline` → `design-gates` → `implementation-gates` → `release-gate` → `validate-all-reports`）
4. 无论成功失败，上传门控报告、流程状态、基线快照等产物

---

## 八、项目完整示例：任务看板功能（已验证）

`specs/task-board/` 展示了一个完整走过全流程的功能案例，可作为标杆参考：

| 指标 | 状态 |
| :--- | :--- |
| 功能名称 | 团队任务看板系统（支持拖拽排序、通知、活动日志、权限控制） |
| 风险等级 | 高风险（high） |
| 当前状态 | `release-ready`（发布就绪） |
| 审批状态 | **已审批**（审批人：zhaoxingchen，日期：2026-05-06） |
| 所有门控 | Gate 1/2/3/4/5 + Release Gate **全部 PASS** |
| 设计版本 | v2（含优化迭代） |
| 任务切片 | 8 个（5 业务逻辑 + 1 数据库 + 1 异步 + 1 外部集成） |

---

## 九、基线版本管理体系

基线（Baseline）是 SDD 项目的核心数据基础设施，贯穿整个五阶段流程。它并非机器学习语境中的"基准模型"，而是一种**软件工程意义上的版本化规范快照**：记录每个挂载业务项目在设计阶段和实现阶段已经被验证、审批并固化的事实，作为后续所有 AI 生成与门控验证的权威参照。

### 9.1 基线的核心定位

在 `sdd-assistant` Skill 的决策优先级规则中，基线的权威性被明确定义为：

```
真实基线（sdd-index-real.json） > 设计基线（sdd-index-design.json） > 通用知识
```

AI Agent 在执行任何设计生成或门控校验前，**必须优先查询基线**，而不得依赖自身的通用推断，从而确保生成结果"脚踏实地"，不与已有系统脱节。

---

### 9.2 基线目录结构

每个挂载的业务项目拥有独立的基线 **Bucket 目录**，存储于 `.spec/baselines/` 下，目录名由"项目名 + 项目根路径 SHA1 前 8 位"构成，确保全局唯一性：

```
.spec/
├── baseline/                          # SDD 工具自身的基线（自治基线）
└── baselines/
    ├── arc-web-a602642e/              # 业务项目 A 的基线 Bucket
    │   ├── sdd-index-design.json      # 设计基线索引
    │   ├── sdd-index-real.json        # 真实实现基线索引
    │   ├── 架构宪法.md                # 治理宪法（架构边界 + 上线检查清单）
    │   ├── 技术债卡.md               # 已知技术债务清单
    │   ├── module-map.json            # Java 源码模块图快照
    │   └── schema-context.json        # 数据库 Schema 上下文快照
    └── attached-sample-project-30095deb/  # 业务项目 B 的基线 Bucket
        └── ...（同上结构）
```

Bucket 名称由 `baseline_paths.py` 中的 `build_baseline_bucket_name()` 函数自动生成，以防止不同路径下的同名项目发生基线污染。

---

### 9.3 六大基线产物说明

| 产物 | 文件类型 | 内容与用途 |
| :--- | :--- | :--- |
| `sdd-index-design.json` | JSON | **设计基线索引**：记录所有经门控审批通过（`IMPLEMENTED` 状态）的设计意图条目，含 API 路径、设计文档引用、审批时间戳，供 Gate 2（设计真实性）比对 |
| `sdd-index-real.json` | JSON | **真实实现基线索引**：记录所有通过 Gate 5 并完成基线同步的功能，含已落地 API 路径、操作类型、数据库表名，是最高权威数据源 |
| `架构宪法.md` | Markdown | **治理宪法**：当前项目的架构边界规则、硬性约束和上线前检查清单，由 `refresh-baseline-governance` 命令生成 |
| `技术债卡.md` | Markdown | **技术债务清单**：影响未来设计、实现和发布决策的已知技术债，在设计生成阶段由 AI 参考 |
| `module-map.json` | JSON | **模块图快照**：扫描业务项目 `src/main/java` 和 `src/test/java` 后生成的 Java 类/方法结构图，支持 Gate 2（设计与代码一致性）和 Gate 5（实现覆盖率）的双向比对，含扫描器类型、置信度、来源签名、TTL 字段 |
| `schema-context.json` | JSON | **Schema 上下文快照**：融合 SQL 建表脚本与设计模型提取的数据库表结构，让 AI 在设计生成时能"看见"真实的数据库状态，支持 Gate 2 数据模型一致性验证 |

**重要约束**：`.spec/` 目录下的所有 JSON 索引文件**禁止手动编辑**，只允许工具链脚本写入。任何手动修改将破坏基线的完整性，并可能导致后续所有门控出现误判。

---

### 9.4 基线生命周期

基线通过以下四个阶段在流程中流转：

#### 阶段一：项目挂载与基线初始化

执行 `run_pipeline.py onboard-project` 时，工具链自动：

- 在 `.spec/baselines/` 下创建对应 Bucket 目录
- 初始化空的 `sdd-index-design.json` 和 `sdd-index-real.json`
- 生成初始 `架构宪法.md` 和 `技术债卡.md`

#### 阶段二：基线刷新（Refresh）

在设计生成前，需先刷新基线以获取最新项目状态：

| 刷新命令 | 作用 |
| :--- | :--- |
| `refresh-module-map` | 扫描业务项目 Java 源码，更新 `module-map.json` |
| `refresh-schema-context` | 扫描 SQL 文件与设计模型，更新 `schema-context.json` |
| `refresh-baseline-governance` | 重新生成 `架构宪法.md` 和 `技术债卡.md` |
| `refresh-baseline` | 以上三者的统一入口命令 |

基线文件均包含 `generated_at` 和 `ttl` 字段，`baseline_validators.py` 中的 `validate_baseline_freshness()` 函数会在每次门控执行前检测基线是否过期，过期则发出警告或阻断流程。

#### 阶段三：门控验证中的基线引用

| 门控引用的基线产物 | 验证内容 |
| :--- | :--- |
| Gate 2（设计真实性） | `module-map.json`、`schema-context.json` |
| 设计文档中的接口、实体是否与代码库和数据库现状一致 |
| Gate 5（实现覆盖率） | `module-map.json`、`sdd-index-design.json` |
| 任务切片中的每个任务是否有对应的 Java 实现类/方法存在 |

#### 阶段四：基线同步（Sync）

Gate 5 验证通过后，`sync_baseline.py` 中的 `sync_feature_to_baseline()` 函数自动执行基线提升：

1. 从设计包（`设计包/`）中提取资源清单：
   - `baseline_extractors.py` 解析 OpenAPI YAML → 提取 API 路径和操作类型
   - 解析 `数据模型.md` → 提取数据库表名和字段
   - 解析 `数据库变更.sql` → 提取 CREATE TABLE 语句
   - 解析 `异步事件契约.yaml` → 提取事件/Topic 名称
2. 将对应条目在 `sdd-index-design.json` 中标记为 `IMPLEMENTED`
3. 向 `sdd-index-real.json` 追加一条实现记录（含 API 路径、操作、表名、证据哈希等）
4. 写入时使用文件锁保证线程安全，并做幂等性检查防止重复同步

---

### 9.5 基线完整性保障机制

| 机制 | 实现位置 | 说明 |
| :--- | :--- | :--- |
| **新鲜度校验** | `baseline_validators.py` | 检测 `generated_at + ttl` 是否在有效期内，过期基线将触发警告或阻断 |
| **项目签名校验** | `baseline_validators.py` | 比对 Bucket 内存储的项目根路径签名与当前配置，检测项目迁移或误挂载 |
| **Schema 签名校验** | `baseline_validators.py` | 验证 `schema-context.json` 内容签名，防止 Schema 变更后基线未同步刷新 |
| **低置信度标记** | `baseline.py` `ModuleMapDocument` | 当模块图扫描结果置信度低时（`is_low_confidence`），门控报告中会特别标注 |
| **本地回退标记** | `baseline.py` `SchemaContextDocument` | 当无法访问真实数据库时使用本地 SQL 回退（`uses_local_fallback`），门控结果中注明 |

---

## 十、后续规划与扩展方向

根据项目文档（`sdd-architecture-improvement-backlog.md` 及 `sdd_汇报与试点优化方案.md`）：

1. **多项目并行支持**：当前已通过 Bucket 隔离机制支持多业务项目挂载，后续完善项目间依赖管理
2. **前端组件扫描**：当前 Gate 5 仅支持 Java，规划扩展至前端（TypeScript/Vue）代码库
3. **更多 AI 平台适配**：模板目录已预留 Codex、Gemini、OpenCode 等平台接入位
4. **PolyQuery 能力增强**：v1.2.0 已支持 6 类数据库，后续增加 Schema 变更感知与自动同步
5. **团队看板集成**：`task-board` PRD 已规划，将 SDD 任务切片与项目管理系统打通

---

## 十一、结语

SDD 项目将 AI 能力深度融合于研发团队的标准化流程治理中，不是简单地"用 AI 写代码"，而是通过结构化的门控体系、可审计的设计产物、自动化的合规验证，**让 AI 成为研发质量的守门员，而不仅仅是代码生成工具**。

该项目已在内部试点功能（`task-board`、`pilot-payment-review`）中完成端到端验证，具备向更大范围推广的条件。

---

*文档生成日期：2026-05-15 | 项目维护者：stardust_08*
