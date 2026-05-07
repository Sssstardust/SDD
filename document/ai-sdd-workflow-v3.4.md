# AI SDD 混合版自动化工作流 (v3.4)

## 0. 设计目标

这份文档是基于现有 `fix.md` 的独立整理版，目标是形成一套更适合 Java/Spring 棕地项目的 AI 驱动 SDD 工作流。

核心目标：

- 用 Baseline 作为唯一事实来源，减少 AI 幻觉
- 用 `capability_tags` 驱动产物和门禁，而不是只依赖 `feature_type`
- 用版本化审批与门禁报告，保证过程可追溯
- 用“垂直切片 + 横切任务”共同驱动实现，而不是只按业务分支拆任务
- 在 code 完成时自动触发 PRD 覆盖验证，形成设计到实现闭环

---

## 1. Baseline：项目级唯一事实来源

Baseline 是 AI 的长期记忆与运行时上下文来源。

```text
.spec/baseline/
├── sdd-index-design.json      # 设计态索引（仅存已审批通过的设计意图）
├── sdd-index-real.json        # 实现态索引（仅存已真实落地的接口/实体）
├── module-map.json            # 现有类、包、方法签名快照
├── schema-context.json        # 数据库元数据快照
├── constitution.md            # 架构红线
└── tech-debt.md               # 已知技术债
```

### 1.1 设计态索引生命周期

`sdd-index-design.json` 的每条记录必须具备生命周期字段：

```json
{
  "intent_id": "order-create-api-v2",
  "feature": "order-create",
  "design_version": "design-v2.md",
  "status": "ACTIVE",
  "approved_at": "2026-04-17T09:00:00Z",
  "paths": ["POST /api/v2/orders"],
  "tables": ["t_order"],
  "superseded_by": null
}
```

状态取值：

- `ACTIVE`
- `SUPERSEDED`
- `CANCELLED`
- `IMPLEMENTED`

规则：

- 只有 `ACTIVE` 状态参与排他性冲突校验
- 新版本设计发布后，旧的 `ACTIVE` 条目自动转为 `SUPERSEDED`
- 需求取消时，设计条目转为 `CANCELLED`
- Gate 5 通过且实现落地后，设计条目转为 `IMPLEMENTED`

### 1.2 双索引分工

- `sdd-index-design.json`
  作用：设计态冲突校验，避免并行需求在 API 路径、表名、事件名上撞车
- `sdd-index-real.json`
  作用：实现态真实基准，作为新一轮 AI 设计的主要事实来源

---

## 2. Phase 1：Feature Brief

Phase 1 负责定义意图、识别风险、清理歧义。

产物：`specs/{feature}/feature-brief.md`

### 2.1 必填字段

```yaml
feature_name: order-create
feature_type: sync
one_liner: "用户下单后实时扣减库存并创建支付单"

capability_tags:
  - db-change
  - payment
  - idempotent

risk_tier: high

requirements:
  - req_id: REQ-001
    priority: P0
    description: "下单后库存实时扣减"
  - req_id: REQ-002
    priority: P0
    description: "支付超时 30min 取消订单"
  - req_id: REQ-003
    priority: P1
    description: "重复提交幂等保护"
```

### 2.2 `[AMBIGUOUS]` 内联机制

AI 识别到不确定点时，必须内联标注：

```markdown
- 下单后扣减库存 [AMBIGUOUS: 是预扣还是实扣？超卖时拒绝下单还是允许负库存？]
- 支付超时取消订单 [AMBIGUOUS: 超时时长由谁配置？取消后库存是否回滚？]
```

### 2.3 风险定级

Harness 自动判定 `risk_tier`，人工只能升级不能降级：

- 有 `payment` 标签 -> `high`
- 同时有 `async + db-change` -> `high`
- 有 `security-sensitive` -> `high`
- 同时有 `external-call + payment` -> `high`
- 其他默认 `low`

### 2.4 Phase 1 进入条件

