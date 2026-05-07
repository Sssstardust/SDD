#!/usr/bin/env python3
"""
refresh_project_state.py

为所有正式 feature 刷新 flow-status.json / flow-status.md。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from versioning import iter_feature_dirs
ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--feature",
        default=None,
        help="仅刷新指定目录名对应的 feature",
    )
    args = parser.parse_args()

    feature_dirs = iter_feature_dirs()
    if args.feature:
        feature_dirs = [path for path in feature_dirs if path.name == args.feature]

    count = 0
    for feature_dir in feature_dirs:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_flow_status.py"), str(feature_dir)],
            check=False,
        )
        if result.returncode != 0:
            print(f"[FAIL] 刷新 feature 状态失败: {feature_dir}")
            return result.returncode
        count += 1

    print("[OK] 项目状态刷新完成")
    print(f"  - features: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
