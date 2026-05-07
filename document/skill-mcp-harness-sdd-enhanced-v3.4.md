# AI SDD 自动化系统设计文档（增强版精简稿）
## 架构：Baseline + Feature Brief + Design Pack + Task Slice + Gates

**版本:** 3.4-enhanced  
**日期:** 2026-04-17  
**适用场景:** 存量 Java/Spring 工程，使用 AI 辅助完成需求澄清、技术设计、任务拆分、验证闭环。  
**文档定位:** 本文是增强版主规范，只保留流程骨架、关键产物、Gate 和实施口径。详细脚本、长示例和模板内容拆到配套文档中维护。  

---

## 1. 设计目标

本方案要解决三类问题：

1. AI 幻觉  
   类名、字段、接口、表结构与真实工程不一致。
2. 设计漂移  
   需求、设计、任务、测试、实现之间缺少追溯链。
3. 流程失控  
   高风险需求没有明确审批落点，横切工作容易被漏掉，验证时机不统一。

核心原则：

- **Baseline First**：AI 只能基于项目级事实来源生成内容。
- **Capability Driven**：模板、产物、门禁由 `capability_tags` 驱动，而不是只靠 `feature_type`。
- **Reviewable by Humans**：给人工审阅的文档必须可读、可讨论、可追责。
- **Traceable End-to-End**：需求、设计、任务、测试、实现之间必须可追溯。
- **Local First**：本地脚本是主触发源，CI 只做复核。

---

## 2. 当前版本中 Harness、Skill 和 MCP 的定位说明

虽然当前文档的主视角已经从早期的 `Skill + MCP + Harness` 三层表述，转向了 `Baseline + Feature Brief + Design Pack + Task Slice + Gates` 这套工作流表述，但三者在当前版本中依然存在，只是职责呈现方式发生了变化。

### 2.1 Harness 的定位

Harness 在当前版本中不再作为单独的“主角章节”出现，而是以内嵌的**流程控制层**存在，负责：

- 阶段推进规则
- 前置条件检查
- Gate 阻断逻辑
- 风险审批约束
- 状态迁移
- Baseline 同步时机

也就是说，当前文档里的这些内容本质上都属于 Harness：

- `Feature Brief -> Design -> Task Slice -> Verify` 的阶段流转
- Gate 1 / 2 / 3 / 4 / 5
- `risk_tier` 约束
- `reports/v{N}` 报告口径
- `sync_baseline.py` 的触发规则

### 2.2 Skill 的定位

Skill 在当前版本中承担的是**生成与解析能力封装层**，负责把 AI 能力沉淀成可复用的工作单元，例如：

- `requirement-analyzer`
  负责解析 PRD、抽取结构化信息
- `sdd-generation`
  负责生成设计文档、组装上下文、接入反馈重试

Skill 的职责重点是：

- Prompt 模板
- AI 调用逻辑
- 确定性校验脚本
- 阶段内的输入输出约束

### 2.3 MCP 的定位

MCP 在当前版本中承担的是**事实来源层**，负责把 AI 生成所需的真实上下文引入流程，例如：

- `project-explorer`
  提供类、包、方法签名和模块结构
- `polyquery`
  提供数据库实时元数据
- `arch-standard`
  提供架构规范和团队约束

MCP 的核心价值不是生成内容，而是提供“AI 不能凭空假设”的真实依据。

### 2.4 当前版本的关系总结

可以用一句话概括三者在当前版本中的关系：

- **Harness** 负责控流程
- **Skill** 负责出内容
- **MCP** 负责供事实

而 `Baseline / Feature Brief / Design Pack / Task Slice / Gates` 则是这三者协同作用后形成的工作流产物与控制面。

---

## 3. 总体工作流

```text
Feature Brief
  -> Draft Design
  -> Gate 1 / Gate 2 / Gate 3
  -> 风险审批（仅 High）
  -> 写入 sdd-index-design.json
  -> Task Slice
  -> Gate 4 测试骨架生成
  -> code 完成
  -> Gate 5 PRD 覆盖验证
  -> sync_baseline.py
  -> 写入 sdd-index-real.json
```

端到端数据流：

