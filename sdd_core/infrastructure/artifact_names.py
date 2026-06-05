#!/usr/bin/env python3
"""产物命名的单一真相源（中文显示名 <-> 内部物理 key 映射）。

设计取舍：
- 面向人类与 Agent 的文档/提示词统一使用「中文显示名」。
- 物理文件名（部分仍为英文，如 design-pack 目录、*.json 报告）保持稳定，
  避免在流水线重构期破坏既有读写路径与 JSON Schema $id。
- 两者通过本模块集中映射，任何需要展示产物名的地方都应引用这里，
  而不是各自硬编码字符串，从而消除「同一产物多个名字」的发散。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactName:
    """单个产物的命名契约。

    display: 面向人类/Agent 的中文显示名（文档、提示词、报告摘要使用）。
    physical: 实际落盘的文件或目录名（脚本读写、Schema 引用使用）。
    chinese_native: physical 本身是否已是中文（无需额外翻译）。
    """

    key: str
    display: str
    physical: str
    chinese_native: bool = False


# 单一真相源：所有 SDD 产物的命名映射。
ARTIFACTS: dict[str, ArtifactName] = {
    "feature_brief": ArtifactName(
        key="feature_brief",
        display="需求规格.md",
        physical="需求规格.md",
        chinese_native=True,
    ),
    "structured_prd": ArtifactName(
        key="structured_prd",
        display="结构化需求.json",
        physical="structured-prd.json",
    ),
    "design": ArtifactName(
        key="design",
        display="技术方案-v{N}.md",
        physical="技术方案-v{N}.md",
        chinese_native=True,
    ),
    "design_pack": ArtifactName(
        key="design_pack",
        display="设计包",
        physical="design-pack",
    ),
    "task_slices": ArtifactName(
        key="task_slices",
        display="任务切片",
        physical="tasks",
    ),
    "task_slices_manifest": ArtifactName(
        key="task_slices_manifest",
        display="任务列表.json",
        physical="task-slices.generated.json",
    ),
    "gate_report": ArtifactName(
        key="gate_report",
        display="门控报告.json",
        physical="gate-report.json",
    ),
    "verify_report": ArtifactName(
        key="verify_report",
        display="覆盖率报告.json",
        physical="verify-report.json",
    ),
    "approval": ArtifactName(
        key="approval",
        display="审批记录.json",
        physical="approval.json",
    ),
}


def display_name(key: str) -> str:
    """返回产物的中文显示名（用于文档/提示词/报告摘要）。"""
    return ARTIFACTS[key].display


def physical_name(key: str) -> str:
    """返回产物的物理文件/目录名（用于脚本读写）。"""
    return ARTIFACTS[key].physical


def describe_naming_map() -> list[dict[str, object]]:
    """返回完整命名映射，便于校验脚本/文档生成器消费。"""
    return [
        {
            "key": item.key,
            "display": item.display,
            "physical": item.physical,
            "chinese_native": item.chinese_native,
        }
        for item in ARTIFACTS.values()
    ]


if __name__ == "__main__":
    import json

    print(json.dumps(describe_naming_map(), ensure_ascii=False, indent=2))
