# AI SDD Workflow Blueprint

## 1. 目标

这份蓝图用于定义一套更适合 Java/Spring 棕地项目的 AI 驱动规范开发流程。

目标不是照搬 spec-kit，而是在保留其方法论优点的前提下，落地一套更适合团队实际协作的工作流：

- 先明确需求和治理原则，再进入设计和编码
- 用结构化产物替代“一份超级大文档”
- 用能力标签驱动必填章节和质量门禁
- 在编码前就生成验证骨架，而不是编码后补验证
- 保证需求、设计、任务、代码、测试之间可追溯

## 2. 设计原则

- Intention First：先定义“做什么”和“为什么”，再定义“怎么做”
- Small Verifiable Steps：每一阶段都必须有明确产物和可验证出口
- Capability Driven：流程和模板由能力标签驱动，而不是只靠单一 feature_type
- Human Review by Default：AI 负责草拟和加速，人负责批准和守门
- Traceability First：每个设计、任务、测试都要能追到对应 REQ-ID

## 3. 核心对象

每个需求在进入主流程前，先生成两类核心元数据。

### 3.1 风险等级

- `risk_tier=low`
- `risk_tier=medium`
- `risk_tier=high`

### 3.2 能力标签

建议最少支持以下标签：

- `api`
- `db-change`
- `async`
- `batch`
- `external-call`
- `payment`
- `cache`
- `idempotent`
- `perf`
- `security-sensitive`

说明：

- `feature_type` 仍可保留，用于业务归类
- 实际章节要求、质量门禁、测试骨架，应由 `capability_tags` 驱动

## 4. 主流程

### Stage 0: Constitution

产物：`constitution.md`

作用：定义团队级不可违背规则。

建议只保留 3-5 条核心原则，例如：

- 代码质量与分层原则
- 测试标准与覆盖要求
- 性能红线
- 安全与审计要求
- 文档语言与评审要求

### Stage 1: Specify

产物：`spec.md`

作用：只描述“做什么、为什么、怎么验收”。

内容建议：

- 业务目标
- 用户故事
- 边界与非目标
- 非功能需求
- 验收标准
- 未决问题

要求：

- 不把技术实现细节提前写进 `spec.md`
- `spec.md` 必须经过人工审阅后，才能进入下一阶段

### Stage 2: Clarify

产物：

- `clarify.md`
- `requirements-checklist.md`

作用：消除模糊需求，补足缺失信息。

输出内容建议：

- 未决问题清单
- 需要业务确认的假设
- 对需求文档的修订记录
- 需求是否允许进入设计阶段的结论

规则：

- 未决问题未清零，不允许进入设计阶段

### Stage 3: Plan

产物：

- `research.md`
- `plan.md`

作用：确定技术实现方案。

`research.md` 建议包含：

- 技术选型
- 替代方案
- 风险点
- 外部依赖
- 已知约束

`plan.md` 建议包含：

- 架构蓝图
- 模块拆分
- 关键流程
- 技术边界
- 与现有系统的集成方式

### Stage 4: Design Pack

产物：

- `design.md`
- `contracts/openapi.yaml`
- `data-model.md`
- `rollout.md`
- `security.md`

作用：把设计拆成可审阅、可校验、可驱动实现的产物包。

建议职责分工：

- `design.md`
  核心设计、流程、异常处理、架构约束
- `contracts/openapi.yaml`
  API 或事件契约
- `data-model.md`
  实体、表结构、索引、迁移策略
- `rollout.md`
  灰度、回滚、数据修复、上线步骤
- `security.md`
  鉴权、权限、脱敏、审计

### Stage 5: Tasks

产物：`tasks.md`

作用：把设计拆成可执行任务。

每个任务建议至少包含：

- `TASK-ID`
- `REQ-ID`
- 任务描述
- 前置依赖
- 风险等级
- 负责人
- 测试类型

### Stage 6: Analyze

产物：`analyze-report.md`

作用：检查需求、设计、任务三者的一致性和覆盖率。

检查项建议：

- 有没有未覆盖的 REQ-ID
- 有没有重复任务
- 有没有设计存在但任务缺失
- 有没有高风险能力标签却缺对应章节

### Stage 7: Implement

产物：

- 源代码
- 迁移脚本
- `implement-notes.md`

作用：按任务实施。

要求：

- 不允许跳过任务直接整包编码
- AI 产出必须能映射回 `TASK-ID`
- 人负责审阅与纠偏

### Stage 8: Verify

产物：

- 测试骨架
- 测试报告
- 覆盖报告
- `gate-report.json`

作用：验证代码是否符合设计和需求。

这里保留现有文档中 Gate 4 / Gate 5 的方向，并把它正式并入流程。

