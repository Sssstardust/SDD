# 排除 polyquery 后的当前剩余问题分析

日期：2026-04-29  
对照文档：`D:\project\SDD\document\skill-mcp-harness-sdd-enhanced-v3.4.md`  
历史版本：`D:\project\SDD\document\排除polyquery后的剩余问题分析-2026-04-22.md`

说明：

- 本文默认 `polyquery` 不再作为当前待开发缺口。
- 本文基于 2026-04-29 当前仓库状态重新校准 2026-04-22 的分析结论。
- 本文只讨论 SDD 自身在 Skill、MCP、Pipeline、Gate、Baseline 与运营治理上的剩余问题。

完成记录：

- 2026-04-29 已补齐本文标记的主要真实缺口：
  - Greenfield Gate 2 已接入 bootstrap 产物存在性、`scaffold-report.json`、最小结构语义校验，并写入 `gate-report.json`。
  - Release Gate 已支持结构化 `release-plan.md` YAML，关键词扫描降级为兼容兜底。
  - 架构规范已增加 `check-arch-standards-sync` 同步校验，Gate 3 分层语义优先读取 `docs/arch-standards/layering-semantics.json`。
  - `arch-standard` MCP 规则读取已调整为 `docs/arch-standards/` 优先。
  - Gate 5 已支持 attached project 的 `verification_commands`，真实项目测试失败会硬阻断 Gate 5。

---

## 1. 结论摘要

2026-04-22 版本的分析框架仍然合理，但具体状态已经过期。当前项目已经补齐多项当时判断为“未开发”的能力：

- Greenfield Bootstrap 已有正式入口。
- Release Gate 已有最小实现。
- Baseline Governance 已能生成 `constitution.md` 和 `tech-debt.md`。
- 设计态索引已支持取消和归档动作。
- Task Slice 深校验已基本补齐。

当前真正剩余的问题不再是“这些流程有没有”，而是：

1. Greenfield Gate 2 没有把 bootstrap 产物和结构约束真正纳入校验。
2. Release Gate 已有最小实现，但证据模型仍偏关键词扫描。
3. Gate 3 仍是 MCP 规则与脚本硬编码混合驱动。
4. Gate 5 已有执行与实现追溯，但还没有深入到真实业务实现验证。
5. 架构规范仍存在双份维护风险。
6. P5 运营化治理仍未完全平台化。

一句话总结：

**Skill / MCP / 主流程主体已经基本成型，当前重点应从“补入口”转为“补深度、补治理、补单一事实源”。**

---

## 2. 当前已经补齐的历史问题

### 2.1 Greenfield / Bootstrap 已有正式入口

当前 `run_pipeline.py` 已提供：

- `bootstrap`
- `greenfield-init`
- `scaffold`

对应实现：

- `scripts/bootstrap_feature.py`
- `scripts/bootstrap_utils.py`
- `.spec/templates/bootstrap/`

可生成的 bootstrap 产物包括：

- `constitution.md`
- `architecture.md`
- `module-layout.md`
- `bootstrap-plan.md`
- `scaffold-report.json`

因此，2026-04-22 文档中“Greenfield / Bootstrap 没有形成正式流程”的判断已经过期。

### 2.2 Release Gate 已有最小实现

当前 `run_pipeline.py` 已提供：

- `release-gate`
- `pre-release-check`
- `go-live-check`

对应实现：

- `scripts/release_gate.py`
- `.spec/schemas/reports/release-gate-report.schema.json`

Release Gate 当前会检查：

- Gate 5 是否已通过
- 回滚方案证据
- 监控与告警证据
- 灰度策略证据
- `db-change` 场景下 SQL 是否包含 `DOWN` 或 `ROLLBACK`

因此，2026-04-22 文档中“Release Gate 尚未开发”的判断已经过期。

### 2.3 Baseline 治理文件已补齐

当前 `.spec/baseline/` 与 `.spec/baselines/<attached-project-bucket>/` 下均已包含：

- `constitution.md`
- `tech-debt.md`
- `module-map.json`
- `schema-context.json`
- `sdd-index-design.json`
- `sdd-index-real.json`

对应实现：

- `scripts/baseline_governance.py`
- `scripts/refresh_baseline_governance.py`
- `python scripts/run_pipeline.py refresh-baseline-governance`