进入 Phase 2 之前必须满足：

- 不存在任何 `[AMBIGUOUS:` 标记
- `capability_tags` 非空
- `requirements` 中至少有一个 `P0`

---

## 3. Phase 2：Design

Phase 2 拆成 4 个步骤，避免审批和设计形成自循环。

### 3.1 Step 1：生成 Draft 设计

输出：`design-v{N}.md`

此时状态为 `Draft`，只允许保存，不允许写入 `sdd-index-design.json`。

### 3.2 Step 2：执行 Gate 1 / Gate 2 / Gate 3

- Gate 1：结构完整性
- Gate 2：真实性校验
- Gate 3：架构语义审计

只有全部通过，设计才进入审批阶段。

### 3.3 Step 3：高风险版本化审批

若 `risk_tier=high`，则必须生成：

`reports/v{N}/approval.json`

```json
{
  "design_version": "design-v1.md",
  "feature": "order-create",
  "risk_tier": "high",
  "status": "APPROVED",
  "approved_by": "张三",
  "approved_at": "2026-04-17T10:00:00Z",
  "comments": "事务边界已确认，幂等键方案通过"
}
```

规则：

- 审批对象是已经通过 Gate 1/2/3 的 `design-v{N}.md`
- 每个版本必须独立审批
- `reports/v1/approval.json` 不能复用于 `design-v2.md`

### 3.4 Step 4：写入设计态索引

仅当满足以下条件时，才允许调用 `update_index_design.py`：

- `risk_tier=low`
- 或 `reports/v{N}/approval.json.status == APPROVED`

写入后：

- `design-v{N}.md` 状态更新为 `Approved`
- 相同 `feature` 的旧 `ACTIVE` 条目自动转为 `SUPERSEDED`

### 3.5 报告命名约定

所有报告与设计版本强绑定，并按版本目录隔离：

- `design-v1.md` -> `reports/v1/gate-report.json`
- `design-v1.md` -> `reports/v1/approval.json`
- `design-v1.md` -> `reports/v1/gate4-skeleton.json`
- `design-v1.md` -> `reports/v1/verify-report.json`

约定：

- `design-v{N}.md` 对应 `reports/v{N}/`
- 旧版本报告只归档，不覆盖
- 脚本永远按“设计版本号 -> 报告目录”定位，不通过模糊文件名猜测

---

## 4. Capability Tags 治理矩阵

`capability_tags` 决定必须产出的设计包文件和必须执行的门禁规则。

| Tag | 强制产物 | 强制 Gate |
| --- | --- | --- |
| `db-change` | `数据模型.md`, `数据库变更.sql` | 字段真实性校验、回滚脚本校验 |
| `payment` | `支付状态机.md`, `对账策略.md` | 强制 Gate 3 审查事务边界与补偿 |
| `idempotent` | `幂等策略.md` | 校验唯一键/锁/状态机 |
| `async` | `异步事件契约.yaml` | 校验重试、死信、消费语义 |
| `external-call` | `外部调用策略.md` | 校验超时、重试、熔断 |
| `api` | `接口契约.openapi.yaml`, `接口文档.md` | 接口契约完整性校验；人工审阅内容完整性校验 |

### 4.1 设计包命名约定

为了兼顾可读性和脚本可定位性，`design-pack/` 采用“语义名称 + 明确后缀”的命名方式：

- 契约文件：中文语义名 + `.yaml`
- 策略文件：中文语义名 + `.md`
- 状态机文件：中文语义名 + `.md`
- 迁移脚本：中文语义名 + `.sql`
- 模型文件：中文语义名 + `.md`

说明：

- `design-pack/` 下的文件主要给人看，优先采用中文命名
- `reports/`、脚本、自动生成产物继续保留英文命名，避免实现复杂度上升

推荐命名：

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

### 4.2 人工审阅文档模板规则

