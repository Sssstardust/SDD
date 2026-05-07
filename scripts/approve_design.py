#!/usr/bin/env python3
"""
approve_design.py

为高风险设计更新 reports/v{N}/approval.json 的审批状态。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from json_io import read_json
from versioning import detect_latest_design_path, reports_dir_for_design, resolve_feature_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--approved-by", required=True, help="审批人")
    parser.add_argument("--comments", default="", help="审批意见")
    parser.add_argument(
        "--status",
        choices=["APPROVED", "REJECTED", "PENDING"],
        default="APPROVED",
        help="审批状态，默认 APPROVED",
    )
    args = parser.parse_args()

    feature_dir = resolve_feature_dir(args.feature_dir)
    design_path = detect_latest_design_path(feature_dir)
    if not design_path.exists():
        print(f"[ERROR] 缺少设计文档: {design_path}")
        return 1

    approval_path = reports_dir_for_design(feature_dir, design_path) / "approval.json"
    if not approval_path.exists():
        print(f"[ERROR] 缺少审批文件: {approval_path}")
        return 1

    payload = read_json(approval_path)
    if not isinstance(payload, dict):
        print(f"[ERROR] 审批文件结构非法: {approval_path}")
        return 1

    payload["status"] = args.status
    payload["approved_by"] = args.approved_by
    payload["approved_at"] = datetime.now(timezone.utc).isoformat()
    payload["comments"] = args.comments

    approval_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[OK] 审批状态已更新")
    print(f"  - design:   {design_path.name}")
    print(f"  - approval: {approval_path}")
    print(f"  - status:   {args.status}")
    print(f"  - by:       {args.approved_by}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