因此，2026-04-22 文档中“Baseline 缺少 constitution.md / tech-debt.md”的判断已经过期。

### 2.4 设计态索引生命周期已补取消和归档

当前 `run_pipeline.py` 已提供：

- `cancel-design`
- `archive-design`

对应实现：

- `scripts/design_index_lifecycle.py`
- `tests/test_design_index_lifecycle.py`

当前已覆盖：

- `ACTIVE`
- `SUPERSEDED`
- `CANCELLED`
- `IMPLEMENTED`
- 非 ACTIVE 记录归档

因此，2026-04-22 文档中“CANCELLED / 归档动作未实现”的判断已经过期。

### 2.5 Task Slice 深校验已基本补齐

当前 `scripts/generate_test_skeleton.py` 已支持：

- `req_ids` 必须存在于 `feature-brief.md`
- `acceptance_checks` 必须映射回 `design-vN.md` 验收矩阵
- `depends_on` 必须引用存在的切片
- `depends_on` 支持循环依赖检测
- Gate 4 生成 `gate4-skeleton.json`

对应测试：

- `tests/test_task_slice_validation.py`

因此，2026-04-22 文档中“Task Slice 深校验还没补齐”的判断大部分已经过期。

---

## 3. 当前仍然真实存在的问题

## 3.1 Greenfield Gate 2 深校验未闭环

### 当前现状

Greenfield Bootstrap 已经有入口和产物，但 Gate 2 的真实性 / 结构约束校验没有同步深化。

当前 `scripts/check_design_truthfulness.py` 仍主要检查：

- `feature-brief.md` 中是否存在 REQ-ID
- `design-pack/` 是否存在
- design-pack 是否覆盖 REQ-ID
- Markdown 设计包是否过薄

它没有真正检查：

- greenfield feature 是否已生成 bootstrap 产物
- `constitution.md` 是否存在并具备硬约束内容
- `architecture.md` 是否说明模块边界
- `module-layout.md` 是否定义包结构与依赖方向
- `bootstrap-plan.md` 是否覆盖基础设施、测试、监控与回滚规划
- `scaffold-report.json` 是否为 PASS
- 设计文档是否遵守 bootstrap 中定义的模块边界

### 验证结果

执行：

```powershell
python -m pytest tests\test_greenfield_bootstrap_and_release_gate.py tests\test_task_slice_validation.py -q
```

结果：

- `8 passed`
- `2 failed`

失败集中在 Greenfield Gate 2：

- 缺少 bootstrap 产物时，测试期望 Gate 2 返回 bootstrap 相关错误，但当前先因为缺少 REQ-ID 失败。
- bootstrap 产物存在后，测试期望 Gate 2 通过，但当前仍因 feature brief 测试样例缺少 REQ-ID 失败。

这说明当前问题不是“没有 bootstrap”，而是：

**Gate 2 的 greenfield 分支还没有成为 bootstrap-aware 的结构门禁。**

### 影响

- Greenfield 可以生成 bootstrap，但 Gate 2 不能有效消费它。
- 新建工程场景仍可能绕过模块边界、包结构和脚手架约束。
- Flow State 能提示 bootstrap-needed，但 Gate 2 还不能真正阻断 bootstrap 不完整。

### 建议优先级

P0，当前最明确。

建议先补：

- `check_design_truthfulness.py` 中的 `project_mode == greenfield` 分支。
- bootstrap 必需产物存在性检查。
- `scaffold-report.json` 结果检查。
- 最小语义检查：模块边界、包结构、依赖方向、基础设施规划。
- 修正 `tests/test_greenfield_bootstrap_and_release_gate.py` 中测试 fixture，使其包含合法 REQ-ID，避免测试目标被 REQ-ID 前置检查遮蔽。

---

## 3.2 Release Gate 仍偏关键词扫描

### 当前现状

Release Gate 已有最小可用实现，但主要通过关键词搜索判断证据是否存在：

- 回滚 / rollback
- 监控 / monitor / 指标
- 告警 / alert
- 灰度 / canary / 白名单

### 不足

当前还不是结构化上线治理模型：

