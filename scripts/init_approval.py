#!/usr/bin/env python3
"""
init_approval.py

为高风险设计初始化审批草稿文件 reports/v{N}/approval.json。
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from versioning import detect_latest_design_path, reports_dir_for_design, resolve_feature_dir


def extract_yaml_blocks(text: str) -> list[str]:
    matches = re.findall(r"```yaml\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return matches if matches else [text]


def extract_scalar(yaml_text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", yaml_text)
    if not match:
        return None
    return match.group(1).strip().strip('"').strip("'")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    args = parser.parse_args()

    feature_dir = resolve_feature_dir(args.feature_dir)
    feature_brief = feature_dir / "feature-brief.md"
    if not feature_brief.exists():
        print(f"[ERROR] 缺少 feature-brief.md: {feature_brief}")
        return 1

    yaml_text = "\n".join(extract_yaml_blocks(feature_brief.read_text(encoding="utf-8")))
    feature_name = extract_scalar(yaml_text, "feature_name") or feature_dir.name
    risk_tier = extract_scalar(yaml_text, "risk_tier") or "low"

    design_path = detect_latest_design_path(feature_dir)
    if not design_path.exists():
        print(f"[ERROR] 缺少设计文档: {design_path}")
        return 1

    if risk_tier != "high":
        print("[OK] risk_tier!=high，无需审批草稿")
        return 0

    reports_dir = reports_dir_for_design(feature_dir, design_path)
    reports_dir.mkdir(parents=True, exist_ok=True)
    approval_path = reports_dir / "approval.json"

    if approval_path.exists():
        print(f"[OK] 审批草稿已存在，跳过生成: {approval_path}")
        return 0

    payload = {
        "design_version": design_path.name,
        "feature": feature_name,
        "risk_tier": risk_tier,
        "status": "PENDING",
        "approved_by": "",
        "approved_at": "",
        "comments": "待人工审批后将 status 更新为 APPROVED。"
    }
    approval_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[OK] 审批草稿已生成")
    print(f"  - design:   {design_path.name}")
    print(f"  - approval: {approval_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
