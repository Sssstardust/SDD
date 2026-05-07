# SDD 架构补充完善清单

本文档记录当前 SDD 工具链在真实团队落地前需要补充、完善和明确的架构点。目标不是否定现有方向，而是把当前 MVP 与生产级治理之间的差距显式化，便于后续按优先级演进。

## 1. 总体判断

当前项目已经具备基础流程编排、Design Pack 校验、Baseline 快照、双态索引、MCP 接入和 Gate 报告能力，但更适合作为试点工具链。

在推广到真实业务团队前，需要重点补强四类能力：

- 流程成本控制：避免小团队被完整 SDD 模板压垮。
- 事实源可信度：明确 MCP、数据库、源码扫描、设计文档的可信等级。
- 多模块边界：支持多服务、多技术栈、多数据源下的 Baseline 隔离与冲突检测。
- 版本冻结：保证 `design-vN.md`、`reports/vN/`、`design-pack/` 和 Baseline 同步使用同一份冻结证据。

## 2. 优先级定义

| 优先级 | 含义 | 推荐处理时机 |
| --- | --- | --- |
| P0 | 不补会影响 SDD 可信度或阻碍团队使用 | 试点扩大前 |
| P1 | 会影响规模化落地、多人协作或复杂项目适配 | 1 到 2 个迭代内 |
| P2 | 体验、效率、治理完善项 | 稳定试点后持续演进 |

## 3. 流程成本与 Design Pack 分级

### 3.1 建立轻量 / 标准 / 完整 SDD 模式

优先级：P0

当前问题：

- 文档层面容易给人感觉“每个需求都要产出完整 Design Pack”。
- 小团队、短迭代场景下，如果简单 API 也必须维护幂等、外部调用、异步事件等模板，会造成明显执行负担。
- 当前实现虽然按 `capability_tags` 决定文件集合，但团队规则没有明确“什么时候必须打哪些 tag”。

建议方案：

- 定义三档模式：
  - 轻量 SDD：简单查询、简单内部 API，仅保留 `feature-brief.md`、`design-vN.md`、必要接口文档。
  - 标准 SDD：涉及接口、数据库、任务拆分和测试骨架。
  - 完整 SDD：涉及支付、幂等、外部调用、异步事件、状态机、审批等高风险场景。
- 在 `feature-brief.md` 模板中增加 `sdd_level` 字段。
- `capability_tags` 只允许由需求事实触发，不允许模板默认全开。
- Gate 1 根据 `sdd_level + capability_tags` 校验必需文件，而不是让所有 feature 承担同一套成本。

验收标准：

- 一个只读查询 API 可以通过轻量 SDD，不需要幂等策略、外部调用策略、异步事件契约。
- 支付、资金、跨系统写操作自动进入完整 SDD。
- 文档中有明确示例说明不同需求如何选择 SDD 模式。

影响范围：

- `document/template/Feature-Brief-模板.md`
- `scripts/init_design_pack.py`
- `scripts/check_design_pack.py`
- `docs/team-onboarding.md`

### 3.2 补充团队节奏适配策略

优先级：P1

当前问题：

- 缺少对 5 人小团队、两周迭代、紧急需求、缺陷修复等不同节奏的操作建议。
- 所有流程都从完整治理角度描述，容易让团队认为必须一次性做到全量合规。

建议方案：

- 在团队接入文档中增加“推广策略”：
  - 第 1 阶段：只对高风险需求完整执行 SDD。
  - 第 2 阶段：把常规需求纳入轻量 SDD。
  - 第 3 阶段：把 Gate 接入 CI 和发布流程。
- 定义豁免机制：紧急修复允许先实现，但必须补录最小设计、测试证据和 Baseline 记录。

验收标准：

- 团队可以按风险和规模选择流程，不会被单一重流程阻塞。
- 每个例外都有记录入口和补录要求。

影响范围：

- `docs/team-onboarding.md`
- `docs/attached-project-mode.md`
- `scripts/release_gate.py`

