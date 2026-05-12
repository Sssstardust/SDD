#!/usr/bin/env python3
"""
check_approval.py

Minimal approval validation:
- risk_tier=low passes directly
- risk_tier=high requires reports/v{N}/approval.json with status=APPROVED
"""

from __future__ import annotations

import argparse
import re
import sys

from init_approval import main as init_approval_main
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_dir", help="specs/<feature> directory path")
    args = parser.parse_args()

    feature_dir = resolve_feature_dir(args.feature_dir)
    feature_brief = feature_dir / "feature-brief.md"
    if not feature_brief.exists():
        print(f"[ERROR] missing feature-brief.md: {feature_brief}")
        return 1

    yaml_text = "\n".join(extract_yaml_blocks(feature_brief.read_text(encoding="utf-8")))
    risk_tier = extract_scalar(yaml_text, "risk_tier") or "low"

    design_path = detect_latest_design_path(feature_dir)
    approval_path = reports_dir_for_design(feature_dir, design_path) / "approval.json"

    if risk_tier == "low":
        print("[OK] risk_tier=low, approval is not required")
        return 0

    if not approval_path.exists():
        print(f"[WARN] risk_tier=high but approval.json is missing, bootstrapping: {approval_path}")
        saved_argv = list(sys.argv)
        try:
            sys.argv = ["init_approval.py", str(feature_dir)]
            init_code = init_approval_main()
        finally:
            sys.argv = saved_argv
        if init_code != 0 or not approval_path.exists():
            print(f"[FAIL] failed to initialize approval.json: {approval_path}")
            return 1
        print(f"[FAIL] approval scaffold created but status is still not APPROVED: {approval_path}")
        return 1

    data = read_json(approval_path)
    if data.get("status") != "APPROVED":
        print(f"[FAIL] approval exists but status is not APPROVED: {approval_path}")
        return 1

    print("[OK] approval validation passed")
    print(f"  - design_version: {design_path.name}")
    print(f"  - approval: {approval_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
