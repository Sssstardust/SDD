# SDD 工具链架构、Skill 资产与冗余分析白皮书

本文档总结了当前 SDD 项目中所有 MCP Server 和 Agent Skill 的职能边界，并针对现有架构中的逻辑重叠与冗余点提出了优化建议。

---

## 1. 核心架构矩阵

### 🛠️ MCP Servers (执行层/事实源)
作为 IDE/Agent 与物理世界的接口，负责获取代码事实、执行底层命令和应用标准。

| MCP Server | 核心职责 | 对应 Gate | 状态 |
| :--- | :--- | :--- | :--- |
| **`sdd-pipeline`** | **统一调度入口**。将 Python 脚本（`run_pipeline.py`）封装为标准工具。 | 全阶段 | 🟢 活跃 |
| **`project-explorer`** | **代码 AST 感知**。深度扫描 Java/Python 源码，生成 `module-map` 物理基线。 | Gate 2/4/5 | 🟢 活跃 |
| **`polyquery`** | **数据库 Schema 感知**。跨数据源（PostgreSQL/MySQL/Oracle）获取真实表结构。 | Gate 2 | 🟢 活跃 |
| **`arch-standard`** | **规则事实源**。定义分层架构（L1-L4）红线及调用链路准则。 | Gate 3 | 🟢 活跃 |

### 🧠 Agent Skills (逻辑层/SOP)
作为 Agent 的“大脑指令集”，定义了复杂的推理逻辑、文档生成协议和研发 SOP。

| Skill | 核心职责 | 核心逻辑位置 | 状态 |
| :--- | :--- | :--- | :--- |
| **`sdd-assistant`** | **流程灵魂**。定义了 SDD 三大铁律（暴露歧义、决策显式化、提供锚点）。 | `skills/sdd-assistant/SKILL.md` | 🟢 活跃 |
| **`requirement-analyzer`** | **需求结构化**。利用 AI 将模糊 PRD 解析为 100% 结构化的 `logic_atoms` JSON。 | `skills/requirement-analyzer/` | 🟢 活跃 |
| **`sdd-generation`** | **设计自动化**。结合 Baseline 物理事实生成 `design-vN.md` 与 `design-pack`。 | `skills/sdd-generation/` | 🟢 活跃 |

---

## 2. 冗余与逻辑重叠分析

经过对 `scripts/`（引擎层）与 `skills/`（逻辑层）的深度对比，识别出以下三个核心冗余点：

### ❌ 冗余点 1：需求解析的“双中心”逻辑漂移
- **现象**：`scripts/generate_feature_brief.py`（启发式/正则）与 `skills/requirement-analyzer`（AI 驱动）各自维护了一套 `TAG_KEYWORDS` 和 `risk_tier` 判定逻辑。
- **风险**：逻辑不同步。在无 AI Key 的本地回退模式下，生成的标签可能与 AI 模式下产生冲突，导致 Gate 校验行为不一致。
- **建议**：
    - **归口管理**：将标签判定、风险等级计算等“确定性逻辑”抽离到 `scripts/application/feature_brief_logic.py`。
    - **引用复用**：让 Python 脚本和 Skill 的 `extract.py` 共同引用该库。

### ❌ 冗余点 2：任务模板的“硬编码”问题
- **现象**：`scripts/generate_task_slices.py` 中直接使用 Python 列表拼接 Markdown 字符串来生成任务切片。
- **风险**：随着“实现预演”伪代码的加入，任务模板变得越来越难以维护，且难以适配不同语言栈（如 Java vs Python）。
- **建议**：
    - **模板化**：引入 `templates/slices/*.md`，脚本仅负责解析 `logic_atoms` 并作为变量填充。

### ❌ 冗余点 3：架构红线的“多头定义”
- **现象**：架构规则分散在 `arch-standard` 的 JSON 配置、`layering-semantics.json` 以及 `check_arch_semantics.py` 的硬编码 Python 函数中。
- **风险**：治理标准不统一，开发者难以感知完整的规则全貌。
- **建议**：
    - **单点事实**：废弃 Python 层的所有硬编码校验，强制通过 `arch-standard` MCP 获取所有规则，脚本仅作为规则的“断言执行器”。

---

## 3. 演进路线建议

1.  **短期 (Phase A)**：执行“逻辑归口”，合并启发式脚本与 AI Skill 的关键词判定逻辑。
2.  **中期 (Phase B)**：剥离任务生成模板，建立 `.spec/templates/slices` 目录，提升任务生成的灵活性。
3.  **长期 (Phase C)**：实现 `arch-standard` 对 Gate 3 的全量接管，清理硬编码规则。

---
*文档生成于：2026-05-15*
*由 SDD 智能架构师 总结并审阅*