## 4. MCP 与 Baseline 事实源可信度

### 4.1 为 `project-explorer` 引入 Java AST 级扫描

优先级：P0

当前问题：

- `project-explorer` 当前主要通过正则扫描 Java 类和 public 方法。
- 对 Lombok、复杂泛型、内部类、继承方法、注解生成方法、MyBatis XML 映射、代理类等支持不足。
- 老项目中如果 module-map 不准，Gate 2 / Gate 5 的实现追溯可信度会下降。

建议方案：

- 将 Java 扫描升级为 AST 或编译器级方案：
  - 短期：接入 JavaParser，补全类、字段、方法、注解、内部类。
  - 中期：可选接入 JDT 或 `javac` symbol API，提高泛型和继承解析能力。
- 在 `module-map.json` 中增加扫描质量字段：
  - `scanner`: `regex` / `javaparser` / `jdt`
  - `confidence`: `low` / `medium` / `high`
  - `unsupported_features`: 记录 Lombok、XML Mapper、反射等未覆盖项。
- Gate 使用 `confidence` 决策：
  - 低可信度不能直接 PASS，只能 WARN 或要求人工确认。

验收标准：

- 能识别 Lombok 注解类的关键字段。
- 能区分同名类的 FQN 和模块。
- 能识别内部类、record、interface、enum。
- module-map 生成报告中能看到扫描覆盖率与不支持项。

影响范围：

- `mcp-servers/project-explorer/src/lib/scanner.ts`
- `scripts/refresh_module_map.py`
- `scripts/check_design_truthfulness.py`
- `scripts/check_design_test_coverage.py`

### 4.2 建立 PolyQuery 生产接入安全边界

优先级：P0

当前问题：

- `polyquery` 支持只读模式、超时和行数限制，但真实生产从库权限、元数据查询性能、网络白名单和审计要求还未在 SDD 层固化。
- `config/polyquery.json` 当前是本地配置约定，缺少团队级安全模板和审批边界。
- 如果 polyquery 不可用并回退本地快照，容易出现“看似通过但事实不是实时数据库”的误解。

建议方案：

- 明确生产使用原则：
  - 只连接只读从库或专用元数据库。
  - 只授予 metadata / information_schema / describe 权限。
  - 禁止使用生产写账号。
  - 设置查询超时和最大表数量。
- 在严格模式下默认使用 `--polyquery-fallback fail`。
- 在 `schema-context.json` 中记录：
  - `source`
  - `connection_name`
  - `schema_name`
  - `generated_at`
  - `fallback_from`
  - `confidence`
- 当 `source=local-fallback` 时，Gate 2 应输出 WARN 或 FAIL，取决于 feature 风险等级。

验收标准：

- 高风险 feature 不允许使用 local fallback 通过 Gate 2。
- polyquery 失败时报告中明确显示失败原因，不静默降级。
- 文档中有 DBA 权限申请模板。

影响范围：

- `docs/polyquery-integration.md`
- `scripts/refresh_schema_context.py`
- `scripts/polyquery_adapter.py`
- `scripts/check_design_truthfulness.py`

### 4.3 建立事实源等级模型

优先级：P0

当前问题：

- 目前 Baseline 中不同来源的数据混在一起，缺少统一可信等级。
- 设计文档推断、MCP 扫描、真实数据库元数据、CI 测试结果的可信度不同，但 Gate 报告没有系统区分。

建议方案：

- 定义事实源等级：
  - L1：编译器、数据库元数据、CI 测试、真实构建结果。
  - L2：MCP 扫描快照。
  - L3：设计文档、正则解析、人工填写。
- Baseline 文件统一增加 `evidence_level` 和 `confidence`。
- Gate 报告必须输出每个关键结论的证据来源。

验收标准：

- Gate 2 / Gate 5 报告中可以看到类、表、字段、测试结论分别来自哪个事实源。
- 低等级证据不会被误当成强事实。

影响范围：