```text
用户输入 PRD / 需求单
  -> feature-brief.md
  -> design-v{N}.md + design-pack/
  -> Gate 1/2/3
  -> reports/v{N}/approval.json（High 风险）
  -> tasks/slice-NNN.md
  -> reports/v{N}/gate4-skeleton.json
  -> DesignVerificationTest.java
  -> reports/v{N}/verify-report.json
  -> sdd-index-real.json
```

---

## 3. Baseline：项目级唯一事实来源

```text
.spec/baseline/
├── sdd-index-design.json
├── sdd-index-real.json
├── module-map.json
├── schema-context.json
├── constitution.md
└── tech-debt.md
```

职责：

- `sdd-index-design.json`
  设计态冲突校验，避免并行需求在 API 路径、表名、事件名上撞车。
- `sdd-index-real.json`
  实现态真实基准，作为新一轮 AI 设计的主要事实来源。
- `module-map.json`
  类、包、方法签名快照。
- `schema-context.json`
  数据库元数据快照。

设计态索引状态：

- `ACTIVE`
- `SUPERSEDED`
- `CANCELLED`
- `IMPLEMENTED`

规则：

- 只有 `ACTIVE` 参与占位校验。
- 新版本设计发布后，旧 `ACTIVE` 条目转为 `SUPERSEDED`。
- 需求取消时转为 `CANCELLED`。
- Gate 5 通过且实现落地后转为 `IMPLEMENTED`。

维护原则：

- 设计态索引的归档/淘汰由开发者决定。
- 做出归档或淘汰决定时，必须同步更新相关索引状态与文档说明。

---

## 4. 棕地 / 绿地双模式兼容

当前工作流统一保留一套主流程，但通过 `project_mode` 区分两种工程场景：

- `brownfield`
  适用于存量 Java/Spring 工程，优先依赖真实 Baseline（现有类、现有表、现有接口）
- `greenfield`
  适用于新建工程，优先依赖规划型 Baseline（架构约束、模块布局、脚手架计划）

统一主流程不变：

`Feature Brief -> Draft Design -> Gate 1/2/3 -> 审批 -> Task Slice -> Gate 4 -> Gate 5 -> Baseline 同步`

补充说明：

- `project_mode=brownfield` 时，直接进入 `Feature Brief`
- `project_mode=greenfield` 时，建议先执行 `Phase 0 / Bootstrap`，再进入 `Feature Brief`

### 4.1 两种模式的差异

#### Brownfield

重点：

- 校验类、字段、接口、表结构是否真实存在
- 保证设计和存量系统兼容

依赖：

- `module-map.json`
- `schema-context.json`

#### Greenfield

重点：

- 先建立架构边界和脚手架
- 再生成功能设计
- 防止项目从第一天就形成错误结构

建议补充的规划型 Baseline：

- `constitution.md`
- `architecture.md`
- `module-layout.md`
- `bootstrap-plan.md`

### 4.2 `project_mode` 的判断机制

`project_mode` 允许由 agent 自动初判，但最终必须允许人工确认或覆盖。

原则：

- agent 负责“带证据的初判”
- 人负责“最终确认”

建议写入 `feature-brief.md`：

```yaml
project_mode: brownfield
project_mode_source: agent
project_mode_confidence: 0.82
project_mode_evidence:
  - "检测到现有 src/main/java 和大量 Java 类"
  - "检测到已有数据库表结构"
  - "检测到既有 Controller/Service/Repository"
project_mode_confirmed_by: zhangsan
```

规则：

- `confidence >= 0.8` 时，可给出默认建议
- `confidence < 0.8` 时，要求人工确认，或默认标记为 `hybrid`
- 允许开发者覆盖 agent 判断

### 4.3 Gate 2 的双模式含义

#### Brownfield 下的 Gate 2

重点校验：

- 类是否存在
- 字段是否存在
- 接口是否存在
- 表是否存在

#### Greenfield 下的 Gate 2

重点校验：

- 模块边界是否符合规划
- 命名是否符合规范
- 包结构是否符合架构
- 基础脚手架是否齐备

一句话：

- **Brownfield 验真实性**
- **Greenfield 验结构约束**

### 4.4 Greenfield 的 Phase 0 / Bootstrap 阶段

当 `project_mode=greenfield` 时，建议在正式进入 `Feature Brief` 前增加一个轻量的 `Phase 0 / Bootstrap` 阶段，用来先建立项目级约束和脚手架边界。

推荐产物：

