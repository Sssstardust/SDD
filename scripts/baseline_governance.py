#!/usr/bin/env python3
"""
baseline_governance.py

生成 Baseline 治理文档：
- constitution.md：项目级硬约束基线
- tech-debt.md：当前会影响后续设计/实现的开放债项
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from baseline_paths import get_active_baseline_dir
from concurrency import atomic_write_text, path_lock
from flow_state import inspect_feature_state
from versioning import get_primary_design_root, iter_feature_dirs as iter_attached_feature_dirs


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE_DIR = get_active_baseline_dir()
CONSTITUTION_FILE = "constitution.md"
TECH_DEBT_FILE = "tech-debt.md"
DEFAULT_CONSTITUTION_RULES = (
    "所有设计与实现必须遵守分层边界，禁止跨层直连或绕过既有门禁。",
    "P0/P1 需求必须可追溯到测试或验证入口，未覆盖前不得视为完成。",
    "高风险设计必须先完成审批，审批通过后才能进入实现阶段。",
    "Gate 5 未通过前不得写入实现态 baseline。",
    "上线前必须完成回滚方案、监控与告警、灰度策略三项检查。",
)


def extract_yaml_blocks(text: str) -> list[str]:
    matches = re.findall(r"```yaml\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return matches if matches else [text]


def extract_scalar(yaml_text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", yaml_text)
    if not match:
        return None
    return match.group(1).strip().strip('"').strip("'")


def read_feature_meta(feature_dir: Path) -> dict[str, str]:
    feature_brief = feature_dir / "feature-brief.md"
    if not feature_brief.exists():
        return {
            "feature_name": feature_dir.name,
            "project_mode": "unknown",
        }

    yaml_text = "\n".join(extract_yaml_blocks(feature_brief.read_text(encoding="utf-8")))
    return {
        "feature_name": extract_scalar(yaml_text, "feature_name") or feature_dir.name,
        "project_mode": extract_scalar(yaml_text, "project_mode") or "brownfield",
    }


def iter_feature_dirs(specs_dir: Path | None) -> list[Path]:
    if specs_dir is None:
        return iter_attached_feature_dirs()
    if not specs_dir.exists():
        return []
    return [
        path.resolve()
        for path in sorted(specs_dir.iterdir())
        if path.is_dir() and not path.name.startswith(".") and not path.name.startswith("_")
    ]


def collect_constitution_sources(specs_dir: Path) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    for feature_dir in iter_feature_dirs(specs_dir):
        meta = read_feature_meta(feature_dir)
        constitution_path = feature_dir / CONSTITUTION_FILE
        if meta["project_mode"] != "greenfield" or not constitution_path.exists():
            continue
        sources.append(
            {
                "feature_name": meta["feature_name"],
                "path": constitution_path.as_posix(),
            }
        )
    return sources


def build_constitution_markdown(specs_dir: Path) -> tuple[str, int]:
    sources = collect_constitution_sources(specs_dir)
    lines = [
        "# Baseline Constitution",
        "",
        f"- generated_at: {datetime.now(timezone.utc).isoformat()}",
        f"- source_specs_dir: {specs_dir.as_posix()}",
        f"- source_count: {len(sources)}",
        "",
        "## 1. 项目级硬约束",
        "",
    ]
    lines.extend([f"- {rule}" for rule in DEFAULT_CONSTITUTION_RULES])
    lines.extend(
        [
            "",
            "## 2. Greenfield 来源",
            "",
        ]
    )
    if sources:
        for item in sources:
            lines.append(f"- {item['feature_name']}: `{item['path']}`")
    else:
        lines.append("- 当前未发现 greenfield bootstrap constitution，暂以主流程硬约束作为项目级红线基线。")

    lines.extend(
        [
            "",
            "## 3. 维护说明",
            "",
            "- 该文件是 baseline 的治理快照，用于沉淀当前项目默认适用的工程红线。",
            "- 若后续出现新的 greenfield bootstrap 宪法或项目级约束调整，应重跑生成流程更新本文件。",
            "",
        ]
    )
    return "\n".join(lines), len(sources)


def build_tech_debt_items(specs_dir: Path) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for index, feature_dir in enumerate(iter_feature_dirs(specs_dir), start=1):
        state = inspect_feature_state(feature_dir)
        current_stage = str(state.get("current_stage") or "")
        if current_stage == "release-ready":
            continue

        missing = [str(item) for item in state.get("missing_artifacts", [])] if isinstance(state.get("missing_artifacts"), list) else []
        blockers = [str(item) for item in state.get("blockers", [])] if isinstance(state.get("blockers"), list) else []
        reason = str(state.get("reason") or "").strip()
        if not reason and not missing and not blockers:
            continue

        risk_tier = str(state.get("risk_tier") or "low")
        severity = "high" if risk_tier == "high" else ("medium" if blockers else "low")
        summary = reason or (blockers[0] if blockers else (missing[0] if missing else "需要继续推进"))
        items.append(
            {
                "debt_id": f"DEBT-{index:03d}",
                "feature_name": str(state.get("feature_name") or feature_dir.name),
                "current_stage": current_stage or "unknown",
                "risk_tier": risk_tier,
                "severity": severity,
                "summary": summary,
                "next_command": str(state.get("next_command") or ""),
                "missing_artifacts": missing,
                "blockers": blockers,
                "reason": reason,
            }
        )
    return items


def build_tech_debt_markdown(specs_dir: Path) -> tuple[str, int]:
    items = build_tech_debt_items(specs_dir)
    lines = [
        "# 技术债基线",
        "",
        f"- generated_at: {datetime.now(timezone.utc).isoformat()}",
        f"- source_specs_dir: {specs_dir.as_posix()}",
        "",
        "## 1. 采集口径",
        "",
        "- 只记录会影响后续设计、实现或发布决策的开放约束。",
        "- 债项来源于 feature 主流程状态中的缺失产物、阻塞项和待推进原因。",
        "",
        "## 2. 当前债项",
        "",
        "| Debt ID | Feature | Stage | Severity | Summary | Next |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    if items:
        for item in items:
            next_command = str(item["next_command"]).replace("|", "\\|")
            summary = str(item["summary"]).replace("|", "\\|")
            lines.append(
                f"| {item['debt_id']} | {item['feature_name']} | {item['current_stage']} | {item['severity']} | {summary} | `{next_command}` |"
            )
    else:
        lines.append("| DEBT-000 | project | release-ready | low | 当前未检测到需要进入 baseline 的开放技术债 | `-` |")

    lines.extend(
        [
            "",
            "## 3. 债项明细",
            "",
        ]
    )
    if items:
        for item in items:
            lines.extend(
                [
                    f"### {item['debt_id']} {item['feature_name']}",
                    "",
                    f"- 当前阶段：{item['current_stage']}",
                    f"- 风险级别：{item['risk_tier']}",
                    f"- 原因：{item['reason'] or item['summary']}",
                ]
            )
            missing_artifacts = item["missing_artifacts"]
            blockers = item["blockers"]
            if missing_artifacts:
                lines.append("- 缺失产物：")
                lines.extend([f"  - {entry}" for entry in missing_artifacts])
            else:
                lines.append("- 缺失产物：无")
            if blockers:
                lines.append("- 阻塞项：")
                lines.extend([f"  - {entry}" for entry in blockers])
            else:
                lines.append("- 阻塞项：无")
            lines.append(f"- 建议动作：{item['next_command'] or '人工确认下一步'}")
            lines.append("")
    else:
        lines.extend(
            [
                "- 当前所有正式 feature 均已进入 `release-ready`，暂无需要纳入 baseline 的开放技术债。",
                "",
            ]
        )

    return "\n".join(lines), len(items)


def _refresh_governance_baseline_unlocked(
    specs_dir: Path | None = None,
    baseline_dir: Path | None = None,
) -> dict[str, object]:
    effective_specs_dir = specs_dir or get_primary_design_root()
    effective_baseline_dir = baseline_dir or get_active_baseline_dir(create=True, migrate_legacy=True)
    effective_baseline_dir.mkdir(parents=True, exist_ok=True)

    constitution_text, source_count = build_constitution_markdown(effective_specs_dir)
    tech_debt_text, debt_count = build_tech_debt_markdown(effective_specs_dir)

    constitution_path = effective_baseline_dir / CONSTITUTION_FILE
    tech_debt_path = effective_baseline_dir / TECH_DEBT_FILE
    atomic_write_text(constitution_path, constitution_text, encoding="utf-8")
    atomic_write_text(tech_debt_path, tech_debt_text, encoding="utf-8")

    return {
        "constitution_path": str(constitution_path),
        "tech_debt_path": str(tech_debt_path),
        "source_count": source_count,
        "debt_count": debt_count,
    }


def refresh_governance_baseline(
    specs_dir: Path | None = None,
    baseline_dir: Path | None = None,
    *,
    acquire_lock: bool = True,
) -> dict[str, object]:
    effective_baseline_dir = baseline_dir or get_active_baseline_dir(create=True, migrate_legacy=True)
    if not acquire_lock:
        return _refresh_governance_baseline_unlocked(specs_dir, effective_baseline_dir)
    with path_lock(effective_baseline_dir, phase="refresh-baseline-governance"):
        return _refresh_governance_baseline_unlocked(specs_dir, effective_baseline_dir)