- `.spec/baselines/*/module-map.json`
- `.spec/baselines/*/schema-context.json`
- `scripts/gate_report.py`
- `scripts/check_design_truthfulness.py`
- `scripts/check_design_test_coverage.py`

## 5. Gate 确定性校验强化

### 5.1 明确 Gate 1/2/3 不是 AI 自由判断

优先级：P0

当前问题：

- 文档提到“确定性校验脚本”，但没有给出足够多的运行示例和校验边界。
- 团队可能误以为 Gate 由 AI 自由发挥，从而担心幻觉风险。

建议方案：

- 在文档中明确：
  - Gate 1 负责结构和 Design Pack 完整性。
  - Gate 2 负责 Baseline 真实性和 REQ 覆盖。
  - Gate 3 负责架构语义最小规则。
  - AI 可以辅助生成内容，但 Gate 结论来自脚本产物。
- 每个 Gate 文档补充：
  - 输入文件。
  - 输出报告。
  - 确定性规则。
  - 当前不覆盖的场景。

验收标准：

- 新成员能在 10 分钟内理解每个 Gate 到底检查什么。
- 报告中能看到执行命令和原始输出。

影响范围：

- `docs/team-onboarding.md`
- `docs/agent-integration.md`
- `scripts/gate1.py`
- `scripts/check_design_truthfulness.py`
- `scripts/check_arch_semantics.py`

### 5.2 增强字段级、方法级和契约级校验

优先级：P1

当前问题：

- Gate 2 当前主要检查类名、表名、REQ 覆盖和部分冲突。
- “字段是否存在”“方法签名是否匹配”“OpenAPI 与 Controller 是否一致”等还没有严格实现。

建议方案：

- 字段级：
  - 从 `schema-context.json` 的 `column_details` 校验字段存在、类型、nullable。
  - 数据模型引用已有表时必须能追溯到真实 schema 或 SQL 变更。
- 方法级：
  - 从 AST 版 module-map 校验类和方法签名。
  - 对 Controller / Service / Repository 分别建立最小契约。
- 契约级：
  - OpenAPI path / method / operationId 与真实 Controller 映射校验。
  - MyBatis XML / JPA Entity 与数据模型建立映射。

验收标准：

- 设计中引用不存在字段时 Gate 2 失败。
- 设计中引用不存在方法时 Gate 5 至少 WARN，高风险场景 FAIL。
- OpenAPI 与 Controller 不一致时可定位到具体 path。

影响范围：

- `scripts/check_design_truthfulness.py`
- `scripts/check_design_test_coverage.py`
- `mcp-servers/project-explorer`

### 5.3 Gate 结果引入严格模式

优先级：P1

当前问题：

- 部分 Gate 当前允许 WARN 或 SKIPPED，适合试点，但不适合发布准入。
- Gate 5 默认如果未配置 attached project verification commands，会标记 SKIPPED。

建议方案：

- 增加 `--strict` 或环境变量 `SDD_STRICT=true`。
- 严格模式下：
  - `local-fallback` 不允许通过高风险 Gate。
  - `attached_execution=SKIPPED` 不允许进入 release gate。
  - 低可信 module-map 不允许作为实现态同步依据。

验收标准：

- 本地试点可以宽松运行。
- CI / 发布流水线可以严格运行。

影响范围：

- `scripts/run_pipeline.py`
- `scripts/check_design_truthfulness.py`
- `scripts/check_design_test_coverage.py`
- `scripts/release_gate.py`

## 6. 多模块、多服务与多数据源 Baseline

### 6.1 引入组件维度的 Baseline 模型

优先级：P0

当前问题：

- 现有 baseline 按 attached project 分桶，适合单业务项目。
- 如果一个需求涉及订单、库存、支付等多个服务，且技术栈不同，当前全局合并会造成边界不清。
- Java 8 + MyBatis 与 Java 17 + JPA 混合时，扫描规则、构建命令、数据库映射都不同。

