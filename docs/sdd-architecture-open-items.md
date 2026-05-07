# SDD 架构未完成项清单

本文档从 `docs/sdd-architecture-improvement-backlog.md` 重新审阅后抽取仍未完全完成的事项。  
口径：已基本满足验收标准的条目不再列入；已部分落地但仍有验收缺口的条目保留为“部分完成”。

更新时间：2026-05-06

## 当前已基本闭合的事项

以下事项不再作为开放项跟踪：

- `3.1` 主体能力：已增加 `sdd_level`，并在 `check_design_pack.py` / `init_design_pack.py` 中按 `sdd_level + capability_tags` 做基础约束。
- `5.1` 主体文档边界：已在 README、team onboarding、agent integration 中说明 Gate 脚本边界。
- `7.1` 主体能力：Gate 1 已冻结 `reports/vN/design-pack.snapshot/`，Gate 2、设计态索引和 baseline 同步已优先读取快照。
- `7.2` 主体能力：`sync-baseline` 已支持 `--design-version`。
- `7.3` 主体能力：实现态 baseline 已写入 design/design-pack/module-map/schema-context hash 与 evidence。
- `12.2` 主体文档：README、attached project、team onboarding 已补充当前限制。
- `10.2` 主体能力：`refresh_schema_context.py` 已写入 schema-context 刷新审计日志。
- `11.2` 主体能力：`doctor.ps1` 已纳入 Gate smoke test。

## P0 未完成项

### P0-1：`3.1` SDD 分级自动判定与示例矩阵尾项

状态：部分完成

已完成：

- `feature-brief.md` 模板已增加 `sdd_level`。
- Gate 1 已能按 `sdd_level + capability_tags` 约束轻量 / 标准 / 完整 SDD。
- 高风险 feature 必须使用完整 SDD 的基础规则已落地。

未完成：

- 尚未根据需求事实自动推导 `sdd_level`。
- “支付、资金、跨系统写操作自动进入完整 SDD”仍主要依赖人工填写 `risk_tier` / `capability_tags`。
- 示例文档还缺少轻量 / 标准 / 完整三类需求的完整样例。

建议下一步：

- 在 `generate_feature_brief.py` 或 requirement analyzer 中增加 `sdd_level` 推导。
- 增加示例：只读 API、DB 变更、支付/幂等完整 SDD。
- 补测试覆盖：支付/资金关键词或跨系统写操作必须推导到 `full`。

影响范围：

- `scripts/generate_feature_brief.py`
- `skills/requirement-analyzer`
- `docs/team-onboarding.md`
- `examples/fixtures/`

### P0-2：`4.1` project-explorer Java AST 级扫描

状态：部分完成

已完成：

- project-explorer 已输出 `scanner=java-lexical-v2`、`evidence_level`、`confidence`、`unsupported_features` 和 `scan_quality`。
- 轻量 Java 扫描已覆盖类、字段、公开方法、注解、内部类、record/interface/enum、extends/implements。
- `module-map.json` 已能记录 Lombok、反射、MyBatis mapper 等低可信特征。
- Gate 2 已基于低可信 `module-map` 在非 strict 下 WARN、strict 下 FAIL。
- Gate 5 implementation traceability 已基于低可信 `module-map` 降级为 WARN，strict 流程中会阻断。
- 已补充 project-explorer scanner、Gate 2 低可信、Gate 5 低可信回归测试。

未完成：

- Java 扫描仍未升级到 JavaParser / JDT / `javac` symbol API。
- Lombok 生成方法、复杂泛型符号解析、继承方法、MyBatis XML 映射等仍未形成符号级可靠覆盖。

建议下一步：

- 接入 JavaParser / JDT / `javac` symbol API，把 `java-lexical-v2` 升级为符号级扫描器。
- 增加继承方法、泛型擦除前类型、MyBatis XML 与接口方法绑定解析。
- 将 scanner 质量报告接入更细粒度的 evidence 降级策略。

