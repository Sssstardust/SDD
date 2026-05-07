---
name: SDD 汇报与试点优化方案
overview: 面向技术决策层与落地团队的 SDD v3.4 状态与试点计划；2026-04-29 二次核对后已校准「已完成 / 待办 / 新发现风险」。
updated_at: 2026-04-29
plan_revision: 2
canonical_source: SDD 仓库 document/sdd_汇报与试点优化方案_4445e498.plan.md（与本副本应保持一致）
current_baseline:
  tests: 72（以 `python -m pytest -q` 或 CI 为准）
  completed_highlights:
    - P0 五项（跨平台 Gate5、CI 真复核、Gate2/Release 防伪 PASS、文档 gate5 命名、MCP fallback 显式化）
    - P1·6 baseline_extractors 公共库；P1·9 validate_reports 从 YAML 读 risk_tier；P1·8 risk_tier 下限强校验（禁止 capability 推导 high 时手写 low）
    - P1·11 CI artifact（gate / verify / release-gate 报告）
    - P1 收尾：CI windows/ubuntu matrix；workspace-hygiene 主口径改为 tooling-hygiene
    - P1 收尾：feature-brief / release-plan 关键字段接入 scripts/sdd_yaml.py 共享解析适配层
    - P2 收尾：Release Gate SQL 回滚证据复用 check_design_pack 语义；gate5 支持 --require-attached-execution
    - Design Pack 加强 lint（OpenAPI path 参数、operationId 唯一、CREATE/DROP 回滚配对）— 原 P2 提前落地
    - 回归测试：test_sdd_risk_closure、test_design_pack_lint 等覆盖上述行为
  still_blocking:
    - P1·7 单一事实源（arch 规则、模板、shrimp-rules 双份）
    - P1 收尾：依赖允许时接入 PyYAML / jsonschema 做完整 schema 级校验
    - 多项目隔离（attached-project 单例、ops 日志单文件）— 上量前
todos:
  - id: p0-cross-platform
    content: P0·1 跨平台修复：Gate5 JUnit classpath 用 os.pathsep；venv 同时探测 Windows / POSIX python
    status: completed
  - id: p0-ci-deepen
    content: P0·2 CI：validate-all-reports --require-verify；verify-report result 必须为 PASS
    status: completed
  - id: p0-replace-keyword-checks
    content: P0·3 Gate2 REQ 强证据（排除 openapi/sql 弱位置）；Release 强制结构化 release-plan YAML
    status: completed
  - id: p0-doc-paths
    content: P0·4 README/docs 相对路径；主规范 Gate5 触发为 gate5 子命令
    status: completed
  - id: p0-mcp-warn
    content: P0·5 assemble_context fallback 打 WARN + arch_standard_source + warnings 列表
    status: completed
  - id: p1-extractors
    content: P1·6 scripts/baseline_extractors.py；truthfulness / update_index_design / sync_baseline 共用
    status: completed
  - id: p1-validate-reports
    content: P1·9 validate_reports 从 feature-brief YAML 读 risk_tier（非全文子串）
    status: completed
  - id: p1-risk-tier
    content: P1·8 check_feature_brief：derive_min_risk 下限校验（推导 high 时不允许 brief 写 low）；允许人工升级 high
    status: completed
  - id: p1-ci-artifact
    content: P1·11 CI upload-artifact：specs/**/reports 下 gate-report / verify-report / release-gate-report
    status: completed
  - id: p2-design-pack-lint
    content: P2 提前：check_design_pack OpenAPI/SQL 语义级校验 + test_design_pack_lint
    status: completed
  - id: p1-single-source
    content: P1·7 单一事实源：docs/arch-standards 与 mcp rules；.spec/templates 与 document/.spec/templates；shrimp-rules 归属/语种
    status: pending
  - id: p1-hygiene-rename
    content: P1·10 workspace-hygiene 主口径已改为 tooling-hygiene；旧命令保留兼容；可选 attached-hygiene 后续单列
    status: completed
  - id: p1-ci-linux-matrix
    content: P1 收尾：GitHub Actions 增加 ubuntu-latest job，验证 Gate5/脚本在 Linux 下通过
    status: completed
  - id: p1-yaml-real-parser
    content: P1 收尾：release_plan / feature_brief 关键字段已接入 sdd_yaml 共享解析适配层；后续在依赖允许时接入 PyYAML/jsonschema
    status: in_progress
  - id: p2-release-sql-reuse
    content: P2：Release Gate 的 SQL 回滚证据与 check_design_pack 语义对齐，避免仅 -- DOWN 关键词
    status: completed
  - id: p2-gate5-require-attached
    content: P2：gate5 可选 --require-attached-execution，未配置 verification_commands 时 FAIL 或 WARN 策略可配
    status: completed
  - id: p2-test-mock-hygiene
    content: P2：test_sdd_risk_closure 中替换模块级 ROOT/which mock 为 unittest.mock.patch
    status: pending
  - id: pilot-feature
    content: 试点闭环：1 个真实低风险 feature 跑通 design-cycle → implementation-gates → release-gate，记录耗时与拦截案例
    status: pending
  - id: case-evidence
    content: 汇报素材：记录 1 次 AI 幻觉或设计漂移被 Gate 拦截的真实例子
    status: pending