建议方案：

- 引入 `component_id`：
  - `order-service`
  - `inventory-service`
  - `payment-service`
- `attached-project.json` 支持多个 component：

```json
{
  "components": [
    {
      "component_id": "order-service",
      "runtime": "java8",
      "persistence": "mybatis",
      "project_root": "D:\\projects\\order-service",
      "scan_roots": ["src/main/java"],
      "schema_roots": ["src/main/resources"]
    }
  ]
}
```

- `feature-brief.md` 或 design 中声明 `affected_components`。
- Gate 只检查受影响组件，避免全项目扫描噪声。

验收标准：

- 一个 feature 可声明影响多个组件。
- 每个组件可有独立扫描器、构建命令和 schema 来源。
- Gate 报告按组件展示结论。

影响范围：

- `.spec/attached-project.json`
- `scripts/attached_project.py`
- `scripts/baseline_paths.py`
- `scripts/refresh_module_map.py`
- `scripts/refresh_schema_context.py`

### 6.2 调整 module-map 与 schema-context 的唯一键

优先级：P1

当前问题：

- `module-map.json` 中同名类依赖 display_name 做区分，但跨模块语义仍不够强。
- `schema-context.json` 当前按表名合并，跨库、跨 schema 同名表存在冲突风险。

建议方案：

- module-map 类唯一键升级为：
  - `component_id + fqn`
  - 无 FQN 时使用 `component_id + source_file + simple_name`
- schema-context 表唯一键升级为：
  - `db_type + connection_name + schema_name + table_name`
- 冲突检测时区分：
  - 同组件冲突
  - 跨组件共享依赖
  - 跨组件非法占用

验收标准：

- 不同服务中的同名类不会互相污染。
- 不同数据库中的同名表不会被错误合并。
- 冲突报告能定位到 component / datasource / schema。

影响范围：

- `mcp-servers/project-explorer/src/lib/scanner.ts`
- `scripts/polyquery_adapter.py`
- `scripts/refresh_schema_context.py`
- `scripts/update_index_design.py`

### 6.3 提升冲突检测粒度

优先级：P1

当前问题：

- 设计态索引当前主要检查 path / table / event 级资源冲突。
- 对方法级、字段级、消息字段级、状态机状态级冲突没有覆盖。

建议方案：

- 将资源占位细化为：
  - API：path + method。
  - 表：datasource + schema + table。
  - 字段：table + column。
  - 事件：topic + eventName + key fields。
  - 方法：component + class + method signature。
- 冲突级别区分：
  - BLOCKER：同资源被两个 ACTIVE 设计不兼容修改。
  - WARN：共享只读资源或兼容扩展。

验收标准：

- 两个 feature 同时修改同一个表的同一字段时能阻断。
- 两个 feature 新增同名 API path 但 method 不同能正确区分。

影响范围：

- `scripts/update_index_design.py`
- `baseline_extractors.py`
- `.spec/baselines/*/sdd-index-design.json`

## 7. 版本策略与证据冻结

### 7.1 为 Design Pack 建立版本快照

优先级：P0

当前问题：

- `reports/vN/` 已经按设计版本保存报告。
- 但 `design-pack/` 是 feature 级共享目录，不是版本级目录。
- 如果 v2 报告已生成，之后 v3 修改了同一份 `design-pack/`，旧报告对应的证据会被污染。

建议方案：

- 每次 Gate 1 通过后冻结一份 Design Pack：
  - `reports/vN/design-pack.snapshot/`
  - 或 `.spec/design-artifacts/<feature>/vN/design-pack/`
- 后续 Gate 2/3/4/5 和 sync-baseline 都读取版本快照。
- 当前工作区 `design-pack/` 只作为草稿区。

验收标准：

- v1、v2、v3 的报告能分别追溯到当时的设计包内容。
- 修改当前 `design-pack/` 不会改变旧版本 Gate 结论。

影响范围：