影响范围：

- `mcp-servers/project-explorer/src/lib/scanner.ts`
- `scripts/refresh_module_map.py`
- `scripts/check_design_truthfulness.py`
- `scripts/check_design_test_coverage.py`

### P0-3：`4.2` PolyQuery 生产接入边界尾项

状态：部分完成

已完成：

- 文档已补充只读账号、metadata 权限、禁止写账号、DBA 申请模板。
- `refresh-schema-context` 已支持 `--polyquery-fallback fail|local`。
- `schema-context` 已能记录 `source`、`fallback_from` 等基础信息。
- Gate 2 已按 `source=local-fallback` 和 feature 风险等级自动 WARN/FAIL。
- 严格模式下 Gate 2 会阻断 local fallback。
- schema-context 刷新已写入审计日志。

未完成：

- 严格模式下默认 `--polyquery-fallback fail` 尚未贯穿所有 pipeline 刷新入口。
- polyquery 生产接入的限流、最大表数量治理尚未形成统一 Gate 规则。

建议下一步：

- 在 `design-gates` 或 CI 推荐命令中支持严格 polyquery 刷新策略。
- 继续补充限流和最大表数量检查。

影响范围：

- `scripts/refresh_schema_context.py`
- `scripts/polyquery_adapter.py`
- `scripts/check_design_truthfulness.py`
- `scripts/run_pipeline.py`

### P0-4：`4.3` 统一事实源等级模型

状态：部分完成

已完成：

- `sync-baseline` 已写入 design、design-pack、module-map、schema-context、verify-report 的 evidence 与 hash。
- Gate 2 已输出 design/design-pack 的基础 evidence。
- `module-map.json` / `schema-context.json` 刷新时已写入基础 `evidence_level` / `confidence` / `source_signature` / `ttl`。
- Gate 5 已输出 design/module-map/schema-context evidence。

未完成：

- Gate 2 / Gate 5 还没有把类、表、字段、测试结论逐项关联到 L1/L2/L3 事实源。
- 低等级证据降级策略仍不完整。

建议下一步：

- 为 baseline 文件增加统一 evidence metadata。
- Gate 报告按结论输出证据来源，例如 class/table/field/test 分别标注 L1/L2/L3。
- 严格模式下禁止 L3 证据直接支撑高风险 PASS。

影响范围：

- `.spec/baselines/*/module-map.json`
- `.spec/baselines/*/schema-context.json`
- `scripts/gate_report.py`
- `scripts/check_design_truthfulness.py`
- `scripts/check_design_test_coverage.py`

### P0-5：`6.1` 组件维度 Baseline 模型

状态：部分完成

已完成：

- `attached-project.json` 已可承载 `components[]` 配置模型，且兼容单项目与多组件形态。
- feature 已支持声明 `affected_components`，并已接入 Gate 2 / Gate 5 的受影响范围过滤。
- attached verification 已可按 `affected_components` 过滤执行范围。
- fixture 矩阵已补充 `multi-component-api` 组件样例。

未完成：

- baseline bucket 内的 module-map / schema-context 仍未完成按 component 的物理分区与唯一键升级。
- verification commands 虽已支持组件维度过滤，但组件模型与 baseline / schema-context / 索引的底层隔离尚未完全统一。
- Gate 报告虽已包含 `affected_components` 和部分组件执行结果，但尚未形成完整的 component-aware 展示与冲突定位。

建议下一步：

- 将 baseline bucket 内的 module-map / schema-context 增加 component 分区。
- 升级 module-map / schema-context 唯一键，避免跨组件、跨数据源资源混淆。
- 将 Gate 2 / Gate 5 / Release 相关报告统一提升为 component-aware 输出。

影响范围：

- `.spec/attached-project.json`
- `scripts/attached_project.py`
- `scripts/baseline_paths.py`
- `scripts/refresh_module_map.py`
- `scripts/refresh_schema_context.py`