- `constitution.md`
- `architecture.md`
- `module-layout.md`
- `bootstrap-plan.md`
- `scaffold-report.json`

职责：

- 确定技术栈和工程目录
- 定义模块边界和包结构
- 明确统一异常、日志、配置、监控等基础设施约束
- 初始化测试框架和基础工程脚手架

建议最小流程：

```text
greenfield
  -> Bootstrap / Architecture First
  -> Feature Brief
  -> Draft Design
  -> Gate 1 / Gate 2 / Gate 3
  -> Task Slice
  -> Gate 4 / Gate 5
```

与 Brownfield 的差异：

- Brownfield 依赖“真实存在的工程上下文”
- Greenfield 依赖“规划中的目标架构上下文”

因此在 Greenfield 模式下，Gate 2 的核心不是校验“类/字段是否存在”，而是校验：

- 模块划分是否符合规划
- 包结构是否符合架构
- 基础脚手架是否齐备
- 命名是否符合规范

说明：

- 当前版本仍以 Brownfield 为主场景
- 该 Bootstrap 阶段是兼容 Greenfield 的补充设计
- 后续若团队确实需要新建工程支持，可将其上升为正式主流程阶段

### 4.5 Greenfield 的 `feature-brief.md` 示例

当 `project_mode=greenfield` 时，`feature-brief.md` 建议体现“规划优先”的信息：

```yaml
project_mode: greenfield
project_mode_source: agent
project_mode_confidence: 0.88
project_mode_evidence:
  - "仓库中未检测到现有业务代码"
  - "未检测到既有数据库表和接口定义"
  - "需求描述包含初始化项目与基础模块搭建"
project_mode_confirmed_by: zhangsan

feature_name: order-center
feature_type: new-domain
one_liner: "新建订单中心服务，负责下单、查询和订单状态管理"

capability_tags:
  - api
  - db-change
  - idempotent

risk_tier: low

requirements:
  - req_id: REQ-001
    priority: P0
    description: "支持创建订单"
  - req_id: REQ-002
    priority: P0
    description: "支持查询订单详情"
```

### 4.6 Bootstrap 模板目录

为避免 Greenfield 场景下“脚手架规划”输出风格不一致，建议新增 Bootstrap 模板目录：

```text
.spec/templates/bootstrap/
├── constitution.template.md
├── architecture.template.md
├── module-layout.template.md
└── bootstrap-plan.template.md
```

这些模板的作用是：

- 统一 Greenfield 场景下的架构与脚手架输出结构
- 为 agent 提供固定骨架，避免缺少模块边界、基础设施、测试策略等关键章节
- 作为 Greenfield 下 Gate 2 的结构约束输入

---

## 5. Phase 1：Feature Brief

产物：`specs/{feature}/feature-brief.md`

最小结构：

```yaml
project_mode: brownfield
project_mode_source: agent
project_mode_confidence: 0.82
project_mode_evidence:
  - "检测到现有 src/main/java"
project_mode_confirmed_by: zhangsan

feature_name: order-create
feature_type: sync
one_liner: "用户下单后实时扣减库存并创建支付单"

capability_tags:
  - api
  - db-change
  - payment
  - idempotent

risk_tier: high

requirements:
  - req_id: REQ-001
    priority: P0
    description: "下单后库存实时扣减"
```

约束：

- 所有歧义必须以内联 `[AMBIGUOUS: ...]` 标记暴露。
- 进入 Phase 2 前，`[AMBIGUOUS]` 必须清零。
- `capability_tags` 非空。
- `requirements` 中至少有一个 `P0`。
- `project_mode` 已确认。

`risk_tier` 自动判定：

- `payment` -> `high`
- `async + db-change` -> `high`
- `security-sensitive` -> `high`
- `external-call + payment` -> `high`
- 其他 -> `low`

---

## 6. Phase 2：Design

Phase 2 分 4 步：

1. 生成 `design-v{N}.md`（Draft）  
   允许保存，不允许写设计态索引。
2. 执行 Gate 1 / Gate 2 / Gate 3  
   全部通过才进入审批。
3. 高风险审批  
   `risk_tier=high` 必须生成 `reports/v{N}/approval.json`。
4. 写入设计态索引  
   `risk_tier=low` 或审批通过后，才允许写入 `sdd-index-design.json`。

版本化报告目录：