- `scripts/gate1.py`
- `scripts/check_design_truthfulness.py`
- `scripts/check_arch_semantics.py`
- `scripts/generate_task_slices.py`
- `scripts/sync_baseline.py`

### 7.2 `sync-baseline` 支持显式设计版本

优先级：P0

当前问题：

- 当前 `sync_baseline.py` 默认取最新 `design-vN.md`。
- 正常情况下这能避免同步中间版本，但在多人协作或并行修改时，latest 可能不是发布要同步的版本。

建议方案：

- 增加参数：

```powershell
python scripts/run_pipeline.py sync-baseline specs\feature-a --design-version v3
```

- CI / release gate 必须显式传入设计版本。
- 同步前校验：
  - `reports/vN/verify-report.json` 为 PASS。
  - `reports/vN/gate-report.json` 中 Gate 1/2/3/5 版本一致。
  - design hash 与报告记录一致。

验收标准：

- 不会因为最新草稿版本存在而阻止同步已批准版本。
- 不会把未审批、未验证版本同步到 real index。

影响范围：

- `scripts/sync_baseline.py`
- `scripts/run_pipeline.py`
- `scripts/release_gate.py`

### 7.3 Baseline 写入增加 hash 与证据链

优先级：P1

当前问题：

- real index 当前记录 feature、design_version、paths、tables、source_intent_id。
- 缺少 design 文件、design-pack、module-map、schema-context 的内容 hash。

建议方案：

- real index 增加：
  - `design_hash`
  - `design_pack_hash`
  - `module_map_hash`
  - `schema_context_hash`
  - `verified_report`
  - `verified_at`
- Gate 报告同步写入同样 hash。

验收标准：

- 任一实现态 Baseline 记录都能还原其同步时的设计证据。
- 设计包被后续修改时，旧 Baseline 仍可审计。

影响范围：

- `scripts/gate_report.py`
- `scripts/check_design_test_coverage.py`
- `scripts/sync_baseline.py`

## 8. Gate 5 与真实业务测试

### 8.1 将 Gate 5 从设计验证测试推进到业务测试载体

优先级：P1

当前问题：

- Gate 5 目前主要检查生成测试骨架中的 TODO 是否清除，并尝试执行测试文件。
- attached project 的 `verification_commands` 是可选的。
- 这适合试点，但不足以作为真实上线前质量门禁。

建议方案：

- 高风险 feature 必须配置 `verification_commands`。
- `verification_commands` 支持按 component 配置。
- 支持 `{feature_name}`、`{component_id}`、`{design_version}` 占位符。
- Gate 5 输出真实业务测试命令、工作目录、退出码、日志 tail。

验收标准：

- 未配置真实业务测试命令的高风险 feature 不能通过严格模式 Gate 5。
- 多组件需求能分别执行各组件测试命令。

影响范围：

- `.spec/attached-project.json`
- `scripts/check_design_test_coverage.py`
- `docs/attached-project-mode.md`

### 8.2 建立需求到测试的可追溯映射

优先级：P1

当前问题：

- 当前 Gate 5 主要通过 TODO 标记判断 REQ 是否覆盖。
- 真实项目测试用例和 REQ-ID 之间缺少稳定映射。

建议方案：

- 定义测试注解或命名规范：
  - Java：`@SddRequirement("REQ-001")`
  - Python：测试函数 docstring 或 marker。
  - JUnit DisplayName 包含 REQ-ID。
- Gate 5 扫描真实测试报告或源码，建立 REQ 覆盖矩阵。

验收标准：

- 不依赖生成测试骨架，也能判断 REQ-ID 是否被真实测试覆盖。
- 覆盖缺口可定位到具体 REQ 和测试文件。

影响范围：

- `scripts/generate_test_skeleton.py`
- `scripts/check_design_test_coverage.py`

## 9. 双态索引与治理规则

### 9.1 明确设计态和实现态的生命周期

优先级：P1

当前问题：