### P0-6：`10.1` 敏感配置与凭据管理的 doctor 检查

状态：部分完成

已完成：

- 已提供 `config/polyquery.example.json`。
- 已提供 `.env.example`。
- `.gitignore` 已忽略 `config/polyquery.json`、`.env` 等本地敏感配置。
- polyquery 文档已说明禁止提交真实连接串。
- `doctor.ps1` 已增加 config / `.spec` / `.env*` 明文密码、连接串、可疑 secret 扫描。
- doctor 已增加 security warnings 分组。

未完成：

- 安全扫描结果尚未写入 tooling hygiene JSON。

建议下一步：

- 将安全检查结果写入 tooling hygiene 或 doctor 报告。

影响范围：

- `scripts/doctor.ps1`
- `scripts/build_workspace_hygiene.py`
- `docs/polyquery-integration.md`

## P1 未完成项

### P1-1：`3.2` 团队节奏适配与豁免机制

状态：部分完成

已完成：

- `docs/team-onboarding.md` 已补充推广节奏。

未完成：

- 紧急修复 / 缺陷修复的豁免记录入口尚未实现。
- release gate 尚未读取豁免记录并要求补录最小设计、测试证据和 Baseline。

建议下一步：

- 增加 `exceptions/` 或 `reports/vN/exception.json`。
- release gate 对豁免项校验补录要求。

影响范围：

- `docs/team-onboarding.md`
- `docs/attached-project-mode.md`
- `scripts/release_gate.py`

### P1-2：`5.2` 字段级、方法级和契约级校验

状态：部分完成

已完成：

- Gate 2 已支持从 `数据模型.md` 提取表字段引用，并对既有 `schema-context` 表校验 `columns` / `column_details[].name` 中的字段存在性。
- 当设计引用了既有表但字段不存在于 `schema-context` 时，Gate 2 会失败并输出缺失字段清单。
- Gate 2 已支持字段类型规范化对比，并对 `nullable` / 必填语义与 `schema-context.column_details` 做一致性校验。
- project-explorer 已从 Spring MVC 注解中提取 Controller endpoint。
- Gate 2 已支持 OpenAPI path/method/operationId 与真实 Controller endpoint 的最小映射校验。
- Gate 5 已从 Mermaid sequenceDiagram 提取目标类方法调用，并校验设计引用方法是否存在于 `module-map.public_methods`。
- 已补充字段缺失、字段类型不一致、nullable 不一致场景的回归测试。

未完成：

- MyBatis XML / JPA Entity 与数据模型尚未建立映射。
- 方法签名目前是轻量方法名级校验，尚未基于 JavaParser/JDT/`javac` 做参数类型级符号解析。

建议下一步：

- 补 MyBatis XML / JPA Entity 与数据模型映射。
- AST 版 module-map 完成后，将方法校验升级到参数类型级签名匹配。

影响范围：

- `scripts/check_design_truthfulness.py`
- `scripts/check_design_test_coverage.py`
- `mcp-servers/project-explorer`

### P1-3：`5.3` Gate 严格模式

状态：部分完成

已完成：

- Gate 5 已支持 `--require-attached-execution`。
- `gate2` / `gate5` / `release-gate` / `design-gates` / `implementation-gates` / `full-flow` 已支持 `--strict`。
- `SDD_STRICT=true` 已接入 Gate 2、Gate 5、Release Gate。
- strict 下 Gate 5 要求 attached execution，Release Gate 要求 verify-report 中 attached_execution 为 PASS。

未完成：

- 低可信 module-map 的 strict 阻断仍较粗，只在 Gate 5 implementation traceability 非 PASS 时阻断。
- CI 推荐流水线尚未正式改为 strict。

建议下一步：

- strict 下禁止低可信 module-map 同步实现态。

影响范围：

- `scripts/run_pipeline.py`
- `scripts/check_design_truthfulness.py`
- `scripts/check_design_test_coverage.py`
- `scripts/release_gate.py`

