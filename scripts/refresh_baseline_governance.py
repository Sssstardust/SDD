#!/usr/bin/env python3
"""
refresh_baseline_governance.py

刷新 baseline 的治理文档快照。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from baseline_paths import get_active_baseline_dir
from baseline_governance import DEFAULT_BASELINE_DIR, refresh_governance_baseline
from versioning import get_primary_design_root


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--specs-dir",
        default=str(get_primary_design_root()),
        help="feature 目录根路径，默认主 design_root/",
    )
    parser.add_argument(
        "--baseline-dir",
        default=str(get_active_baseline_dir(create=True, migrate_legacy=True)),
        help="baseline 输出目录，默认当前附着项目对应的 baseline 桶",
    )
    args = parser.parse_args()

    specs_dir = Path(args.specs_dir)
    baseline_dir = Path(args.baseline_dir)
    result = refresh_governance_baseline(specs_dir, baseline_dir)

    print("[OK] baseline 治理文档已刷新")
    print(f"  - constitution: {result['constitution_path']}")
    print(f"  - tech debt:    {result['tech_debt_path']}")
    print(f"  - sources:      {result['source_count']}")
    print(f"  - debts:        {result['debt_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