- 当前设计态支持 ACTIVE / SUPERSEDED / IMPLEMENTED 等状态。
- 但团队文档中对状态流转、取消、归档、重新打开的说明还不够完整。

建议方案：

- 文档化状态机：
  - ACTIVE：当前有效设计意图。
  - SUPERSEDED：被新版本替代。
  - CANCELLED：需求取消或方案废弃。
  - IMPLEMENTED：已同步到实现态。
- 规定每个状态变化必须有操作记录。
- release gate 只接受 IMPLEMENTED 或明确豁免状态。

验收标准：

- 任一设计意图可追溯到创建、审批、替代、实现或取消。
- 旧设计不会长期停留在 ACTIVE。

影响范围：

- `scripts/update_index_design.py`
- `scripts/design_index_lifecycle.py`
- `scripts/build_flow_status.py`
- `docs/team-onboarding.md`

### 9.2 增加 stale baseline 检测

优先级：P1

当前问题：

- 如果源码或数据库发生变化但没有刷新 Baseline，Gate 可能使用过期事实。
- 当前 cache 有 TTL，但 Gate 侧没有统一判断 Baseline 是否过期。

建议方案：

- Baseline 文件记录：
  - `generated_at`
  - `source_signature`
  - `ttl`
- Gate 前检查：
  - module-map 是否过期。
  - schema-context 是否过期。
  - 是否与当前 attached project 配置一致。

验收标准：

- 过期 Baseline 在严格模式下阻断。
- 非严格模式下至少 WARN。

影响范围：

- `scripts/refresh_module_map.py`
- `scripts/refresh_schema_context.py`
- `scripts/check_design_truthfulness.py`
- `scripts/check_design_test_coverage.py`

## 10. 安全、权限与配置治理

### 10.1 敏感配置与凭据管理

优先级：P0

当前问题：

- polyquery 配置建议使用环境变量，但还需要统一模板和检查。
- 本地 `.env`、数据库连接串、生产账号不能误提交。

建议方案：

- 提供 `config/polyquery.example.json` 和 `.env.example`。
- `doctor.ps1` 检查是否存在明文密码。
- 文档明确禁止提交真实连接串。
- 建议通过团队密钥管理或 CI secret 注入。

验收标准：

- 仓库中不存在真实密码。
- 新成员能按模板配置本地只读连接。

影响范围：

- `config/`
- `scripts/doctor.ps1`
- `.gitignore`
- `docs/polyquery-integration.md`

### 10.2 数据库查询审计

优先级：P2

当前问题：

- polyquery 查询结果用于 Baseline，但缺少统一审计记录。

建议方案：

- 每次刷新 schema-context 时记录：
  - 数据源。
  - 表数量。
  - 查询耗时。
  - 是否 fallback。
  - 是否自动发现。
- 可选输出到 `.spec/ops/`。

验收标准：

- 能追踪每次数据库元数据读取行为。

影响范围：

- `scripts/polyquery_adapter.py`
- `scripts/ops_log.py`

## 11. CI、发布与团队工作台

### 11.1 增加 CI 推荐流水线

优先级：P1

当前问题：

- 当前命令可以本地运行，但缺少推荐 CI pipeline。
- 不同团队可能各自拼接命令，导致 Gate 执行不一致。

建议方案：

- 提供标准流水线阶段：
  - `refresh-baseline`
  - `design-gates`
  - `implementation-gates --strict`
  - `release-gate`
  - `validate-all-reports`
- 输出 GitHub Actions 或 Jenkins 示例。

验收标准：

- 团队可以直接复制一份 CI 配置开始试点。

影响范围：

- `.github/`
- `docs/team-onboarding.md`
- `docs/agent-integration.md`

### 11.2 强化 doctor 检查

优先级：P2

当前问题：

- doctor 脚本已有基础检查，但可以进一步覆盖 attached project、MCP、polyquery、安全配置和 Gate smoke test。

建议方案：

- doctor 输出分组：
  - 工具链。
  - MCP。
  - attached project。
  - Baseline freshness。
  - polyquery readiness。
  - security warnings。

