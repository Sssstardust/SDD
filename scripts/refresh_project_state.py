#!/usr/bin/env python3
"""
refresh_project_state.py

Refresh flow-status artifacts for all formal features.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from attached_project import DEFAULT_ATTACHMENT_PATH
from versioning import iter_feature_dirs


ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feature", default=None, help="Only refresh the named feature directory.")
    parser.add_argument(
        "--attachment-file",
        default=str(DEFAULT_ATTACHMENT_PATH),
        help="Attachment config path used to enumerate feature roots.",
    )
    parser.add_argument("--profile", default=None, help="Optional attachment profile name.")
    args = parser.parse_args()

    attachment_path = Path(args.attachment_file)
    feature_dirs = iter_feature_dirs(attachment_path=attachment_path, profile=args.profile)
    if args.feature:
        feature_dirs = [path for path in feature_dirs if path.name == args.feature]

    count = 0
    for feature_dir in feature_dirs:
        command = [sys.executable, str(ROOT / "scripts" / "build_flow_status.py"), str(feature_dir)]
        if args.attachment_file:
            command.extend(["--attachment-file", str(attachment_path)])
        if args.profile:
            command.extend(["--profile", args.profile])
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            print(f"[FAIL] failed to refresh feature state: {feature_dir}")
            return result.returncode
        count += 1

    print("[OK] project state refresh completed")
    print(f"  - features: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