### P1-4：`6.2` module-map 与 schema-context 唯一键升级

状态：未完成

未完成：

- module-map 唯一键尚未升级为 `component_id + fqn`。
- schema-context 唯一键尚未升级为 `db_type + connection_name + schema_name + table_name`。
- 冲突报告尚不能定位到 component / datasource / schema。

建议下一步：

- 先在 schema-context 中保留兼容字段，同时新增 `resource_key`。
- update_index_design 逐步改为使用唯一键而不是裸 table_name。

影响范围：

- `mcp-servers/project-explorer/src/lib/scanner.ts`
- `scripts/polyquery_adapter.py`
- `scripts/refresh_schema_context.py`
- `scripts/update_index_design.py`

### P1-5：`6.3` 冲突检测粒度升级

状态：未完成

未完成：

- 当前设计态索引主要是 path / table / event 级。
- 尚未支持 API method、字段、事件字段、方法签名、状态机状态级冲突。
- 尚未区分 BLOCKER / WARN 资源冲突级别。

建议下一步：

- 将 API 资源从 path 升级为 `path + method`。
- 将表资源拆到 datasource/schema/table/column。
- 设计态索引新增 `resource_claims[]`，统一表达资源占用。

影响范围：

- `scripts/update_index_design.py`
- `scripts/baseline_extractors.py`
- `.spec/baselines/*/sdd-index-design.json`

### P1-6：`7.2` sync-baseline 版本一致性尾项

状态：部分完成

已完成：

- `sync-baseline --design-version` 已支持。
- 已校验 `verify-report.json` 的 `design_version` 与同步版本一致。
- 已强校验 `gate-report.json` 中 Gate 1/2/3/5 均为 PASS。
- 已校验 design hash 与 Gate 1 报告记录一致。

未完成：

- release gate / CI 尚未强制显式传入 design version。

建议下一步：

- CI / release 示例改为显式版本。

影响范围：

- `scripts/sync_baseline.py`
- `scripts/run_pipeline.py`
- `scripts/release_gate.py`

### P1-7：`7.3` Gate 报告 hash 证据链尾项

状态：部分完成

已完成：

- 实现态 real index 和 `baseline_sync` 报告已写入主要 hash。
- Gate 2 已写入 design/design-pack/module-map/schema-context evidence。
- Gate 5 已写入 design/module-map/schema-context evidence。

未完成：

- 报告校验工具尚未校验证据 hash 是否仍匹配当前快照。

建议下一步：

- `validate_reports.py` 增加 hash 一致性校验。

影响范围：

- `scripts/gate_report.py`
- `scripts/check_design_truthfulness.py`
- `scripts/check_design_test_coverage.py`
- `scripts/validate_reports.py`

### P1-8：`8.1` Gate 5 真实业务测试载体

状态：部分完成

已完成：

- 已支持 attached project `verification_commands`。
- 已支持 `gate5 --require-attached-execution`。
- 已输出命令、工作目录、退出码、日志 tail。
- strict 下 Gate 5 会自动要求 attached execution。
- 高风险 feature 在非 strict 路径下也已要求 `attached_execution_required=true`，Release Gate / `validate_reports.py` 已消费该约束。
- `verification_commands` 已支持 `{feature_name}`、`{component_id}`、`{design_version}` 占位符。

未完成：

- `verification_commands` 虽已支持组件配置与按受影响组件过滤，但尚未与 component-aware baseline / schema-context / 报告模型完全收口。
- Gate 5 还没有完全升级为“真实业务准入层”，对真实测试覆盖结果的准入消费仍偏轻。

建议下一步：

- 在完整 component-aware 模型落地后，按组件输出更完整的 attached execution 结果。
- 将真实业务测试结果与 Gate 5 / Release Gate 的准入规则进一步绑定。

影响范围：

