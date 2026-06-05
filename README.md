# SDD Skill Asset Library

> **🚀 定位声明**：本仓库是一个 **标准化的 AI Skill 资产库**。它将 SDD（Schema-Driven Design）的复杂架构能力封装为 AI Agent 可直接调用的原子技能，通过严谨的 I/O 契约实现机器与人类的“架构语言对齐”。

本仓库不再仅仅是一个 CLI 工具箱，而是一个**以内核为驱动、以 Skill 为出口**的现代化架构设计中枢。

---

## 🚀 快速上手（唯一推荐接入路径）

> 对 Agent 而言，**SDD 的唯一对外出口是 `skills/`**。MCP 与 CLI 是实现层，除非原子 Skill 未覆盖，否则不直接调用。

1. 让 Agent 加载 `skills/sdd-assistant`（编排出口），它会按统一阶段推进整条链路：
   **分析需求 → 生成设计 → 设计门控 → 生成切片 → 实现门控 → 发布门控**。
2. 编排过程中，`sdd-assistant` 会调用三个原子 Skill：
   `requirement-analyzer`（分析需求）、`sdd-generation`（生成设计）、`sdd-validate`（门控校验）。
3. 非交互 / CI 场景，可直接执行确定性入口：

```powershell
python skills/sdd-assistant/run.py <PRD路径> ./specs/<feature_name> <feature_name>
```

接入细节见 [Agent 接入说明](docs/agent-integration.md)；数据流与产物契约见 [Skill 数据流协议](docs/skill-data-flow.md)。

---

## 🏗️ 核心架构

SDD 采用“内核 + 门面”的双层解耦架构，对外只暴露 Skill 一层：

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

| 技能名称 | 核心职责 | 输出产物（中文显示名） |
| :--- | :--- | :--- |
| **`requirement-analyzer`** | 需求语义解析（分析需求） | `结构化需求.json` + `需求规格.md` |
| **`sdd-generation`** | 架构设计自动生成（生成设计） | `技术方案-v{N}.md` + `设计包/` |
| **`sdd-validate`** | 架构红线与门控校验（设计门控） | `门控报告.json` |
| **`sdd-assistant`** | **唯一编排出口** | 完整验证后的设计包 |

> 产物命名以中文显示名为准，物理文件名遵循统一映射（单一真相源：`sdd_core/infrastructure/artifact_names.py`）。完整命名词表见 [架构与功能改进建议](docs/SDD架构与功能改进建议.md)。

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

## ⚠️ 实现层说明 (MCP / CLI)
`mcp-servers/sdd-pipeline` 与 `sdd_core/run_pipeline.py` 属于**实现层**，供 Skill 内部或高级用法调用。新接入的 Agent 应优先使用 `skills/` 下的标准化入口，而非直接驱动 MCP/CLI，以避免回到“多入口发散”的状态。

---

## 📂 文档索引
- [架构与功能改进建议](docs/SDD架构与功能改进建议.md)
- [Agent 接入说明](docs/agent-integration.md)
- [Skill 数据流协议](docs/skill-data-flow.md)
- [团队接入规范](docs/team-onboarding.md)
- [阶段三重构总结](docs/refactoring/phase3-summary.md)

---
*Powered by SDD Kernel - 使机器理解架构，使人类解放设计。*