- 没有固定的 `release-plan.md` schema。
- 没有明确责任人、审批人、执行窗口、回滚触发条件。
- 没有区分“文档提到过”与“治理项已确认”。
- 没有校验监控指标名称、告警规则、灰度批次、回滚 SQL 与应用开关的对应关系。

### 建议优先级

P1。

建议新增：

- `document/template/Release-Plan-模板.md`
- `.spec/schemas/reports/release-gate-report.schema.json` 的扩展字段
- `release-plan.md` 结构化 YAML 区
- Release Gate 从关键词扫描升级为结构化字段校验

---

## 3.3 Gate 3 仍是规则源混合驱动

### 当前现状

Gate 3 已接入 `arch-standard` MCP，能读取：

- `get_feature_rules`
- `semantic_checks`

但 `scripts/check_arch_semantics.py` 仍保留较多硬编码逻辑：

- 分层角色识别
- UI / Controller / Service / Repository / StateMachine 调用方向
- Mermaid sequenceDiagram 分析规则
- 部分 capability tag 对应语义检查

### 风险

- 新增规范时可能需要同时改文档、MCP rule、Gate 3 脚本。
- 规则解释逻辑与规范文本可能漂移。
- `arch-standard` 还不是唯一事实源。

### 建议优先级

P1。

建议将 Gate 3 演进为：

- `arch-standard` 提供规则事实与语义检查定义。
- Gate 3 只做解释器和执行器。
- 对 Mermaid 分层检查保留专门解析器，但规则阈值和角色映射外置到规则文件。

---

## 3.4 Gate 5 仍未深入真实业务实现验证

### 当前现状

Gate 5 当前已经具备：

- 读取 `gate4-skeleton.json`
- 检查 `TODO[REQ-xxx]`
- 尝试执行 Java / Python 测试
- 输出 `verify-report.json`
- 基于 `module-map.json` 分析设计引用类是否映射到真实实现

### 不足

当前仍主要是“设计验证测试 + 实现追溯提示”：

- 生成测试默认仍是设计验证骨架。
- 未建立与目标业务项目 Maven / Gradle 测试任务的稳定映射。
- 真实业务服务、接口、数据库断言还不是标准路径。
- `implementation_result` 当前更像追溯信号，而不是硬阻断。

### 建议优先级

P2。

建议后续增加：

- attached project 的测试命令配置。
- Gate 5 对目标项目测试结果的硬阻断。
- 设计 REQ-ID 到真实测试用例 / 接口用例 / SQL 校验的映射。
- 对 `implementation_result == WARN` 的升级策略。

---

## 3.5 架构规范仍存在双份维护风险

### 当前现状

规范文件同时存在于：

- `docs/arch-standards/`
- `mcp-servers/arch-standard/rules/`

当前两个目录中的同名规则文件内容一致，但仍然是双份维护。

额外差异：

- `mcp-servers/arch-standard/rules/` 下还有 `layering-semantics.json`。
- `arch-standard` 当前优先读取 `mcp-servers/arch-standard/rules/`。

### 风险

- 团队改了 `docs/arch-standards/`，MCP 规则未同步。
- MCP 规则改了，文档未同步。
- Gate 3 和设计生成消费的规则与团队阅读的规则可能逐渐不同。

### 建议优先级

P1。

建议明确单一事实源：

- 方案 A：以 `docs/arch-standards/` 为事实源，MCP 运行时读取 docs。
- 方案 B：以 `mcp-servers/arch-standard/rules/` 为事实源，docs 只引用或生成。

更推荐方案 A，因为规范首先是团队协作资产，其次才是 MCP 输入。

---

## 3.6 P5 运营化治理仍未完全平台化

### 当前已有

- reports schema
- design-pack 最小校验
- project console
- flow overview
- workspace hygiene
- baseline governance
- release gate 最小实现
- agent integration 第一阶段文档和模板

### 仍不足

- 决策项维护机制仍不完整。
- 模板版本策略仍不明确。
- 规范单一事实源未定。
- OpenAPI / SQL / YAML lint 体系仍偏最小实现。
- 各 agent 接入仍是本地源码版，尚未产品化发布。
- `sdd-pipeline-mcp` 尚未封装，agent 仍需要通过终端调用 `run_pipeline.py`。

### 建议优先级

P3。

---

## 4. 当前优先级建议

### P0