isProject: false
---

# SDD v3.4 项目深度分析与汇报建议（plan_revision 2）

> **Canonical**：以 SDD 仓库内 `document/sdd_汇报与试点优化方案_4445e498.plan.md` 为准（本文件为同步副本；下方相对链接以仓库根为基准）。  
> 主规范：`skill-mcp-harness-sdd-enhanced-v3.4.md`  
> 差距基线：`document/v3.4-当前实现差距分析-2026-04-29.md`  
> 受众：技术决策层（侧重）+ 落地团队；范围：单团队单 brownfield 试点

## 一、一句话定性（已更新）

> **P0「防伪 PASS」与跨平台、CI 真复核已收口；主链路进入「可信试点」阶段。** Gate 1–5、双态索引、Task Slice、polyquery 接入、批量 `validate-all-reports`、Design Pack 加强 lint 与 `baseline_extractors` 已落地；当前测试约 **72 passed**。剩余重点：**单一事实源、YAML schema 级校验、上量前的多项目隔离**。

## 二、价值闭环（决策层）

### 2.1 三类成本

- **AI 幻觉**：Baseline First + Gate 2 事实源（module-map / schema / index-real）部分阻断。
- **设计漂移**：双态索引、切片、Gate 4/5、REQ 强证据覆盖。
- **流程失控**：`risk_tier`、审批、Gate 5 本地主触发、Release 结构化计划。

### 2.2 核心闭环（简图）

```mermaid
flowchart LR
    PRD[PRD] --> Brief[feature-brief]
    Brief --> Design[design + design-pack]
    Design --> G123[Gate1-3]
    G123 --> Index[sdd-index-design]
    Index --> Slice[task slices]
    Slice --> G4[Gate4 skeleton]
    G4 --> Impl[实现]
    Impl --> G5[Gate5 verify]
    G5 --> Sync[sync_baseline]
    Sync --> Rel[Release Gate]
```

### 2.3 汇报口径

- **定位**：AI 工程治理框架，不是单纯 AI 写代码工具。
- **资产**：baseline、模板、报告 schema、门禁脚本可长期复用。
- **阶段**：单项目试点 OK；多团队平台化需先完成 P1·7 与多项目隔离。

## 三、已完成增量（相对首轮分析）

| 领域 | 说明 |
|------|------|
| Gate5 跨平台 | `os.pathsep`、双路径 venv；见 `scripts/check_design_test_coverage.py` |
| CI | `validate-all-reports --stage all --require-verify`；`validate_verify` 强制 `result==PASS`；artifact 上传 |
| Gate2 REQ | `design_pack_has_req_evidence`：排除 openapi/sql 弱证据；表格/验收/契约关键词行 |
| Release | 结构化 `release-plan.md` 必选；关键词仅 warning |
| MCP | `assemble_context`：fallback 时 stderr WARN + `arch_standard_source` + `warnings` |
| 解析统一 | `scripts/baseline_extractors.py` → truthfulness / `update_index_design` / `sync_baseline` |
| risk_tier | `check_feature_brief.py`：`derive_min_risk` 禁止「推导 high 却写 low」 |
| Design Pack | OpenAPI path 参数、operationId 唯一、CREATE/DROP 回滚配对；`tests/test_design_pack_lint.py` |
| Linux CI | `.github/workflows/sdd-verify.yml` 增加 `windows-latest` / `ubuntu-latest` matrix |
| Tooling hygiene | 产物主命名从 `workspace-hygiene` 改为 `tooling-hygiene`，旧命令保留兼容 |
| Release SQL | Release Gate 的 SQL 回滚证据复用 `check_design_pack` 的回滚语义 |
| Gate5 attached | `gate5 --require-attached-execution` 可强制附着项目验证命令存在并通过 |
| 回归 | `tests/test_sdd_risk_closure.py` 覆盖上述契约 |

## 四、风险清单（二次核对后）

### 已显著缓解

- **伪 PASS（Gate2/Release）**：已按上表收紧；bootstrap greenfield 仍为**关键词列表**语义，属已知弱项。
- **Gate5 跨平台**：已修；**CI 仍仅 windows-latest**，Linux 未在流水线验证。
- **CI 浅复核**：已改为全量正式 feature + `PASS` 强校验 + artifact。
- **解析漂移**：OpenAPI/表/事件提取已抽公共库。
- **MCP 静默降级**：已显式 WARN + 上下文字段。