```text
reports/
└── v{N}/
    ├── approval.json
    ├── gate-report.json
    ├── gate4-skeleton.json
    └── verify-report.json
```

规则：

- `design-v{N}.md` 对应 `reports/v{N}/`
- 旧版本报告只归档，不覆盖
- 脚本永远按“设计版本号 -> 报告目录”定位

---

## 6. Capability Tags 与 Design Pack

能力标签决定必须产出的设计包文件和必须执行的门禁规则。

| Tag | 强制产物 | 强制 Gate |
| --- | --- | --- |
| `db-change` | `数据模型.md`, `数据库变更.sql` | 字段真实性校验、回滚脚本校验 |
| `payment` | `支付状态机.md`, `对账策略.md` | 强制 Gate 3 审查事务边界与补偿 |
| `idempotent` | `幂等策略.md` | 校验唯一键/锁/状态机 |
| `async` | `异步事件契约.yaml` | 校验重试、死信、消费语义 |
| `external-call` | `外部调用策略.md` | 校验超时、重试、熔断 |
| `api` | `接口契约.openapi.yaml`, `接口文档.md` | 接口契约完整性校验；人工审阅内容完整性校验 |

`design-pack/` 目录：

```text
design-pack/
├── 接口契约.openapi.yaml
├── 接口文档.md
├── 数据模型.md
├── 数据库变更.sql
├── 幂等策略.md
├── 支付状态机.md
├── 对账策略.md
├── 异步事件契约.yaml
└── 外部调用策略.md
```

模板目录：

```text
.spec/templates/design-pack/
├── 接口文档.template.md
├── 数据模型.template.md
├── 幂等策略.template.md
├── 支付状态机.template.md
├── 对账策略.template.md
└── 外部调用策略.template.md
```

规则：

- 人工审阅类 Markdown 文档必须有模板。
- 机器优先产物如 `接口契约.openapi.yaml`、`数据库变更.sql`、`异步事件契约.yaml` 不强制 Markdown 模板。
- Gate 1 按 `capability_tags` 检查文件存在性、非空和最小结构。

---

## 7. Phase 3：Task Slice

Phase 3 不再只按业务序列图分支拆任务，而是采用：

- 垂直切片 `vertical slices`
- 横切任务 `cross-cutting slices`

最小切片结构：

```yaml
slice_id: SLICE-002-BIZ
depends_on: ["SLICE-001-INFRA"]
req_ids: ["REQ-001", "REQ-002"]
acceptance_checks:
  - "下单成功后 inventory.quantity 减少 orderQty"
test_spec:
  type: integration
  framework: junit5
```

要求：

- `req_ids` 必须能在 `feature-brief.md` 中找到。
- `acceptance_checks` 必须能映射回 `design-v{N}.md` 的验收矩阵。
- `test_spec` 是 Gate 4 的上游输入。

横切任务示例：

- `db-change` -> DDL 迁移、回滚验证
- `async` -> Topic/队列配置、死信配置
- `perf` -> 埋点、缓存预热、压测准备
- `external-call` -> 熔断、超时、降级配置

---

## 8. Gate 4：测试骨架生成

所有切片在拓扑序校验通过后，自动触发 Gate 4。

输入：

- `slice-NNN.md` 中的 `req_ids`
- `acceptance_checks`
- `test_spec`
- `design-v{N}.md` 的接口契约、异常处理、验收矩阵

输出：

- `reports/v{N}/gate4-skeleton.json`
- `src/test/java/.../design/{feature}DesignVerificationTest.java`

作用：

- 建立 `REQ-ID -> Test Method` 映射
- 生成待开发者补全断言的测试骨架

---

## 9. Gate 5：PRD 覆盖验证

触发时机：

- **唯一主触发源为本地** `python scripts/run_pipeline.py gate5 <feature>`
- CI 只做复核，不作为主触发源
- 若 CI 检测不到 `reports/v{N}/verify-report.json`，直接报错

检查逻辑：

1. 读取 `reports/v{N}/gate4-skeleton.json`
2. 扫描测试文件，检查 TODO 是否已消除
3. 运行测试，收集结果
4. P0 测试未实现或失败 -> 硬阻断 code 完成确认
5. P1 遗漏 -> 写入 `reports/v{N}/verify-report.json`

通过后自动执行：

