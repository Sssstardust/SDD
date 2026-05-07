#!/usr/bin/env python3
"""
check_feature_brief.py

最小可用的 Feature Brief 校验脚本：
- 检查 [AMBIGUOUS] 是否清零
- 检查必填字段是否存在
- 校验 capability_tags 是否非空
- 校验 requirements 至少包含一个 P0
- 校验 risk_tier 是否不低于规则推导结果
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sdd_yaml import get_list, get_scalar, load_merged_yaml_mapping


def extract_requirement_priorities(data: dict[str, object]) -> list[str]:
    priorities: list[str] = []
    requirements = data.get("requirements")
    if not isinstance(requirements, list):
        return priorities
    for item in requirements:
        if isinstance(item, dict) and item.get("priority"):
            priorities.append(str(item["priority"]))

    return priorities


def has_unresolved_ambiguity(text: str) -> bool:
    in_code_block = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if "[AMBIGUOUS:" in raw_line and "`[AMBIGUOUS:" not in raw_line:
            return True
    return False


def derive_min_risk(tags: set[str]) -> str:
    if "payment" in tags:
        return "high"
    if "async" in tags and "db-change" in tags:
        return "high"
    if "security-sensitive" in tags:
        return "high"
    if "external-call" in tags and "payment" in tags:
        return "high"
    return "low"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_brief", help="feature-brief.md 文件路径")
    args = parser.parse_args()

    path = Path(args.feature_brief)
    if not path.exists():
        print(f"[ERROR] 文件不存在: {path}")
        return 1

    text = path.read_text(encoding="utf-8")
    data = load_merged_yaml_mapping(text)

    errors: list[str] = []
    warnings: list[str] = []

    if has_unresolved_ambiguity(text):
        errors.append("存在未清理的 [AMBIGUOUS] 标记")

    required_scalar_fields = [
        "project_mode",
        "project_mode_source",
        "project_mode_confidence",
        "project_mode_confirmed_by",
        "feature_name",
        "feature_type",
        "one_liner",
        "risk_tier",
    ]
    for field in required_scalar_fields:
        if not get_scalar(data, field):
            errors.append(f"缺少必填字段: {field}")

    project_mode = get_scalar(data, "project_mode")
    if project_mode and project_mode not in {"brownfield", "greenfield", "hybrid"}:
        errors.append(f"非法的 project_mode: {project_mode}")

    tags = get_list(data, "capability_tags")
    if not tags:
        errors.append("capability_tags 不能为空")

    priorities = extract_requirement_priorities(data)
    if not priorities:
        errors.append("requirements 不能为空")
    elif "P0" not in priorities:
        errors.append("requirements 中至少需要一个 P0")

    if tags:
        derived = derive_min_risk(set(tags))
        risk_tier = get_scalar(data, "risk_tier")
        if risk_tier not in {"low", "high"}:
            errors.append(f"非法的 risk_tier: {risk_tier}")
        elif derived == "high" and risk_tier != "high":
            errors.append(
                f"risk_tier 过低：根据 capability_tags 推导最少应为 high，当前为 {risk_tier}"
            )
        elif derived == "low" and risk_tier == "high":
            warnings.append("risk_tier 高于自动推导结果，允许，视为人工升级")

    confidence = get_scalar(data, "project_mode_confidence")
    if confidence:
        try:
            val = float(confidence)
            if not (0 <= val <= 1):
                errors.append("project_mode_confidence 必须在 0~1 之间")
        except ValueError:
            errors.append("project_mode_confidence 必须是数字")

    if errors:
        print("[FAIL] feature-brief 校验失败")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("[OK] feature-brief 校验通过")
    for warning in warnings:
        print(f"  [WARN] {warning}")
    print(f"  - 文件: {path}")
    print(f"  - project_mode: {project_mode}")
    print(f"  - capability_tags: {', '.join(tags)}")
    print(f"  - requirements: {len(priorities)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