### Stage 9: Release Review

产物：`release-checklist.md`

作用：上线前确认交付安全。

检查项建议：

- 回滚方案
- 监控项
- 告警项
- 数据修复方案
- 灰度策略
- 风险确认

## 5. 能力标签驱动规则

### `api`

必须具备：

- `contracts/openapi.yaml`
- 接口测试骨架
- 错误码定义

### `db-change`

必须具备：

- `data-model.md`
- 迁移脚本
- 回滚脚本
- 数据校验方案

### `async`

必须具备：

- 消息契约
- 重试策略
- 死信策略
- 补偿策略

### `external-call`

必须具备：

- 超时策略
- 重试策略
- 熔断/降级策略
- 幂等说明

### `payment`

必须具备：

- 状态机
- 对账方案
- 资金一致性说明
- 补偿机制

### `cache`

必须具备：

- Key 设计
- TTL
- 失效策略
- 一致性说明

### `idempotent`

必须具备：

- 幂等键
- 唯一约束或状态机方案
- 重试行为说明

### `perf`

必须具备：

- 性能目标
- 压测方案
- 资源约束

## 6. Gate 设计

### Gate 0: Input Quality

检查对象：

- `spec.md`
- `clarify.md`

检查点：

- 未决问题是否清零
- 必填需求是否完整

### Gate 1: Design Structure

检查对象：

- `design pack`

检查点：

- 必填产物是否存在
- 必填章节是否完整
- 能力标签要求是否满足

### Gate 2: Truthfulness

检查对象：

- 类名
- 方法
- 字段
- 接口路径
- 表结构

检查点：

- 类名存在性
- 方法签名存在性
- 字段存在性
- 表/字段与上下文一致性

### Gate 3: Architecture Compliance

检查对象：

- `design.md`

检查点：

- 分层
- 事务边界
- 异常处理
- 命名
- 依赖方向

### Gate 4: Test Skeleton Generation

根据：

- `contracts/openapi.yaml`
- `design.md`
- `REQ-ID`

生成：

- 测试骨架
- `REQ-ID -> Test` 映射

### Gate 5: Requirement Coverage

检查：

- P0 需求是否全部被测试覆盖
- TODO 是否已清除
- 测试是否通过

### Gate 6: Release Safety

检查：

- 回滚
- 灰度
- 监控
- 告警
- 数据修复

## 7. 状态流转

建议状态机：

- `Draft`
- `Clarified`
- `Planned`
- `Designed`
- `Approved`
- `Implementing`
- `Verified`
- `Released`

每个版本建议固化以下元数据：

- `status`
- `reviewer`
- `gate-report.json`
- `source spec version`
- `design version`
- `prompt/rule version`

## 8. 推荐目录结构

```text
repo-root/
├── .specify/
│   ├── memory/
│   │   └── constitution.md
│   ├── templates/
│   └── scripts/
├── docs/
│   └── features/{feature}/
│       ├── spec.md
│       ├── clarify.md
│       ├── requirements-checklist.md
│       ├── research.md
│       ├── plan.md
│       ├── design-v1.md
│       ├── data-model.md
│       ├── rollout.md
│       ├── security.md
│       ├── contracts/
│       │   └── openapi.yaml
│       ├── tasks.md
│       ├── analyze-report.md
│       ├── design-v1-gate-report.json
│       ├── test-skeleton-report.json
│       ├── gate5-report.json
│       └── implement-notes.md
├── scripts/
├── skills/
├── mcp-servers/
└── .harness/
```

## 9. 推荐落地顺序

### P0

先建立工作流骨架：

- 新增 `constitution.md`
- 从当前 `design` 体系中拆出 `spec.md`
- 引入 `risk_tier + capability_tags`
- 固化 `status + reviewer + gate-report`

### P1

补齐中间产物层：

- 新增 `clarify.md`
- 新增 `research.md`
- 新增 `plan.md`
- 新增 `tasks.md`
- 新增 `analyze-report.md`
- 用 `capability_tags` 驱动模板和 gate
- 补方法/字段真实性校验

### P2

把实现与验证正式并入主流程：

- 新增 `implement-notes.md`
- 把 Gate 4 / Gate 5 正式纳入实现闭环
- 增加构建、测试、发布前检查
- 建立 `REQ-ID -> Task -> Code -> Test` 的完整追溯链

## 10. 一句话总结

这套蓝图的核心不是“再写一份更大的 SDD 模板”，而是把流程重构成：

`constitution -> spec -> clarify -> plan -> design pack -> tasks -> analyze -> implement -> verify -> release`

如果当前文档继续沿这个方向演进，它就会从“设计治理框架”升级成一套真正可执行的“规范驱动开发框架”。