凡是主要给人审阅、以 Markdown 为主的 `design-pack` 文档，都必须有一份对应模板文件，用于约束 agent 输出结构，避免不同需求之间的文档风格和章节粒度漂移。

**模板目录位置：**

```text
.spec/templates/design-pack/
├── 接口文档.template.md
├── 数据模型.template.md
├── 幂等策略.template.md
├── 支付状态机.template.md
├── 对账策略.template.md
└── 外部调用策略.template.md
```

说明：

- Agent 生成人工审阅文档时，必须以对应模板为骨架补全内容
- 模板定义的是章节结构和最小信息集，不要求固定具体文案
- 机器优先产物如 `接口契约.openapi.yaml`、`数据库变更.sql` 继续按标准 schema/脚本规范生成，不强制使用 Markdown 模板

### 4.3 design-pack 文件清单

| 文件名 | 推荐格式 | 最小必填字段/章节 | 模板文件 | 对应 Gate |
| --- | --- | --- | --- | --- |
| `接口契约.openapi.yaml` | YAML(OpenAPI 3.x) | `openapi`, `info`, `paths`, `operationId`, `responses` | 无，遵循 OpenAPI schema | Gate 1、Gate 2、Gate 4 |
| `接口文档.md` | Markdown | 接口清单、调用方、业务说明、关键请求字段、关键响应字段、错误码说明 | `.spec/templates/design-pack/接口文档.template.md` | Gate 1、人工评审 |
| `数据模型.md` | Markdown | 实体/表映射、字段清单、索引说明、影响分析 | `.spec/templates/design-pack/数据模型.template.md` | Gate 1、Gate 2 |
| `数据库变更.sql` | SQL | `-- UP`、`-- DOWN/ROLLBACK`、关键变更注释 | 无，遵循 SQL 迁移规范 | Gate 1、Release Gate |
| `幂等策略.md` | Markdown | 场景说明、幂等键、冲突处理、存储/TTL | `.spec/templates/design-pack/幂等策略.template.md` | Gate 1、Gate 3 |
| `支付状态机.md` | Markdown | 状态列表、状态转移、触发条件、终态、补偿策略 | `.spec/templates/design-pack/支付状态机.template.md` | Gate 1、Gate 3 |
| `对账策略.md` | Markdown | 对账对象、对账维度、对账频率、差异处理 | `.spec/templates/design-pack/对账策略.template.md` | Gate 1、Gate 3 |
| `异步事件契约.yaml` | YAML | `event/topic`, `producer`, `consumer`, `payload schema`, `retry`, `dlq` | 无，遵循事件契约 schema | Gate 1、Gate 3 |
| `外部调用策略.md` | Markdown | 调用方/被调方、超时、重试、熔断、降级 | `.spec/templates/design-pack/外部调用策略.template.md` | Gate 1、Gate 3 |

### 4.4 Gate 1 执行方式

Gate 1 根据 `feature-brief.md` 的 `capability_tags` 检查：

- 对应文件是否存在
- 对应文件是否非空
- 关键字段是否具备最小结构
- 若文件属于人工审阅文档，还需校验其章节结构是否满足对应模板的最小要求

---

## 5. Phase 3：Task Slice

Phase 3 不再只按业务序列图分支拆任务，而是采用：

- 垂直切片 `vertical slices`
- 横切任务 `cross-cutting slices`

### 5.1 垂直切片

来自 `design-v{N}.md` 的业务路径和主/异常流程分支。

用途：

- 拆业务流实现
- 保证端到端场景闭环

### 5.2 横切任务

来自 `capability_tags` 自动触发。

示例：

- `db-change` -> DDL 迁移、回滚验证
- `async` -> Topic/队列配置、死信配置
- `perf` -> 埋点、缓存预热、性能压测准备
- `external-call` -> 熔断、超时、降级配置
- `security-sensitive` -> 权限、审计、脱敏

### 5.3 依赖模型

每个切片必须包含 `depends_on`：