- `sync_baseline.py`
- `sdd-index-design.json` 中对应条目更新为 `IMPLEMENTED`
- 将接口/表/版本写入 `sdd-index-real.json`

---

## 10. Release Gate

上线前仍需确认：

- 回滚方案已就绪
- 监控与告警已配置
- 灰度策略已确认

---

## 11. 推荐目录结构

```text
repo-root/
├── AGENTS.md
├── ARCHITECTURE.md
├── .spec/
│   ├── baseline/
│   │   ├── sdd-index-design.json
│   │   ├── sdd-index-real.json
│   │   ├── module-map.json
│   │   ├── schema-context.json
│   │   ├── constitution.md
│   │   └── tech-debt.md
│   └── templates/
│       └── design-pack/
├── specs/{feature}/
│   ├── feature-brief.md
│   ├── design-v1.md
│   ├── design-pack/
│   ├── tasks/
│   └── reports/
│       └── v1/
├── scripts/
├── skills/
└── mcp-servers/
```

---

## 12. 实施顺序

### P0：主流程对齐

- 统一阶段命名
- 统一 `reports/v{N}/...`
- 明确 Gate 5 本地触发、CI 只复核
- 明确 Gate 4、Gate 5 与 Baseline 的时序关系

### P1：治理前置层落地

- 新增 `feature-brief.md`
- 引入 `capability_tags`
- 引入 `risk_tier`
- 引入 `[AMBIGUOUS]`

### P2：设计产物拆分层落地

- 拆出 `design-pack`
- 接入模板目录
- 让 Gate 1 按 `capability_tags` 检查产物

### P3：任务切片与验证闭环落地

- 引入 `slice-NNN.md`
- 增加 `depends_on / req_ids / acceptance_checks / test_spec`
- 用切片驱动 Gate 4 / Gate 5

### P4：双态 Baseline 与审批闭环

- 落地 `sdd-index-design.json`
- 落地 `sdd-index-real.json`
- 引入 `reports/v{N}/approval.json`
- 实现 `sync_baseline.py`

### P5：稳态运行与运营化

- 建立决策项维护机制
- 为 `reports/v{N}/` 定义 JSON schema
- 为 `design-pack` 的 YAML/SQL 文件增加 schema 或 lint 规则

---

## 13. 实施检查清单

### 13.1 P0 检查清单

- [ ] 主流程章节口径与 v3.4 一致
- [ ] `reports/v{N}/` 目录结构进入主文档
- [ ] Gate 5 触发时机已改为“code 完成时本地触发”

### 13.2 P1 检查清单

- [ ] 落地 `feature-brief.md`
- [ ] `requirement-analyzer` 输出 `capability_tags`
- [ ] `risk_tier` 自动判定规则可执行
- [ ] `[AMBIGUOUS]` 清零前不能进入设计阶段

### 13.3 P2 检查清单

- [ ] `design-pack` 文件有固定落点
- [ ] `.spec/templates/design-pack/` 已落地
- [ ] Gate 1 能校验设计包存在性与最小结构

### 13.4 P3 检查清单

- [ ] `slice-NNN.md` 模型落地
- [ ] 切片包含 `depends_on / req_ids / acceptance_checks / test_spec`
- [ ] Gate 4 能从切片生成测试骨架
- [ ] Gate 5 能基于切片 REQ-ID 做覆盖验证

### 13.5 P4 检查清单

- [ ] 双态索引可读写
- [ ] 高风险设计无审批文件时不能写设计态索引
- [ ] Gate 5 通过后自动同步实现态索引

### 13.6 P5 检查清单

- [ ] `reports/v{N}` schema 明确
- [ ] 模板版本管理策略明确
- [ ] 决策项维护机制建立

---

## 14. 配套文档

以下文档继续作为本增强版的细节参考：

- `D:\project\SDD\skill-mcp-harness-sdd.md`
  原始详细版，保留大量脚本、示例和落地经验
- `D:\project\SDD\design-pack-模板清单.md`
  design-pack 模板规则和模板内容
- `D:\project\SDD\v3.4-实施路线图.md`
  演进步骤、阶段目标和实施顺序

---

## 15. 一句话结论

本增强版不是替换原文，而是：

**在保留现有实现细节的前提下，把缺失的 v3.4 能力统一补成一层可落地的目标规范。**