- `.spec/attached-project.json`
- `scripts/check_design_test_coverage.py`
- `docs/attached-project-mode.md`

### P1-9：`8.2` 需求到真实测试的可追溯映射

状态：部分完成

已完成：

- Gate 5 已能扫描 attached project 下的真实测试源码，并提取 `REQ-ID`。
- 当前已支持从 Java / JUnit / Python 测试源码中的多种显式标注或文本引用提取 `REQ-ID`。
- verify-report 已开始产出 `real_test_req_coverage`。
- 相关组件范围已能受 `affected_components` 过滤。

未完成：

- 真实测试 `REQ-ID` 标注规范尚未正式文档化并统一为跨语言约束。
- 当前覆盖主要基于源码扫描，尚未形成测试报告级、框架级的稳定追溯标准。
- `real_test_req_coverage` 目前更多是报告项，尚未全面升级为高风险准入项。

建议下一步：

- 定义跨语言 REQ 标注规范。
- Gate 5 继续扫描真实测试源码和报告，生成更稳定的 REQ coverage matrix。
- 高风险 feature 要求真实测试覆盖 P0 REQ。

影响范围：

- `scripts/generate_test_skeleton.py`
- `scripts/check_design_test_coverage.py`

### P1-10：`9.1` 设计态 / 实现态生命周期治理

状态：部分完成

已完成：

- 代码层已有 ACTIVE / SUPERSEDED / CANCELLED / IMPLEMENTED 相关处理。

未完成：

- 团队文档尚未完整说明状态机、取消、归档、重新打开。
- 状态变化操作记录尚未形成强制校验。
- release gate 尚未只接受 IMPLEMENTED 或明确豁免状态。

建议下一步：

- 在 onboarding 中补状态机图和操作命令。
- release gate 检查实现态同步状态。
- 状态变更写入 ops log 或独立 lifecycle log。

影响范围：

- `scripts/update_index_design.py`
- `scripts/design_index_lifecycle.py`
- `scripts/build_flow_status.py`
- `docs/team-onboarding.md`

### P1-11：`9.2` stale baseline 检测

状态：基本完成

已完成：

- `refresh_module_map.py` / `refresh_schema_context.py` 已写入 `generated_at`、`ttl`、`source_signature`。
- Gate 2 已检测 `module-map.json` / `schema-context.json` 的 `generated_at + ttl` 是否过期。
- Gate 5 已复用 stale baseline 检测，并将 freshness 写入 verify-report / gate-report evidence。
- Gate 2 / Gate 5 已校验 attached project 当前配置与 `module-map.source_signature` 的一致性。
- Gate 2 / Gate 5 已校验 attached project 当前 schema_roots / design_roots 与 `schema-context.source_signature` 的一致性。
- 非 strict 模式下 stale baseline / 配置签名变化产出 WARN；strict 模式下阻断为 FAIL。
- 已补充 stale baseline、module-map attached 签名变化、schema-context 配置签名变化的 WARN / FAIL 回归测试。

后续增强：

- 如需覆盖纯 polyquery 生产 datasource 配置变化，可在 schema-context 中额外记录 polyquery config signature。

影响范围：

- `scripts/refresh_module_map.py`
- `scripts/refresh_schema_context.py`
- `scripts/check_design_truthfulness.py`
- `scripts/check_design_test_coverage.py`

### P1-12：`11.1` CI 推荐流水线完整化

状态：部分完成

已完成：

- 已有 GitHub Actions，覆盖 Windows / Ubuntu、测试、报告校验、artifact。

未完成：

- 尚未提供完整推荐阶段：`refresh-baseline`、`design-gates`、`implementation-gates --strict`、`release-gate`、`validate-all-reports`。
- 尚未提供 Jenkins 示例。
- CI 尚未体现 strict 模式。

建议下一步：

- 增加 `.github/workflows/sdd-pipeline.example.yml`。
- 在文档中给出按 feature 触发的 CI 参数示例。
- strict 模式完成后接入 CI。