### 仍须跟踪

1. **单一事实源**：`docs/arch-standards` vs `mcp-servers/arch-standard/rules`；`.spec/templates` vs `document/.spec/templates`；`shrimp-rules.md`。
2. **多项目**：`attached-project.json` 单指针；`project-ops.jsonl` 全局单文件。
3. **YAML schema 级校验**：`release_gate`、`check_feature_brief` 已接入 `sdd_yaml.py` 共享解析适配层；后续仍建议在依赖允许时接入 PyYAML/jsonschema。
4. **测试 mock 风格**：`test_sdd_risk_closure` 模块级替换 `ROOT`/`which`， refactor 易碎。

## 五、P0 / P1 / P2（当前状态）

### P0 — 已完成

1. Gate5 跨平台  
2. CI 真复核（`validate-all-reports --require-verify` + `result==PASS`）  
3. Gate2/Release 防伪 PASS（强证据 + 结构化 release）  
4. 文档与 `gate5` 命名  
5. MCP fallback 显式化  

### P1 — 混合

| 项 | 状态 |
|----|------|
| baseline_extractors | 完成 |
| validate_reports risk YAML | 完成 |
| risk_tier 下限校验 | 完成 |
| CI artifact | 完成 |
| hygiene 命名 P1·10 | 完成 |
| CI ubuntu job P1 收尾 | 完成 |
| 关键 YAML 共享解析适配层 | 进行中 |
| **单一事实源 P1·7** | **待办** |
| **PyYAML/jsonschema schema 级校验** | **待办** |

### P2 — 部分提前 / 部分待办

- **Design Pack lint 加强**：已提前完成。  
- **Gate5 业务验证 / polyquery 安全 / MCP SDK 统一 / 多项目隔离 / 端到端测试 / Gate1 人类摘要**：仍按原路线图推进。  
- **Release SQL 复用 lint、gate5 --require-attached**：已完成。
- **mock 重构**：见 frontmatter todos。

## 六、试点路径（简）

1. **第 1 周**：`onboard-project` → 选 1 个低风险 feature → `design-cycle` → `implementation-gates` → `release-gate`；记录耗时与拦截点。  
2. **第 2 周**：团队评审报告与模板；推进 P1·7 / P1·10 / CI Linux。  
3. **退出准则**：真实 feature 全流程；Gate5 不凑 TODO；结构化 release-plan；**至少 1 条真实拦截案例**。

## 七、一页汇报摘要（2026-04-29 版）

- **是什么**：v3.4 规范落地的 Skill + MCP + Pipeline 工程治理系统。  
- **现在到哪**：P0 全完成；P1 核心项（解析统一、risk 读取、risk_tier 下限、CI artifact、design-pack 加强 lint、tooling-hygiene、Linux CI、YAML 共享解析）已完成；**剩余主要是单一事实源、YAML schema 级校验、多项目隔离**。  
- **价值**：把 AI 不可信前移到可审计的门禁与报告链。  
- **差距**：双份模板/规则、YAML schema 级校验、多项目隔离、端到端试点证据仍待补强。  
- **下一步**：试点跑真实 feature + 抓拦截案例；并行收口 P1·7 与 YAML parser。  
- **决策点**：上量前必须完成单一事实源与多项目隔离策略。

## 八、二次核对纪要（实施侧）

本轮代码审查与测试清单对齐后的**新增待办**中，`p1-ci-linux-matrix`、`p2-release-sql-reuse`、`p2-gate5-require-attached` 已完成；剩余重点为 `p1-yaml-real-parser`、`p2-test-mock-hygiene` 与单一事实源/多项目隔离。  

**Canonical**：仓库 `document/sdd_汇报与试点优化方案_4445e498.plan.md`。更新 plan 时请先改该文件，再按需同步本 `.cursor/plans/` 副本。

## 九、关键文件索引

- Gate5：`scripts/check_design_test_coverage.py`  
- Gate2：`scripts/check_design_truthfulness.py`  
- Release：`scripts/release_gate.py`  
- 批量校验：`scripts/validate_all_reports.py`、`scripts/validate_reports.py`  
- CI：`.github/workflows/sdd-verify.yml`  
- 公共提取：`scripts/baseline_extractors.py`  
- Skill 上下文：`skills/sdd-generation/assemble_context.py`  
- Feature brief：`scripts/check_feature_brief.py`  
- Design pack：`scripts/check_design_pack.py`  
- 回归：`tests/test_sdd_risk_closure.py`、`tests/test_design_pack_lint.py`
