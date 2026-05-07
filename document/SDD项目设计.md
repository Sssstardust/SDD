# SDD (Spec-Driven Development) 项目执行流程与阶段汇报

## 1. 项目核心理念
SDD (规格驱动开发) 是一套以 **Spec (规格)** 为唯一事实来源的自动化开发工作流。它旨在通过 AI 辅助，将模糊的需求转化为结构化的设计、任务与测试，并建立端到端的可追溯链条。

**核心目标：**
- **消除幻觉**: 建立双态 Baseline（设计态/实现态），作为 AI 运行的唯一上下文。
- **治理前置**: 通过 `capability_tags` 驱动门禁与产物，实现“以终为始”。
- **闭环验证**: 从需求定义到代码实现，每一步都有对应的自动化 Gate（门禁）进行核销。

---

## 2. SDD 标准执行流程 (v3.4)

项目组当前遵循的 v3.4 流程共分为 7 个核心阶段：

### Phase 0: Baseline 治理 (基准同步)
- **核心作用**: 维护项目的“长期记忆”。建立 `sdd-index-design.json` (设计态索引) 和 `sdd-index-real.json` (实现态索引)。
- **操作目标**: 在开始新需求前，同步现有代码、数据库 Schema 和已审批的设计意图，防止并行开发冲突。

### Phase 1: Feature Brief (需求定义)
- **核心作用**: 意图对齐与风险评估。
- **关键动作**:
  - 定义 `capability_tags` (如 `db-change`, `payment`) 驱动后续自动化逻辑。
  - 自动判定 `risk_tier` (风险等级)。
  - 使用 `[AMBIGUOUS]` 机制强制清理业务歧义。
- **核心产物**: `feature-brief.md`。

### Phase 2: Design & Multi-Gates (详细设计与三级审计)
- **核心作用**: 自动化设计生成与质量把控。
- **关键动作**:
  - 生成 `design-v{N}.md` 及 `design-pack/` (包含接口契约、模型定义等)。
  - **Gate 1 (结构完整性)**: 检查产物是否缺失。
  - **Gate 2 (真实性校验)**: 校验类名、方法签名、字段名是否与现有系统 (Baseline) 冲突或一致。
  - **Gate 3 (架构语义审计)**: 审查事务边界、异常表、幂等策略等深度架构红线。
- **审批机制**: `risk_tier=high` 时必须通过人工审批并产出 `approval.json`。

### Phase 3: Task Slice (任务切片)
- **核心作用**: 将设计拆解为可执行、可追溯的最小单元。
- **拆分逻辑**:
  - **垂直切片 (Vertical)**: 覆盖业务主流程与异常分支。
  - **横切任务 (Cross-cutting)**: 处理技术细节 (如配置、权限、埋点)。
- **核心产物**: `tasks/slice-NNN.md`。

### Phase 4: Gate 4 (测试驱动生成)
- **核心作用**: 实现“测试先行”，定义验证标准。
- **操作目标**: 根据设计中的验收矩阵自动生成测试骨架 (Test Skeleton)，建立 `REQ-ID -> Test Method` 的强映射关系。

### Phase 5: Implementation & Gate 5 (实现与覆盖验证)
- **核心作用**: 代码落地与 PRD 核心功能核销。
- **Gate 5 (覆盖验证)**: 自动扫描测试结果，检查 PRD 中的 P0/P1 需求是否已在代码中被测试覆盖并运行通过。
- **同步机制**: 验证通过后，自动调用 `sync_baseline.py` 将实现状态 (Real Index) 写回 Baseline。

### Phase 6: Release Gate (发布门禁)
- **核心作用**: 上线前的最后风险防御。
- **校验内容**: 回滚脚本有效性、监控告警配置、灰度策略。

---

## 3. 核心工具链映射表

| 执行阶段 | 核心门禁 (Gate) | 对应脚本 (scripts/) | 核心产物/报告 |
| :--- | :--- | :--- | :--- |
| **Phase 0** | - | `refresh_project_state.py` | `sdd-index-real.json` |
| **Phase 1** | **Check Brief** | `check_feature_brief.py` | `feature-brief.md` |
| **Phase 2** | **Gate 1 / 2 / 3** | `run_pipeline.py gate1/2/3` | `gate-report.json` |
| **Phase 3** | **Slice Check** | `bootstrap_feature.py` | `tasks/slice-NNN.md` |
| **Phase 4** | **Gate 4** | `generate_test_skeleton.py` | `gate4-skeleton.json` |
| **Phase 5** | **Gate 5** | `python scripts/run_pipeline.py gate5 <feature>` | `verify-report.json` |
| **Phase 6** | **Release Gate** | `release_gate.py` | `gate_report.py` (Release) |

---

## 4. 阶段性进展总结 (v3.4 演进)

1. **流程对齐**: 统一了全生命周期的阶段命名与目录结构，消除了跨部门沟通的语义歧义。
2. **治理前置**: 引入了 `capability_tags` 治理矩阵，使设计产物和门禁规则能够根据功能特性自动匹配。
3. **闭环链路**: 实现了从 `REQ -> Design -> Task -> Test -> Verify` 的端到端追踪，确保“每一行代码都有需求来源，每一个需求都有测试验证”。
4. **双基线模式**: 成功上线设计态与实现态隔离索引机制，显著降低了 AI 在复杂棕地项目中的幻觉率。

---
