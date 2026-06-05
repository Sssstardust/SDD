# SDD Skill Asset Library

> **🚀 定位声明**：本仓库是一个 **标准化的 AI Skill 资产库**。它将 SDD（Schema-Driven Design）的复杂架构能力封装为 AI Agent 可直接调用的原子技能，通过严谨的 I/O 契约实现机器与人类的“架构语言对齐”。

本仓库不再仅仅是一个 CLI 工具箱，而是一个**以内核为驱动、以 Skill 为出口**的现代化架构设计中枢。

---

## 🏗️ 核心架构

SDD 采用“内核 + 门面”的双层解耦架构：

### 1. 核心库 (`sdd_core/`) - **The Kernel**
*   **物理形态**：标准 Python Package。
*   **职责**：承载 DDD 建模、架构语义分析、Gate 门禁算法及设计包渲染等核心业务逻辑。
*   **特性**：纯净、无状态、支持通过 Python API 直接导入调用，消除了对 Shell 环境的强依赖。

### 2. 技能层 (`skills/`) - **The Standard Interface**
*   **物理形态**：独立的功能门面。
*   **职责**：为不同 Agent 平台提供统一的接入协议。
*   **组件**：
    *   **JSON Schema**: 严格定义的 `input.schema.json` 和 `output.schema.json`。
    *   **Manifest**: 平台无关的技能元数据 (`manifest.yaml`)。
    *   **Agent Config**: 自动生成的 OpenAI/Claude/Gemini 配置文件。

---

## 🧩 核心技能矩阵 (Core Skills)

| 技能名称 | 核心职责 | 输出产物 |
| :--- | :--- | :--- |
| **`requirement-analyzer`** | 需求语义解析 | `structured-prd.json` |
| **`sdd-generation`** | 架构设计自动生成 | `design-vN.md` + `design-pack/` |
| **`sdd-validate`** | 架构红线与 Gate 校验 | `gate-report.json` |
| **`sdd-assistant`** | **全全自动驾驶编排器** | 完整验证后的设计包 |

---

## 🌐 多 Agent 生态支持

SDD 原生支持多 Agent 平台。通过 `manifest.yaml` 抽象层，您可以一键生成所有主流平台的配置：

```powershell
# 自动为所有 Skill 同步生成最新的 Agent 配置文件
python sdd_core/generate_agent_configs.py
```

支持平台：
- ✅ **OpenAI** (openai.yaml)
- ✅ **Anthropic Claude** (claude.yaml)
- ✅ **Google Gemini** (gemini.yaml)

---

## 🛠️ 开发者指南 (For Kernel & Skill)

### 1. 安装前提
- Python 3.13+ (推荐使用 `uv` 管理环境)
- Node.js 20+ (用于运行 MCP 桥接)
- `python sdd_core/doctor.py`：一键健康检查

### 2. 库化调用示例
现在您可以直接在自己的 Python 代码中使用 SDD 能力：

```python
from sdd_core.application.analyzers.requirement_analyzer import run_generate_feature_brief

# 以纯程序方式生成需求规格
run_generate_feature_brief(
    source_file="prd.md",
    feature_name="new-feature",
    force=True
)
```

### 3. 运行自动化测试
我们为所有 Skill 提供了 100% 的 Schema 契约校验测试：

```powershell
pytest skills/
```

---

## ⚠️ 兼容性说明 (CLI Wrapper)
为了向后兼容现有的 CI/CD 流程，根目录下的 `run_pipeline.py` 仍保留作为 **sdd_core** 的薄包装层，但建议新接入的 Agent 直接调用 `skills/` 下的标准化入口。

---

## 📂 文档索引
- [架构重构审计报告](document/SDD_Architecture_Review.md)
- [Agent 接入深度说明](docs/agent-integration.md)
- [Skill 数据流协议](docs/skill-data-flow.md)
- [团队接入规范](docs/team-onboarding.md)

---
*Powered by SDD Kernel - 使机器理解架构，使人类解放设计。*