```yaml
slice_id: SLICE-002-BIZ
depends_on: ["SLICE-001-INFRA"]
req_ids: ["REQ-001", "REQ-002"]
acceptance_checks:
  - "下单成功后 inventory.quantity 减少 orderQty"
  - "支付超时 30min 后订单状态变为 CANCELLED"
test_spec:
  type: integration
  framework: junit5
  target_class: OrderServiceTest
  cases:
    - id: TC-001
      req_id: REQ-001
      description: "下单后库存扣减验证"
    - id: TC-002
      req_id: REQ-002
      description: "支付超时取消验证"
```

### 5.4 追溯要求

每个切片必须具备：

- `req_ids`
- `acceptance_checks`
- `test_spec`

约束：

- `req_ids` 必须能在 `feature-brief.md` 中找到
- `acceptance_checks` 必须能映射回 `design-v{N}.md` 的验收矩阵
- `test_spec` 是 Gate 4 生成测试骨架的上游输入

---

## 6. Gate 4：测试骨架生成

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

## 7. Gate 5：PRD 覆盖验证

### 7.1 触发时机

**code 完成时自动触发**

唯一触发源：

- 本地 `python scripts/run_pipeline.py gate5 <feature>`

CI 角色：

- CI 只做复核，不作为 Gate 5 的主触发源
- 若 CI 发现缺少 `reports/v{N}/verify-report.json`，应直接报错，表示开发者未完成本地 Gate 5

### 7.2 检查逻辑

1. 读取 `reports/v{N}/gate4-skeleton.json`
2. 扫描测试文件，检查 TODO 是否已消除
3. 运行测试，收集结果
4. P0 测试未实现或失败 -> 硬阻断 code 完成确认
5. P1 遗漏 -> 记录到 `reports/v{N}/verify-report.json`，警告但不阻断

### 7.3 通过后的自动动作

Gate 5 通过后自动执行 `sync_baseline.py`：

- 找到 `sdd-index-design.json` 中对应 `ACTIVE` 条目
- 更新为 `IMPLEMENTED`
- 将接口/表/版本写入 `sdd-index-real.json`
- 写入 `reports/v{N}/verify-report.json`

---

## 8. Release Gate

上线前仍需确认：

- 回滚方案已就绪
- 监控与告警已配置
- 灰度策略已确认

---

## 9. 推荐目录结构

```text
specs/{feature}/
├── feature-brief.md
├── design-v1.md
├── design-pack/
│   ├── 接口契约.openapi.yaml
│   ├── 接口文档.md
│   ├── 数据模型.md
│   ├── 数据库变更.sql
│   ├── 幂等策略.md
│   ├── 支付状态机.md
│   ├── 对账策略.md
│   ├── 异步事件契约.yaml
│   └── 外部调用策略.md
├── tasks/
│   ├── slice-001-infra.md
│   └── slice-002-biz.md
└── reports/
    ├── v1/
    │   ├── approval.json
    │   ├── gate-report.json
    │   ├── gate4-skeleton.json
    │   └── verify-report.json
    └── v2/
        ├── approval.json
        ├── gate-report.json
        ├── gate4-skeleton.json
        └── verify-report.json

.spec/
└── templates/
    └── design-pack/
        ├── 接口文档.template.md
        ├── 数据模型.template.md
        ├── 幂等策略.template.md
        ├── 支付状态机.template.md
        ├── 对账策略.template.md
        └── 外部调用策略.template.md
```

---

## 10. 端到端追溯链

```text
feature-brief.md
  -> design-v{N}.md
  -> slice-NNN.md
  -> reports/v{N}/gate4-skeleton.json
  -> DesignVerificationTest.java
  -> reports/v{N}/verify-report.json
  -> sdd-index-real.json
```

这条链保证：

- 每个需求都能追到设计
- 每个设计都能追到任务
- 每个任务都能追到测试
- 每个测试结果都能回流到 Baseline

---

## 11. Open Questions / 待决策项