1. Greenfield Gate 2 深校验闭环。
2. 修正 Greenfield Gate 2 相关测试 fixture，确保测试验证目标聚焦 bootstrap-aware 行为。

### P1

1. Release Gate 结构化证据模型。
2. 规范单一事实源治理。
3. Gate 3 去硬编码化第一阶段：规则配置外置。

### P2

1. Gate 5 真实业务实现验证。
2. attached project 测试命令与 REQ-ID 映射。
3. `implementation_result` 的阻断策略。

### P3

1. P5 运营化收口。
2. 模板版本治理。
3. Agent Toolkit 产品化发布。
4. `sdd-pipeline-mcp` 封装。

---

## 5. 建议下一步实施计划

### Step 1：修 Greenfield Gate 2

目标：

- `check_design_truthfulness.py` 能识别 `project_mode: greenfield`。
- 缺少 bootstrap 产物时直接给出 bootstrap 相关失败原因。
- bootstrap 产物齐备且 `scaffold-report.json` 为 PASS 时，继续执行 REQ-ID / design-pack 覆盖检查。
- 增加最小语义校验，确保 bootstrap 文件不是空模板。

验收：

```powershell
python -m pytest tests\test_greenfield_bootstrap_and_release_gate.py tests\test_task_slice_validation.py -q
```

应全部通过。

### Step 2：Release Gate 结构化

目标：

- 新增 `release-plan.md` 模板。
- Release Gate 优先读取结构化 YAML。
- 关键词扫描仅作为兼容兜底。

### Step 3：规范单一事实源

目标：

- 明确 `docs/arch-standards/` 或 `mcp-servers/arch-standard/rules/` 其中一个为事实源。
- 增加同步或校验脚本，阻断双份规则漂移。

---

## 6. 验证命令记录

已执行：

```powershell
python scripts/run_pipeline.py --help
python scripts/run_pipeline.py refresh-baseline-governance
python scripts/validate_reports.py specs/pilot-payment-review --stage all
python -m pytest tests/test_greenfield_bootstrap_and_release_gate.py tests/test_task_slice_validation.py -q
```

验证结果：

- `run_pipeline.py --help` 可看到 bootstrap / release-gate / cancel-design / archive-design / refresh-baseline-governance 等入口。
- `refresh-baseline-governance` 可生成 baseline 治理文档。
- `validate_reports.py specs/pilot-payment-review --stage all` 通过。
- Task Slice 深校验相关测试通过。
- Greenfield Gate 2 相关测试仍失败，确认当前 P0 缺口。

---

## 7. 最终结论

2026-04-22 的文档可以作为历史阶段记录保留，但不应再作为当前缺口清单使用。

当前项目最准确的状态是：

**SDD 的 Skill、MCP、Pipeline、Baseline、Release、Task Slice 主体能力已经具备；下一阶段的关键是把 Greenfield Gate 2、Release Gate、Gate 3、Gate 5 和规范治理从“有入口/有最小实现”推进到“可作为团队稳定门禁”。**

---

## 8. 完成后状态

本节对应 2026-04-29 的修复完成结果。

已完成：

- Greenfield Gate 2 从普通 REQ/design-pack 覆盖检查升级为 bootstrap-aware Gate。
- Release Gate 从纯关键词扫描升级为结构化 `release-plan.md` 优先。
- 架构规范增加同步校验入口：`python scripts/run_pipeline.py check-arch-standards-sync`。
- Gate 3 分层语义配置优先读取 `docs/arch-standards/layering-semantics.json`。
- `arch-standard` MCP 的规则原文读取优先使用 `docs/arch-standards/`。
- Gate 5 支持 attached project 的真实验证命令：

```json
{
  "verification_commands": [
    {
      "name": "unit-test",
      "command": ["mvn", "test"]
    }
  ]
}
```

回归结果：

```powershell
python -m pytest -q
```

结果：

- `43 passed`

剩余增强项：

- Release Gate 还可以继续接入更细的审批流、上线窗口和监控平台事实。
- Gate 5 的真实业务验证已具备入口，后续需要项目组在 attached config 中配置各业务仓库自己的测试命令。
- `sdd-pipeline-mcp` 仍属于后续产品化工作，不影响当前本地 Pipeline 闭环。
