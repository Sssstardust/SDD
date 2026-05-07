#!/usr/bin/env python3
"""
build_approval_summary.py

根据 feature-brief、design、gate-report 和 approval.json 生成审批摘要。
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from json_io import read_json
from versioning import detect_latest_design_path, reports_dir_for_design, resolve_feature_dir


def extract_yaml_blocks(text: str) -> list[str]:
    matches = re.findall(r"```yaml\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return matches if matches else [text]


def extract_scalar(yaml_text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", yaml_text)
    if not match:
        return None
    return match.group(1).strip().strip('"').strip("'")


def extract_requirements(feature_text: str) -> list[dict[str, str]]:
    yaml_text = "\n".join(extract_yaml_blocks(feature_text))
    lines = yaml_text.splitlines()
    in_requirements = False
    base_indent = 0
    current: dict[str, str] | None = None
    result: list[dict[str, str]] = []

    for line in lines:
        if not in_requirements:
            if re.match(r"^\s*requirements\s*:\s*$", line):
                in_requirements = True
                base_indent = len(line) - len(line.lstrip())
            continue

        if not line.strip():
            continue

        indent = len(line) - len(line.lstrip())
        if indent <= base_indent and not line.lstrip().startswith("- "):
            break

        req_match = re.match(r"^\s*-\s*req_id\s*:\s*(REQ-\d+)\s*$", line)
        if req_match:
            if current:
                result.append(current)
            current = {"req_id": req_match.group(1)}
            continue

        if current is None:
            continue

        pri_match = re.match(r"^\s*priority\s*:\s*(P\d+)\s*$", line)
        if pri_match:
            current["priority"] = pri_match.group(1)
            continue

        title_match = re.match(r"^\s*title\s*:\s*\"?(.*?)\"?\s*$", line)
        if title_match:
            current["title"] = title_match.group(1)

    if current:
        result.append(current)
    return result


def extract_bullets(block_title: str, text: str) -> list[str]:
    pattern = rf"(?ms)^##\s+\d+\.\s*{re.escape(block_title)}.*?(?=^##\s+\d+\.|\Z)"
    match = re.search(pattern, text)
    if not match:
        return []
    bullets = []
    for line in match.group(0).splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            bullets.append(stripped[2:].strip())
    return bullets


def extract_design_interfaces(design_text: str) -> list[str]:
    return re.findall(r"-\s*`((?:GET|POST|PUT|DELETE|PATCH)\s+[^`]+)`", design_text)


def extract_design_tables(design_text: str) -> list[str]:
    return sorted(set(re.findall(r"\|\s*[^|]+\|\s*[^|]+\|\s*(t_[a-zA-Z0-9_]+)\s*\|", design_text)))


def render_summary(
    *,
    feature_name: str,
    risk_tier: str,
    one_liner: str,
    design_version: str,
    requirements: list[dict[str, str]],
    interfaces: list[str],
    tables: list[str],
    gate_report: dict,
    approval: dict | None,
) -> str:
    lines = [
        f"# 审批摘要：{feature_name}",
        "",
        f"- 设计版本：`{design_version}`",
        f"- 风险级别：`{risk_tier}`",
        f"- 审批状态：`{(approval or {}).get('status', 'N/A')}`",
        f"- 一句话说明：{one_liner or '无'}",
        "",
        "## 1. 需求摘要",
        "",
    ]

    if requirements:
        for item in requirements:
            lines.append(
                f"- `{item.get('req_id', 'REQ-UNKNOWN')}` `{item.get('priority', 'P?')}` {item.get('title', '')}".rstrip()
            )
    else:
        lines.append("- 无")

    lines.extend(
        [
            "",
            "## 2. 核心接口",
            "",
        ]
    )
    lines.extend([f"- `{item}`" for item in interfaces] or ["- 无"])

    lines.extend(
        [
            "",
            "## 3. 涉及表/对象",
            "",
        ]
    )
    lines.extend([f"- `{item}`" for item in tables] or ["- 无"])

    lines.extend(
        [
            "",
            "## 4. 门禁结果摘要",
            "",
        ]
    )
    for gate_name in ("gate2", "gate3", "gate4", "gate5"):
        gate = gate_report.get(gate_name)
        if isinstance(gate, dict):
            lines.append(f"- `{gate_name}`: `{gate.get('result', 'UNKNOWN')}`")

    lines.extend(
        [
            "",
            "## 5. 风险与关注点",
            "",
        ]
    )
    for gate_name in ("gate2", "gate3"):
        gate = gate_report.get(gate_name)
        if isinstance(gate, dict):
            for warning in gate.get("warnings", []):
                lines.append(f"- [{gate_name}] {warning}")
            for error in gate.get("errors", []):
                lines.append(f"- [{gate_name}] {error}")
    if len(lines) > 0 and lines[-1] == "":
        pass
    if lines[-1] == "## 5. 风险与关注点" or lines[-1] == "":
        pass
    if not any(line.startswith("- [gate") for line in lines):
        lines.append("- 当前无额外风险提示")

    lines.extend(
        [
            "",
            "## 6. 审批建议",
            "",
            "- 若业务风险和设计边界已确认，可将 `approval.json.status` 更新为 `APPROVED`。",
            "- 若仍有不确定点，请在 `comments` 中补充审批意见并维持 `PENDING`。",
            "",
        ]
    )

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    args = parser.parse_args()

    feature_dir = resolve_feature_dir(args.feature_dir)
    feature_brief = feature_dir / "feature-brief.md"
    if not feature_brief.exists():
        print(f"[ERROR] 缺少 feature-brief.md: {feature_brief}")
        return 1

    design_path = detect_latest_design_path(feature_dir)
    if not design_path.exists():
        print(f"[ERROR] 缺少设计文档: {design_path}")
        return 1

    reports_dir = reports_dir_for_design(feature_dir, design_path)
    gate_report_path = reports_dir / "gate-report.json"
    if not gate_report_path.exists():
        print(f"[ERROR] 缺少 gate-report.json: {gate_report_path}")
        return 1

    feature_text = feature_brief.read_text(encoding="utf-8")
    yaml_text = "\n".join(extract_yaml_blocks(feature_text))
    feature_name = extract_scalar(yaml_text, "feature_name") or feature_dir.name
    risk_tier = extract_scalar(yaml_text, "risk_tier") or "low"
    one_liner = extract_scalar(yaml_text, "one_liner") or ""
    requirements = extract_requirements(feature_text)

    design_text = design_path.read_text(encoding="utf-8")
    interfaces = extract_design_interfaces(design_text)
    tables = extract_design_tables(design_text)
    gate_report = read_json(gate_report_path)  # type: ignore[assignment]

    approval_path = reports_dir / "approval.json"
    approval = read_json(approval_path) if approval_path.exists() else None

    summary_path = reports_dir / "approval-summary.md"
    summary_path.write_text(
        render_summary(
            feature_name=feature_name,
            risk_tier=risk_tier,
            one_liner=one_liner,
            design_version=design_path.name,
            requirements=requirements,
            interfaces=interfaces,
            tables=tables,
            gate_report=gate_report,
            approval=approval,
        ),
        encoding="utf-8",
    )

    print("[OK] 审批摘要已生成")
    print(f"  - summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