以下事项暂不在当前版本定案，保留为后续团队评审的明确议题。

### TODO-DISCUSS-001：design-pack 文件命名是否统一采用“业务对象前缀”

当前现状：

- 文档中已采用中文语义命名，如 `支付状态机.md`、`对账策略.md`
- 该方案有助于提升可读性，并减少同类文件歧义

待讨论问题：

- 是否所有同类文档都必须采用“业务对象 + 文档类型”的命名方式
- 例如 `支付状态机.md` 是否应优于 `状态机.md`

评估维度：

- 可读性
- 唯一性
- 脚本映射复杂度
- 后续扩展性

当前处理原则：

- 先保留现有命名，不在当前版本进一步收紧规则
- 待团队评审后，再决定是否将其上升为强制命名规范

### TODO-DISCUSS-002：`feature_type` 与 `capability_tags` 的职责边界

当前现状：

- 当前流程同时保留了 `feature_type` 和 `capability_tags`
- 其中 `capability_tags` 已经承担了主要的设计包与 Gate 驱动职责

待讨论问题：

- `feature_type` 是否继续保留为一等字段
- 还是仅把它作为统计、展示、业务归类字段
- 是否允许未来完全由 `capability_tags` 驱动模板和门禁

评估维度：

- 业务可理解性
- 模板驱动精度
- 风险分级准确率
- 实现复杂度

当前处理原则：

- 当前版本保留 `feature_type`
- 但模板和 Gate 继续优先由 `capability_tags` 驱动

### DECIDED-003：Gate 5 的自动触发源以本地为准

已定规则：

- Gate 5 的唯一触发源为本地 `python scripts/run_pipeline.py gate5 <feature>`
- 开发者在确认 code 完成时，必须先执行本地 Gate 5
- Gate 5 通过前，不允许进入提交流程
- CI 只承担复核职责，不作为主触发源
- 若 CI 检测不到 `reports/v{N}/verify-report.json`，直接判定流程未完成

保留原因：

- 流程简单，团队执行成本更低
- 审计口径单一，避免本地与 CI 双真相冲突
- 更符合“先本地验证，再提交代码”的开发习惯

### TODO-DISCUSS-004：横切任务是否需要独立 blocker 级别

当前现状：

- 文档已经区分了垂直切片与横切任务
- 但横切任务是否一律作为阻断项，还没有完全定死

待讨论问题：

- `db-change`、`async`、`security-sensitive` 这类横切任务是否默认 blocker
- `perf`、`cache`、`external-call` 是否允许按风险等级决定 blocker 与否
- 不同标签的横切任务是否需要标准优先级矩阵

评估维度：

- 发布安全性
- 实现顺序稳定性
- 团队任务拆分复杂度

当前处理原则：

- 当前示例中基础设施切片默认为 blocker
- 其余横切任务的 blocker 级别留待团队规则进一步明确

### DECIDED-005：设计态索引记录的归档/淘汰由开发者决定

已定规则：

- `sdd-index-design.json` 的归档或淘汰不做自动策略
- 由开发者在实际维护中主动决定是否归档、淘汰或保留历史记录
- 一旦开发者做出归档/淘汰决定，必须同步更新相关文档和索引状态，不能只删除单一条目

执行要求：

- 若决定淘汰某条设计意图：
  - 将对应条目状态更新为 `CANCELLED` 或移入归档文件
  - 同步检查 `superseded_by`、`design_version`、`intent_id` 等关联字段是否仍然有效
  - 同步更新相关设计文档的状态说明，避免索引与文档语义不一致
- 若决定归档某一批历史记录：
  - 由开发者将记录迁移到独立归档文件
  - 主索引中不再保留这些记录参与日常占位校验
  - 归档后仍需保证可追溯，不能破坏历史版本定位

当前处理原则：

- 当前版本默认保留全部历史状态记录
- 当开发者明确决定归档或淘汰时，再对相关文档与索引执行人工维护操作
