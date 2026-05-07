#!/usr/bin/env python3
"""
check_approval.py

最小审批校验：
- risk_tier=low 直接通过
- risk_tier=high 必须存在 reports/v{N}/approval.json 且 status=APPROVED
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
    m = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", yaml_text)
    if not m:
        return None
    return m.group(1).strip().strip('"').strip("'")


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
    risk_tier = extract_scalar(yaml_text, "risk_tier") or "low"

    design_path = detect_latest_design_path(feature_dir)
    approval_path = reports_dir_for_design(feature_dir, design_path) / "approval.json"

    if risk_tier == "low":
        print("[OK] risk_tier=low，无需审批")
        return 0

    if not approval_path.exists():
        print(f"[FAIL] risk_tier=high，但缺少审批文件: {approval_path}")
        return 1

    data = read_json(approval_path)
    if data.get("status") != "APPROVED":
        print(f"[FAIL] 审批文件存在但状态不是 APPROVED: {approval_path}")
        return 1

    print("[OK] 审批校验通过")
    print(f"  - design_version: {design_path.name}")
    print(f"  - approval: {approval_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