验收标准：

- 新成员执行一次 doctor 就知道当前环境是否可跑完整流程。

影响范围：

- `scripts/doctor.ps1`
- `docs/agent-integration.md`

## 12. 文档与样例

### 12.1 补充真实案例矩阵

优先级：P1

当前问题：

- 示例项目虽能跑通基本链路，但需要一组可复用、可回归的场景矩阵来覆盖不同复杂度。

建议方案：

- 增加示例：
  - 简单 API 轻量 SDD。
  - DB 变更标准 SDD。
  - 支付/幂等完整 SDD。
  - 多组件需求。
  - polyquery snapshot 离线场景。

当前进展：

- `examples/fixtures/` 已补齐上述 5 类最小样例，并提供矩阵校验脚本 `python scripts/validate_fixture_matrix.py`。
- 已额外补充高风险治理失败样例与 Gate 5 WARN 样例。
- 剩余重点转为更多失败原因分型和更贴近真实业务长链路的样例。

验收标准：

- 每个示例都有输入、命令、预期报告和常见失败案例。

影响范围：

- `examples/fixtures/`
- `docs/team-onboarding.md`
- `docs/polyquery-integration.md`

### 12.2 明确当前限制

优先级：P0

当前问题：

- 部分限制散落在不同文档中，团队不容易形成统一预期。

建议方案：

- 在 README 和接入文档中明确当前限制：
  - project-explorer 不是编译器级索引。
  - schema-context 可来自本地快照或 polyquery，两者可信度不同。
  - Gate 5 当前仍以设计验证测试为主。
  - `design-pack/` 尚未版本冻结。
  - 多组件 Baseline 仍需升级。

验收标准：

- 试点团队不会把 MVP 能力误认为生产级能力。

影响范围：

- `README.md`
- `docs/attached-project-mode.md`
- `docs/team-onboarding.md`

## 13. 推荐落地路线

### 13.1 第一阶段：试点可控化

优先级：P0

目标：让小团队能用，不被流程压垮，同时避免误信低可信数据。

建议任务：

- 补充轻量 / 标准 / 完整 SDD 分级规则。
- 明确当前限制和 Gate 脚本边界。
- 高风险 feature 默认使用 `--polyquery-fallback fail`。
- Gate 报告增加证据来源说明。
- 为 `design-pack/` 做版本快照方案设计。

### 13.2 第二阶段：事实源增强

优先级：P1

目标：让 Baseline 更可信，减少老项目误判。

建议任务：

- project-explorer 升级 AST 扫描。
- schema-context 增加 datasource/schema/table 唯一键。
- Gate 2 增加字段级校验。
- Gate 5 增加真实业务测试强制策略。
- sync-baseline 支持显式 design version。

### 13.3 第三阶段：多组件规模化

优先级：P1

目标：支持真实多服务、多技术栈项目。

建议任务：

- attached project 改造为 components 模型。
- module-map / schema-context 按 component 分区。
- 冲突检测升级到 API method、字段、事件字段和方法签名级。
- CI 接入严格模式。

### 13.4 第四阶段：治理体验完善

优先级：P2

目标：提高团队长期维护效率。

建议任务：

- doctor 增强。
- 数据库查询审计。
- 示例矩阵。
- 项目控制台展示 Baseline 可信度、过期状态和 Gate 健康度。

## 14. 当前最建议优先实现的 5 件事

1. 建立轻量 / 标准 / 完整 SDD 分级，降低团队执行成本。
2. 在文档中明确 MCP 与 Gate 的当前边界，避免误认为已是生产级事实源。
3. 为 `design-pack/` 建立版本快照，解决 `reports/vN/` 与设计包不一致问题。
4. `sync-baseline` 支持显式 `--design-version`，避免 latest 策略在并行协作中误伤。
5. Baseline 增加事实源等级和 hash 证据链，为后续严格 Gate 打基础。