影响范围：

- `.github/`
- `docs/team-onboarding.md`
- `docs/agent-integration.md`

### P1-13：`12.1` 真实案例矩阵

状态：部分完成

未完成：

- 已补齐轻量 API、DB 标准 SDD、支付/幂等完整 SDD、多组件、polyquery snapshot 离线场景的最小 fixture。
- 已补高风险 attached execution 失败样例与 Gate 5 P1 WARN 样例。
- 仍缺少更多失败原因分型和更贴近真实业务长链路的样例。

建议下一步：

- 继续为每个场景补更多失败态 / WARN 态分型样例。
- 增加更接近真实业务项目的长链路样例和产物对照。

影响范围：

- `examples/fixtures/`
- `docs/team-onboarding.md`
- `docs/polyquery-integration.md`

## P2 未完成项

### P2-1：`10.2` 数据库查询审计

状态：基本完成

已完成：

- refresh schema-context 时已写入 `schema-context-refresh` 审计记录。
- 记录项包含数据源、表数量、耗时、fallback、自动发现状态、错误信息。

建议下一步：

- 如后续需要独立审计文件，可从 project ops log 拆分到 `.spec/ops/schema-context-refresh.jsonl`。

影响范围：

- `scripts/polyquery_adapter.py`
- `scripts/refresh_schema_context.py`
- `scripts/ops_log.py`

## 推荐下一轮实施顺序

1. P0-2：继续接入 JavaParser / JDT / `javac` symbol API，补齐符号级 AST。
2. P1-2：补 MyBatis XML / JPA Entity 与数据模型映射，并等待符号级 AST 后升级方法签名精度。
3. P0-5：组件维度 Baseline，为多服务场景打地基。
4. P1-4/P1-5：唯一键与冲突粒度升级。
5. P1-12：CI strict 推荐流水线完整化。

## 原 backlog 条目状态索引

| 原章节 | 当前状态 |
| --- | --- |
| 3.1 | 部分完成，剩自动推导与示例 |
| 3.2 | 部分完成，剩豁免机制 |
| 4.1 | 部分完成，轻量 Java 结构扫描与低可信 Gate 治理已落地，剩符号级 AST |
| 4.2 | 部分完成，剩 strict pipeline 默认和限流 |
| 4.3 | 部分完成，剩逐项事实源等级和低等级降级策略 |
| 5.1 | 基本完成 |
| 5.2 | 部分完成，字段、Controller/OpenAPI、方法名级校验已落地，剩 MyBatis/JPA 映射与参数类型级签名 |
| 5.3 | 部分完成，strict 主入口已落地，剩 CI 推荐和低可信 module-map 细化 |
| 6.1 | 部分完成，`components[]` / `affected_components` / 组件范围过滤已落地，剩 baseline 与唯一键层收口 |
| 6.2 | 未完成 |
| 6.3 | 未完成 |
| 7.1 | 基本完成 |
| 7.2 | 部分完成，剩 CI / release 显式版本 |
| 7.3 | 部分完成，剩 validate_reports hash 校验 |
| 8.1 | 部分完成，高风险 attached execution 要求已落地，剩 component-aware 收口与准入加深 |
| 8.2 | 部分完成，真实测试源码 REQ 扫描与 `real_test_req_coverage` 已落地，剩标准化与强准入 |
| 9.1 | 部分完成，剩文档和 release gate 状态要求 |
| 9.2 | 基本完成，Gate 2/Gate 5 freshness 与 module-map/schema-context 配置签名已落地 |
| 10.1 | 部分完成，剩 tooling hygiene 安全报告 |
| 10.2 | 基本完成 |
| 11.1 | 部分完成，剩完整 CI 阶段和 strict |
| 11.2 | 基本完成 |
| 12.1 | 部分完成，已补 7 类 fixture，剩更多失败分型与长链路样例 |
| 12.2 | 基本完成 |
