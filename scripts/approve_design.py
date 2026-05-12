#!/usr/bin/env python3
"""
approve_design.py

Update `reports/v{N}/approval.json` for high-risk design approval state.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from concurrency import feature_lock
from init_approval import main as init_approval_main
from json_io import read_json, write_json
from versioning import detect_latest_design_path, reports_dir_for_design, resolve_feature_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_dir", help="specs/<feature> directory path")
    parser.add_argument("--approved-by", required=True, help="approver identity")
    parser.add_argument("--comments", default="", help="approval comments")
    parser.add_argument(
        "--status",
        choices=["APPROVED", "REJECTED", "PENDING"],
        default="APPROVED",
        help="approval status, default APPROVED",
    )
    args = parser.parse_args()

    feature_dir = resolve_feature_dir(args.feature_dir)
    design_path = detect_latest_design_path(feature_dir)
    if not design_path.exists():
        print(f"[ERROR] missing design document: {design_path}")
        return 1

    approval_path = reports_dir_for_design(feature_dir, design_path) / "approval.json"
    if not approval_path.exists():
        print(f"[WARN] missing approval file: {approval_path}")
        saved_argv = list(sys.argv)
        try:
            sys.argv = ["init_approval.py", str(feature_dir)]
            init_code = init_approval_main()
        finally:
            sys.argv = saved_argv
        if init_code != 0 or not approval_path.exists():
            print(f"[ERROR] failed to initialize approval file: {approval_path}")
            return 1

    with feature_lock(feature_dir, phase="approve-design"):
        payload = read_json(approval_path)
        if not isinstance(payload, dict):
            print(f"[ERROR] invalid approval file structure: {approval_path}")
            return 1

        payload["status"] = args.status
        payload["approved_by"] = args.approved_by
        payload["approved_at"] = datetime.now(timezone.utc).isoformat()
        payload["comments"] = args.comments
        write_json(approval_path, payload)

    print("[OK] approval status updated")
    print(f"  - design:   {design_path.name}")
    print(f"  - approval: {approval_path}")
    print(f"  - status:   {args.status}")
    print(f"  - by:       {args.approved_by}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
